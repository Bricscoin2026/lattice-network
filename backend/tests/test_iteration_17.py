"""
Iteration 17 regression tests — PEC-style cryptographic delivery receipts.

Covers the review-request acceptance criteria:
  1. Register two fresh tenants (lex / altra) via /api/tenants/register
  2. PEC SUCCESS: recipient signs canonical (mail_id|sealed_at|sender|recipient|doc_hash)
     with ML-DSA-65 sk; POST /api/certify/{mail_id}/read returns delivery_receipt
     with tx_id, block_index, signed_by, SHA3-512 preimage (128 hex chars).
  3. PEC IDEMPOTENT: second call on a mail with existing receipt does NOT forge a new TX.
  4. PEC INVALID SIG: garbage signature_hex returns 422 and does NOT mutate the mail.
  5. PEC NO SIG: empty body still marks the mail read_at but does NOT create a receipt.
  6. /api/certify/recent + /api/ledger/blocks + /api/transactions surface the new tx/block.
  7. Cross-tenant blocks still enforced (certify/send 403 cross-company).
  8. Attachments smoke (PDF upload returns 128-char sha3_512_hex).
  9. Frontend /certify renders without crash for unauthenticated user (separate playwright).
"""
import os
import io
import time
import secrets
import hashlib
import pytest
import requests

from pqcrypto.sign.ml_dsa_65 import sign as mldsa_sign


BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
SOV_HEADERS = {"X-Lattice-Role": "sovereign"}
TIMEOUT = 30


# ----------- helpers -----------
def _u(p: str) -> str:
    return f"{BASE_URL}{p}"


def _slug(prefix: str) -> str:
    """Generate a fresh 6-hex slug for unique tenant prefixes per run."""
    return f"{prefix}{secrets.token_hex(3)}"


def _register_tenant(prefix_slug: str, admin_prefix: str = "admin"):
    body = {
        "name": f"TEST_{prefix_slug.upper()} SpA",
        "domain_prefix": prefix_slug,
        "admin_lns_prefix": admin_prefix,
        "admin_display_name": f"Admin {prefix_slug}",
    }
    r = requests.post(_u("/api/tenants/register"), json=body, headers=SOV_HEADERS, timeout=TIMEOUT)
    assert r.status_code == 200, f"tenant register failed {r.status_code}: {r.text}"
    return r.json()


def _register_employee(tenant_id: str, lns_full: str, display: str = "Empl"):
    r = requests.post(_u("/api/lns/register"), headers=SOV_HEADERS, json={
        "lns_name": lns_full,
        "department": "Test",
        "admin": display,
        "tenant_id": tenant_id,
        "role": "operator",
    }, timeout=TIMEOUT)
    assert r.status_code == 200, f"lns register failed {r.status_code}: {r.text}"
    return r.json()


def _login_jwt(lns_full: str, secret_key_hex: str) -> str:
    rc = requests.post(_u("/api/auth/challenge"), json={"lns_name": lns_full}, timeout=15)
    assert rc.status_code == 200, f"challenge failed: {rc.status_code} {rc.text}"
    cd = rc.json()
    sk = bytes.fromhex(secret_key_hex)
    sig = mldsa_sign(sk, bytes.fromhex(cd["nonce_hex"]))
    rv = requests.post(_u("/api/auth/verify"), json={
        "challenge_id": cd["challenge_id"],
        "lns_name": lns_full,
        "nonce_hex": cd["nonce_hex"],
        "signature_hex": sig.hex(),
    }, timeout=15)
    assert rv.status_code == 200, f"verify failed: {rv.status_code} {rv.text}"
    return rv.json()["token"]


