"""
Iteration 26 — Sprint 1 production hardening additions.

Covers the new pieces called out in the review request that are not
already exercised by test_iteration_24/25:

1. /api/qbft/alerts → returns quorum_ok=true, 4/4 validators ONLINE,
   alerts is an empty list when QBFT cluster is healthy.
2. /api/keyrecovery/request body carries `requester_enc_pk_hex` and
   /api/keyrecovery/status/{rid} surfaces it back (no more out-of-band).
3. /api/leads — 5 sequential POSTs all succeed (per-IP cap is 5/min,
   so this verifies the per-tenant limit additions did NOT regress
   the public landing-page lead capture).
4. DeliveryReceipt /ledger/verify → ok=true and signed_with=ML-DSA-65
   after a Certify mail is opened with a real recipient signature.
5. Alert webhook GET as non-sovereign (auditor) is rejected with 403.
"""
from __future__ import annotations
import os
import secrets
import time
import pytest
import requests
from pqcrypto.sign.ml_dsa_65 import sign as mldsa_sign

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
SOV = {"X-Lattice-Role": "sovereign"}
TIMEOUT = 30


def _u(p: str) -> str:
    return f"{BASE_URL}{p}"


# --------------------------------------------------------------------- 1) QBFT alerts
def test_qbft_alerts_healthy_cluster():
    r = requests.get(_u("/api/qbft/alerts"), headers=SOV, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["quorum_ok"] is True, j
    assert j["validators_online"] == 4, j
    assert j["validators_total"] == 4, j
    assert j["alerts"] == [], j
    for v in j["validators"]:
        assert v["status"] == "ONLINE", v


# --------------------------------------------------------------------- 2) requester_enc_pk_hex passthrough
def _register_tenant(slug: str) -> dict:
    body = {
        "name": f"TEST_iter26 {slug.upper()}",
        "domain_prefix": slug,
        "admin_lns_prefix": "admin",
        "admin_display_name": "Iter26 Admin",
    }
    r = requests.post(_u("/api/tenants/register"), json=body, headers=SOV, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    return r.json()


def _register_employee(tenant_id: str, lns: str, display: str,
                       enc_pk_hex: str | None = None) -> dict:
    payload = {
        "lns_name": lns, "department": "QA", "admin": display,
        "tenant_id": tenant_id, "role": "operator",
    }
    if enc_pk_hex:
        payload["enc_public_key_hex"] = enc_pk_hex
    r = requests.post(_u("/api/lns/register"), json=payload,
                      headers=SOV, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    return r.json()


def _x25519_keypair() -> tuple[str, str]:
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PublicFormat, PrivateFormat, NoEncryption,
    )
    sk = X25519PrivateKey.generate()
    return (
        sk.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex(),
        sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex(),
    )


def test_requester_enc_pk_hex_round_trip():
    slug = "i26r" + secrets.token_hex(3)
    t = _register_tenant(slug)
    tid, domain = t["tenant_id"], t["domain"]

    # Build a minimal owner + 3 guardians, all with X25519 keys.
    employees = {}
    for ln in ["alice", "bob", "carla", "dora"]:
        sk_hex, pk_hex = _x25519_keypair()
        e = _register_employee(tid, f"{ln}.{domain}", ln.title(), pk_hex)
        employees[ln] = {"lns": f"{ln}.{domain}", "enc_sk": sk_hex, "enc_pk": pk_hex,
                         "sk": e["secret_key_hex"]}

    owner = employees["alice"]; guardians = [employees["bob"], employees["carla"], employees["dora"]]

    # We need an enrollment to be able to open a recovery request.
    # Use a 'dummy' sealed share — we are only testing the metadata round-trip,
    # not the actual Shamir math (covered by test_iteration_24).
    fake_envelope = {
        "version": 1, "algorithm": "X25519+AES-256-GCM",
        "eph_pk_hex": "00" * 32, "nonce_b64": "AAAAAAAAAAAAAAAA",
        "ct_b64": "AAAAAAAAAAAA",
    }
    r = requests.post(_u("/api/keyrecovery/enroll"), headers=SOV, json={
        "lns": owner["lns"],
        "guardian1_lns": guardians[0]["lns"],
        "guardian2_lns": guardians[1]["lns"],
        "guardian3_lns": guardians[2]["lns"],
        "encrypted_share1": fake_envelope,
        "encrypted_share2": fake_envelope,
        "encrypted_share3": fake_envelope,
        "share1_fingerprint": "a" * 64,
        "share2_fingerprint": "b" * 64,
        "share3_fingerprint": "c" * 64,
    }, timeout=TIMEOUT)
    assert r.status_code == 200, r.text

    # The fresh X25519 public key the requester wants the guardians to seal for.
    _, req_pk = _x25519_keypair()
    r = requests.post(_u("/api/keyrecovery/request"), headers=SOV, json={
        "lns": owner["lns"], "reason": "lost_keypair",
        "requester_enc_pk_hex": req_pk,
    }, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    rq = r.json()
    request_id = rq["request_id"]

    # Status MUST echo the requester pk so guardians can fetch it without
    # any out-of-band coordination.
    r = requests.get(_u(f"/api/keyrecovery/status/{request_id}"),
                     headers=SOV, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    st = r.json()
    assert st.get("requester_enc_pk_hex") == req_pk, st


# --------------------------------------------------------------------- 3) /api/leads sequential cap smoke
def test_leads_five_sequential_calls_succeed():
    """Per-IP cap is 5/min; we issue 5 fast calls and assert they all 200.
    This guards against the new per-tenant RateLimiter additions accidentally
    blocking the public landing-page form."""
    for i in range(5):
        body = {
            "company_name": f"TEST_co_{secrets.token_hex(3)}",
            "contact_name": f"TEST Lead {i}",
            "email": f"lead{i}_{secrets.token_hex(3)}@example.com",
            "notes": "iter26 smoke",
        }
        r = requests.post(_u("/api/leads"), json=body, timeout=TIMEOUT)
        # We only care that we do not get a 429/5xx. The endpoint may
        # return 200/201 depending on body validation.
        assert r.status_code in (200, 201), f"call {i}: {r.status_code} {r.text}"


# --------------------------------------------------------------------- 4) DeliveryReceipt verify ok=true
def _challenge_login(lns: str, sk_hex: str) -> str:
    rc = requests.post(_u("/api/auth/challenge"), json={"lns_name": lns}, timeout=TIMEOUT)
    assert rc.status_code == 200, rc.text
    cd = rc.json()
    sig = mldsa_sign(bytes.fromhex(sk_hex), bytes.fromhex(cd["nonce_hex"]))
    rv = requests.post(_u("/api/auth/verify"), json={
        "challenge_id": cd["challenge_id"], "lns_name": lns,
        "nonce_hex": cd["nonce_hex"], "signature_hex": sig.hex(),
    }, timeout=TIMEOUT)
    assert rv.status_code == 200, rv.text
    return rv.json()["token"]


def test_delivery_receipt_ledger_verify_ok():
    slug = "i26d" + secrets.token_hex(3)
    t = _register_tenant(slug)
    tid, domain = t["tenant_id"], t["domain"]
    sender_lns = t["admin_lns"]
    sender_sk = t["admin_keypair_json"]["secret_key_hex"]

    recipient_lns = f"recv.{domain}"
    rcp = _register_employee(tid, recipient_lns, "Recipient")
    recipient_sk = rcp["secret_key_hex"]

    sender_token = _challenge_login(sender_lns, sender_sk)
    recipient_token = _challenge_login(recipient_lns, recipient_sk)

    # 1. Sender composes a Certify mail.
    r = requests.post(_u("/api/certify/send"), headers={
        "Authorization": f"Bearer {sender_token}",
    }, json={
        "sender_lns": sender_lns, "recipient_lns": recipient_lns,
        "subject": "iter26 PEC test", "body": "Buongiorno, test DeliveryReceipt.",
        "classification": "INTERNAL",
    }, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    mail = r.json()
    mail_id = mail["mail_id"]
    sealed_at = mail["sealed_at"]
    doc_hash = mail["doc_hash"]

    # 2. Recipient signs the PEC canonical with their ML-DSA-65 sk and POSTs read.
    canonical = "|".join([mail_id, sealed_at, sender_lns, recipient_lns, doc_hash]).encode()
    sig_hex = mldsa_sign(bytes.fromhex(recipient_sk), canonical).hex()

    r = requests.post(_u(f"/api/certify/{mail_id}/read"), headers={
        "Authorization": f"Bearer {recipient_token}",
    }, json={"signature_hex": sig_hex}, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    body = r.json()
    receipt = body.get("delivery_receipt") or body.get("receipt") or {}
    tx_id = receipt.get("tx_id") or body.get("tx_id")
    assert tx_id, f"no tx_id in read response: {body}"

    # 3. /ledger/verify must return ok=true and signed_with=ML-DSA-65.
    # Give the QBFT finalisation a tick to propagate.
    time.sleep(1.5)
    r = requests.get(_u(f"/api/ledger/verify/{tx_id}"), headers=SOV, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    v = r.json()
    assert v.get("ok") is True, f"DeliveryReceipt verify failed: {v}"
    assert v.get("signed_with") == "ML-DSA-65", v


# --------------------------------------------------------------------- 5) webhook auditor 403
def test_alert_webhook_auditor_forbidden():
    r = requests.get(_u("/api/alerts/webhooks"),
                     headers={"X-Lattice-Role": "auditor"}, timeout=TIMEOUT)
    assert r.status_code == 403, r.text