# ----------- shared fixture -----------
@pytest.fixture(scope="module")
def env():
    """Bootstrap: 2 tenants (lex + altra), 1 extra employee in each.

    Founder admin secret_key_hex is now exposed via TenantRegisterResponse.admin_keypair_json,
    BUT we also create one extra employee per tenant so we can test sender->recipient where
    sender != recipient (lex admin -> lex user2)."""
    lex_slug = _slug("lex")
    altra_slug = _slug("altra")
    lex_t = _register_tenant(lex_slug, admin_prefix="admin")
    altra_t = _register_tenant(altra_slug, admin_prefix="admin")
    # Founder admin keypair must be present per the agent-to-agent note
    assert lex_t.get("admin_keypair_json"), "admin_keypair_json missing on lex tenant register response"
    assert altra_t.get("admin_keypair_json"), "admin_keypair_json missing on altra tenant register response"
    lex_admin_lns = lex_t["admin_lns"]
    lex_admin_sk = lex_t["admin_keypair_json"]["secret_key_hex"]
    altra_admin_lns = altra_t["admin_lns"]
    altra_admin_sk = altra_t["admin_keypair_json"]["secret_key_hex"]

    # extra employee inside lex (recipient) so we can sender=admin -> recipient=user2
    lex_user2_lns = f"user2.{lex_t['domain']}"
    lex_user2 = _register_employee(lex_t["tenant_id"], lex_user2_lns, "User2")
    lex_user2_sk = lex_user2["secret_key_hex"]

    # extra employee inside altra
    altra_user2_lns = f"user2.{altra_t['domain']}"
    altra_user2 = _register_employee(altra_t["tenant_id"], altra_user2_lns, "User2A")
    altra_user2_sk = altra_user2["secret_key_hex"]

    lex_admin_jwt = _login_jwt(lex_admin_lns, lex_admin_sk)
    lex_user2_jwt = _login_jwt(lex_user2_lns, lex_user2_sk)
    altra_admin_jwt = _login_jwt(altra_admin_lns, altra_admin_sk)

    return {
        "lex": {
            "tenant_id": lex_t["tenant_id"], "domain": lex_t["domain"],
            "admin_lns": lex_admin_lns, "admin_jwt": lex_admin_jwt,
            "user2_lns": lex_user2_lns, "user2_sk": lex_user2_sk, "user2_jwt": lex_user2_jwt,
        },
        "altra": {
            "tenant_id": altra_t["tenant_id"], "domain": altra_t["domain"],
            "admin_lns": altra_admin_lns, "admin_jwt": altra_admin_jwt,
            "user2_lns": altra_user2_lns, "user2_sk": altra_user2_sk,
        },
    }


def _send_certify_mail(env, sender_jwt, sender_lns, recipient_lns, subject="PEC Test"):
    r = requests.post(_u("/api/certify/send"),
                      headers={"Authorization": f"Bearer {sender_jwt}"},
                      json={
                          "sender_lns": sender_lns,
                          "recipient_lns": recipient_lns,
                          "subject": subject,
                          "body": f"Body for {subject} @ {time.time()}",
                          "classification": "INTERNAL",
                      }, timeout=TIMEOUT)
    assert r.status_code == 200, f"certify send failed: {r.status_code} {r.text}"
    return r.json()


def _fetch_recipient_mail(jwt, mail_id):
    r = requests.get(_u("/api/certify/recent?box=inbox&limit=50"),
                     headers={"Authorization": f"Bearer {jwt}"}, timeout=15)
    assert r.status_code == 200, r.text
    for m in r.json():
        if m.get("mail_id") == mail_id:
            return m
    return None


def _build_canonical(mail) -> bytes:
    return "|".join([
        mail["mail_id"],
        mail.get("sealed_at", ""),
        mail.get("sender_lns", ""),
        mail.get("recipient_lns", ""),
        mail.get("doc_hash", ""),
    ]).encode()


# =========== TESTS ===========

class TestTenantBootstrap:
    def test_two_tenants_registered_with_admin_keypair(self, env):
        # Smoke: env fixture already asserts presence of admin_keypair_json.
        assert env["lex"]["tenant_id"].startswith("tnt-")
        assert env["altra"]["tenant_id"].startswith("tnt-")
        assert env["lex"]["domain"] != env["altra"]["domain"]


class TestPecSuccess:
    """Recipient signs canonical → /read returns full delivery_receipt block."""

    def test_pec_full_happy_path(self, env):
        lex = env["lex"]
        # 1. admin -> user2 inside lex
        sent = _send_certify_mail(env, lex["admin_jwt"], lex["admin_lns"], lex["user2_lns"], subject="PEC OK")
        mail_id = sent["mail_id"]

        # 2. user2 fetches the inbox copy (to retrieve sealed_at + doc_hash)
        mail = _fetch_recipient_mail(lex["user2_jwt"], mail_id)
        assert mail is not None, f"recipient inbox missing mail {mail_id}"
        assert mail["recipient_lns"] == lex["user2_lns"]

        # 3. recipient signs canonical with their ML-DSA-65 sk
        canonical = _build_canonical(mail)
        sk = bytes.fromhex(lex["user2_sk"])
        signature_hex = mldsa_sign(sk, canonical).hex()

        # 4. POST /api/certify/{mail_id}/read
        r = requests.post(_u(f"/api/certify/{mail_id}/read"),
                          headers={"Authorization": f"Bearer {lex['user2_jwt']}"},
                          json={"signature_hex": signature_hex}, timeout=TIMEOUT)
        assert r.status_code == 200, f"/read failed: {r.status_code} {r.text}"
        body = r.json()
        assert body["ok"] is True
        receipt = body["delivery_receipt"]
        assert receipt is not None, "delivery_receipt missing in response"
        assert receipt["tx_id"].startswith("tx-"), receipt
        assert isinstance(receipt["block_index"], int) and receipt["block_index"] > 0
        assert receipt["signed_by"] == lex["user2_lns"]
        assert receipt["signature_hex"] == signature_hex
        # SHA3-512 preimage hex = 128 chars
        assert len(receipt["canonical_preimage_sha3_512"]) == 128
        # cross-check: it MUST equal sha3_512(canonical)
        assert receipt["canonical_preimage_sha3_512"] == hashlib.sha3_512(canonical).hexdigest()

        # 5. /certify/recent (sender view) — mail.delivery_receipt populated
        rs = requests.get(_u("/api/certify/recent?box=sent&limit=50"),
                          headers={"Authorization": f"Bearer {lex['admin_jwt']}"},
                          timeout=15)
        assert rs.status_code == 200
        sender_mail = next((m for m in rs.json() if m["mail_id"] == mail_id), None)
        assert sender_mail is not None
        assert sender_mail.get("delivery_receipt") is not None
        assert sender_mail["delivery_receipt"]["tx_id"] == receipt["tx_id"]

        # 6. /ledger/blocks contains the new block_index with the DeliveryReceipt tx
        rb = requests.get(_u("/api/ledger/blocks?limit=50"), timeout=15)
        assert rb.status_code == 200
        blk = next((b for b in rb.json() if b["index"] == receipt["block_index"]), None)
        assert blk is not None, f"ledger block {receipt['block_index']} not found"

        # 7. /api/transactions surfaces the DeliveryReceipt tx
        rt = requests.get(_u("/api/transactions?limit=200"), timeout=15)
        assert rt.status_code == 200, f"GET /api/transactions failed: {rt.status_code} {rt.text}"
        txs = rt.json()
        dr_tx = next((t for t in txs if t.get("tx_id") == receipt["tx_id"]), None)
        assert dr_tx is not None, f"DeliveryReceipt tx {receipt['tx_id']} not in /api/transactions response"


class TestPecIdempotent:
    def test_second_read_call_does_not_recreate_receipt(self, env):
        lex = env["lex"]
        sent = _send_certify_mail(env, lex["admin_jwt"], lex["admin_lns"], lex["user2_lns"], subject="PEC IDEMP")
        mail_id = sent["mail_id"]
        mail = _fetch_recipient_mail(lex["user2_jwt"], mail_id)
        canonical = _build_canonical(mail)
        sk = bytes.fromhex(lex["user2_sk"])
        sig_hex = mldsa_sign(sk, canonical).hex()
        h = {"Authorization": f"Bearer {lex['user2_jwt']}"}

        r1 = requests.post(_u(f"/api/certify/{mail_id}/read"), headers=h, json={"signature_hex": sig_hex}, timeout=TIMEOUT)
        assert r1.status_code == 200
        rec1 = r1.json()["delivery_receipt"]

        r2 = requests.post(_u(f"/api/certify/{mail_id}/read"), headers=h, json={"signature_hex": sig_hex}, timeout=TIMEOUT)
        assert r2.status_code == 200
        rec2 = r2.json()["delivery_receipt"]
        assert rec2 is not None
        assert rec2["tx_id"] == rec1["tx_id"], "idempotent /read created a new TX"
        assert rec2["block_index"] == rec1["block_index"], "idempotent /read advanced block_index"


class TestPecInvalidSig:
    def test_garbage_signature_returns_422_and_no_mutation(self, env):
        lex = env["lex"]
        sent = _send_certify_mail(env, lex["admin_jwt"], lex["admin_lns"], lex["user2_lns"], subject="PEC BADSIG")
        mail_id = sent["mail_id"]
        h = {"Authorization": f"Bearer {lex['user2_jwt']}"}
        bad_sig = "00" * 3309
        r = requests.post(_u(f"/api/certify/{mail_id}/read"), headers=h, json={"signature_hex": bad_sig}, timeout=TIMEOUT)
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"
        assert "invalid delivery signature" in r.text.lower()
        # mail should not be mutated (no read_at, no delivery_receipt)
        mail_after = _fetch_recipient_mail(lex["user2_jwt"], mail_id)
        assert mail_after.get("delivery_receipt") is None
        assert mail_after.get("read_at") in (None, "")


class TestPecNoSig:
    def test_empty_body_marks_read_but_no_receipt(self, env):
        lex = env["lex"]
        sent = _send_certify_mail(env, lex["admin_jwt"], lex["admin_lns"], lex["user2_lns"], subject="PEC NOSIG")
        mail_id = sent["mail_id"]
        h = {"Authorization": f"Bearer {lex['user2_jwt']}"}
        r = requests.post(_u(f"/api/certify/{mail_id}/read"), headers=h, json={}, timeout=TIMEOUT)
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body.get("delivery_receipt") in (None,)
        # but read_at should now be set
        mail_after = _fetch_recipient_mail(lex["user2_jwt"], mail_id)
        assert mail_after.get("read_at"), "read_at not set after non-PEC /read"
        assert mail_after.get("delivery_receipt") is None


class TestCrossTenantBlocks:
    def test_certify_send_cross_company_is_403(self, env):
        lex = env["lex"]
        altra = env["altra"]
        r = requests.post(_u("/api/certify/send"),
                          headers={"Authorization": f"Bearer {lex['admin_jwt']}"},
                          json={
                              "sender_lns": lex["admin_lns"],
                              "recipient_lns": altra["user2_lns"],
                              "subject": "cross", "body": "should be blocked",
                              "classification": "INTERNAL",
                          }, timeout=TIMEOUT)
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"
        assert "cross-company" in r.text.lower()

    def test_non_recipient_cannot_pec_sign(self, env):
        """A user who is NOT the recipient (e.g. cross-tenant) cannot create a delivery receipt.

        We send admin(lex) -> user2(lex). Then altra admin tries /read on that mail_id.
        Expected: 200 ok+self/noop (no mutation) because the endpoint guards `recipient_lns != me`
        with `{"ok": True, "self": True}` (returns silently, NO receipt is created).
        """
        lex = env["lex"]
        altra = env["altra"]
        sent = _send_certify_mail(env, lex["admin_jwt"], lex["admin_lns"], lex["user2_lns"], subject="cross-read")
        mail_id = sent["mail_id"]
        r = requests.post(_u(f"/api/certify/{mail_id}/read"),
                          headers={"Authorization": f"Bearer {altra['admin_jwt']}"},
                          json={"signature_hex": ""}, timeout=TIMEOUT)
        # Either 200 with self/noop (silent), or 404 (cross-tenant mail invisible).
        assert r.status_code in (200, 403, 404), f"unexpected {r.status_code}: {r.text}"
        if r.status_code == 200:
            body = r.json()
            # Must NOT have created a receipt
            assert body.get("delivery_receipt") in (None,)


class TestAttachmentsSmoke:
    def test_pdf_upload_returns_sha3_512(self, env):
        lex = env["lex"]
        # tiny valid-ish PDF magic header
        pdf_bytes = b"%PDF-1.4\n%fake pec test file\n%%EOF\n"
        files = {"file": ("smoke.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        r = requests.post(_u("/api/attachments/upload"),
                          headers={"Authorization": f"Bearer {lex['user2_jwt']}"},
                          files=files, timeout=TIMEOUT)
        assert r.status_code == 200, f"attachment upload failed: {r.status_code} {r.text}"
        body = r.json()
        sha = body.get("sha3_512_hex")
        assert isinstance(sha, str) and len(sha) == 128
        assert sha == hashlib.sha3_512(pdf_bytes).hexdigest()
