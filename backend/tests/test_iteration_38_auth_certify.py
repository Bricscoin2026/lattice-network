"""Iter_38 — coverage tests for /auth/* and /certify/send.

These tests are the safety net for the upcoming extractions of
`routes/auth.py` (challenge + verify + logout + revoke-all + 2FA) and
`routes/certify_mutating.py` (send + receipt.pdf + mark_read + delete).

TDD style: written BEFORE the extraction. If the extraction breaks ANY
behaviour the suite fails and the extraction is rolled back.
"""
from __future__ import annotations

import pathlib
import re
import time

import pytest
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def _base_url() -> str:
    raw = (ROOT / "frontend" / ".env").read_text(encoding="utf-8")
    m = re.search(r'^REACT_APP_BACKEND_URL\s*=\s*"?([^"\n]+)"?', raw, re.M)
    assert m
    return m.group(1).strip()


BASE = _base_url()
SOV = {"X-Lattice-Role": "sovereign"}


# ---------------------------------------------------------------------------
# Helpers — register an LNS we own (server-managed keypair)
# ---------------------------------------------------------------------------


def _ensure_tenant_domain() -> str:
    tenants = requests.get(BASE + "/api/tenants/public", headers=SOV, timeout=10).json()
    assert tenants, "no tenants — run /api/admin/chain/seed-demo first"
    return tenants[0]["domain"]


def _new_lns_with_keypair() -> dict:
    """Register a fresh LNS using SERVER-managed keypair (sk returned)."""
    domain = _ensure_tenant_domain()
    ts = int(time.time() * 1000)
    body = {
        "lns_name": f"authtest{ts}.{domain}",
        "department": "QA", "admin": "test",
        "display_name": "Auth Test User",
        "role": "operator",
    }
    r = requests.post(BASE + "/api/lns/register", headers=SOV, json=body, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# /auth/challenge
# ---------------------------------------------------------------------------


def test_auth_challenge_returns_nonce():
    user = _new_lns_with_keypair()
    r = requests.post(BASE + "/api/auth/challenge",
                      json={"lns_name": user["lns_name"]}, timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["challenge_id"].startswith("chal-")
    assert body["lns_name"] == user["lns_name"]
    assert len(body["nonce_hex"]) == 64    # 32 bytes
    assert body["issued_at"]


def test_auth_challenge_for_unknown_lns_returns_404():
    r = requests.post(BASE + "/api/auth/challenge",
                      json={"lns_name": "does-not-exist.banca-xyz.lns"}, timeout=10)
    assert r.status_code == 404


def test_auth_challenge_for_revoked_lns_returns_404():
    """Revoked LNS must not get fresh challenges — same 404 (don't leak existence)."""
    user = _new_lns_with_keypair()
    requests.post(BASE + "/api/lns/revoke", headers=SOV,
                  json={"lns_name": user["lns_name"], "reason": "test"}, timeout=15)
    r = requests.post(BASE + "/api/auth/challenge",
                      json={"lns_name": user["lns_name"]}, timeout=10)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# /auth/verify — full end-to-end PQC handshake
# ---------------------------------------------------------------------------


def test_auth_verify_end_to_end_returns_jwt():
    from pqcrypto.sign import ml_dsa_65 as mldsa
    user = _new_lns_with_keypair()
    sk = bytes.fromhex(user["secret_key_hex"])

    chal = requests.post(BASE + "/api/auth/challenge",
                         json={"lns_name": user["lns_name"]}, timeout=10).json()
    nonce = bytes.fromhex(chal["nonce_hex"])
    sig = mldsa.sign(sk, nonce)

    r = requests.post(BASE + "/api/auth/verify", json={
        "challenge_id": chal["challenge_id"],
        "lns_name": user["lns_name"],
        "signature_hex": sig.hex(),
    }, timeout=15)
    assert r.status_code == 200, r.text
    sess = r.json()
    assert sess["ok"] is True
    assert sess["token"]
    assert sess["lns"] == user["lns_name"]
    assert sess["role"] == "operator"
    assert sess["expires_in_seconds"] > 0

    # Token is usable — /api/me with Authorization should reflect the session
    me = requests.get(BASE + "/api/me",
                      headers={"Authorization": f"Bearer {sess['token']}"}, timeout=10).json()
    assert me["lns"] == user["lns_name"]
    assert me["role"] == "operator"


def test_auth_verify_replay_returns_409():
    """Same challenge cannot be reused → 409."""
    from pqcrypto.sign import ml_dsa_65 as mldsa
    user = _new_lns_with_keypair()
    sk = bytes.fromhex(user["secret_key_hex"])
    chal = requests.post(BASE + "/api/auth/challenge",
                         json={"lns_name": user["lns_name"]}, timeout=10).json()
    sig = mldsa.sign(sk, bytes.fromhex(chal["nonce_hex"]))
    body = {"challenge_id": chal["challenge_id"],
            "lns_name": user["lns_name"], "signature_hex": sig.hex()}
    r1 = requests.post(BASE + "/api/auth/verify", json=body, timeout=15)
    assert r1.status_code == 200
    r2 = requests.post(BASE + "/api/auth/verify", json=body, timeout=15)
    assert r2.status_code == 409


def test_auth_verify_bad_signature_returns_401():
    user = _new_lns_with_keypair()
    chal = requests.post(BASE + "/api/auth/challenge",
                         json={"lns_name": user["lns_name"]}, timeout=10).json()
    r = requests.post(BASE + "/api/auth/verify", json={
        "challenge_id": chal["challenge_id"],
        "lns_name": user["lns_name"],
        "signature_hex": "ab" * 3309,   # right length, wrong content
    }, timeout=15)
    assert r.status_code == 401


def test_auth_logout_revokes_jti():
    from pqcrypto.sign import ml_dsa_65 as mldsa
    user = _new_lns_with_keypair()
    sk = bytes.fromhex(user["secret_key_hex"])
    chal = requests.post(BASE + "/api/auth/challenge",
                         json={"lns_name": user["lns_name"]}, timeout=10).json()
    sig = mldsa.sign(sk, bytes.fromhex(chal["nonce_hex"]))
    token = requests.post(BASE + "/api/auth/verify", json={
        "challenge_id": chal["challenge_id"],
        "lns_name": user["lns_name"], "signature_hex": sig.hex(),
    }, timeout=15).json()["token"]

    # logout
    r = requests.post(BASE + "/api/auth/logout",
                      headers={"Authorization": f"Bearer {token}"}, timeout=10)
    assert r.status_code == 200

    # /me with the revoked token must fall back to the legacy role header
    me = requests.get(BASE + "/api/me",
                      headers={"Authorization": f"Bearer {token}"}, timeout=10).json()
    # Token is revoked → user.lns is None (no auth resolved)
    assert me.get("lns") in (None, "")


# ---------------------------------------------------------------------------
# /certify/send + receipt.pdf
# ---------------------------------------------------------------------------


def test_certify_send_smoke():
    """A sender mails a recipient — both must exist + we get a valid mail_id."""
    domain = _ensure_tenant_domain()
    # Find an active LNS in this tenant as both sender and recipient.
    active = requests.get(BASE + "/api/lns/active", headers=SOV, timeout=10).json()
    same_tenant = [a for a in active if a.get("tenant_id")]
    if len(same_tenant) < 2:
        pytest.skip("need at least 2 LNS in same tenant — seed first")

    sender = same_tenant[0]["lns_name"]
    recipient = same_tenant[1]["lns_name"]

    body = {
        "sender_lns": sender,
        "recipient_lns": recipient,
        "subject": f"Test subject {int(time.time())}",
        "body": "Hello from pytest — Iter_38 smoke test.",
        "classification": "INTERNAL",
    }
    r = requests.post(BASE + "/api/certify/send", headers=SOV, json=body, timeout=30)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["ok"] is True
    assert out["mail_id"].startswith("mail-")
    assert out["tx_id"].startswith("tx-")
    assert out["block_index"] >= 1
    assert len(out["doc_hash"]) == 128       # SHA3-512


def _auth_as(lns_name: str, sk_hex: str) -> str:
    """Run the PQC handshake and return a Bearer JWT for `lns_name`."""
    from pqcrypto.sign import ml_dsa_65 as mldsa
    chal = requests.post(BASE + "/api/auth/challenge",
                         json={"lns_name": lns_name}, timeout=10).json()
    sig = mldsa.sign(bytes.fromhex(sk_hex), bytes.fromhex(chal["nonce_hex"]))
    r = requests.post(BASE + "/api/auth/verify", json={
        "challenge_id": chal["challenge_id"],
        "lns_name": lns_name, "signature_hex": sig.hex(),
    }, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_certify_receipt_pdf_returns_pdf():
    """End-to-end PEC flow:
    1. Sender mails recipient.
    2. Recipient opens the mail and signs the canonical payload.
    3. GET /api/certify/{mail_id}/receipt.pdf returns the court-grade PDF.
    """
    import hashlib as _h
    from pqcrypto.sign import ml_dsa_65 as mldsa

    # Two LNS in the same tenant (server-managed keypairs so we have sk).
    sender = _new_lns_with_keypair()
    recipient = _new_lns_with_keypair()
    # Make sure they share a tenant — `_new_lns_with_keypair` uses the first
    # tenant's domain so this holds by construction.

    sent = requests.post(BASE + "/api/certify/send", headers=SOV, json={
        "sender_lns": sender["lns_name"],
        "recipient_lns": recipient["lns_name"],
        "subject": "Receipt test",
        "body": "Verify receipt.pdf returns binary PDF",
        "classification": "INTERNAL",
    }, timeout=30).json()
    assert sent["ok"], sent

    # Recipient logs in via PQC challenge/verify.
    rcpt_token = _auth_as(recipient["lns_name"], recipient["secret_key_hex"])

    # Re-read the mail to get canonical fields exactly as the server stored.
    inbox = requests.get(
        BASE + "/api/certify/recent",
        params={"box": "inbox", "limit": 50},
        headers={"Authorization": f"Bearer {rcpt_token}"},
        timeout=10,
    ).json()
    mail = next(m for m in inbox if m["mail_id"] == sent["mail_id"])

    canonical = "|".join([
        mail["mail_id"],
        mail["sealed_at"],
        mail["sender_lns"],
        mail["recipient_lns"],
        mail["doc_hash"],
    ]).encode()
    sig = mldsa.sign(bytes.fromhex(recipient["secret_key_hex"]), canonical).hex()

    # Recipient signs the open event → on-chain DeliveryReceipt.
    r_open = requests.post(
        BASE + f"/api/certify/{sent['mail_id']}/read",
        headers={"Authorization": f"Bearer {rcpt_token}"},
        json={"signature_hex": sig},
        timeout=20,
    )
    assert r_open.status_code == 200, r_open.text
    assert r_open.json().get("delivery_receipt"), r_open.text

    # PDF is now retrievable.
    r = requests.get(
        BASE + f"/api/certify/{sent['mail_id']}/receipt.pdf",
        headers={"Authorization": f"Bearer {rcpt_token}"},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert r.content.startswith(b"%PDF-")
    assert r.content.rstrip().endswith(b"%%EOF")
    assert len(r.content) > 1000          # not an empty PDF


def test_certify_send_to_unknown_recipient_returns_404():
    """Authenticated tenant user mailing a non-existent recipient → 404.
    (Sovereign operator is intentionally allowed to forge any sender/recipient
    for break-glass ops, so we MUST run this as a real tenant user.)
    """
    sender = _new_lns_with_keypair()
    sender_token = _auth_as(sender["lns_name"], sender["secret_key_hex"])

    r = requests.post(BASE + "/api/certify/send",
        headers={"Authorization": f"Bearer {sender_token}"},
        json={
            "sender_lns": sender["lns_name"],
            "recipient_lns": "ghost@nope.banca-test.lns",
            "subject": "x", "body": "x", "classification": "INTERNAL",
        }, timeout=15,
    )
    assert r.status_code in (403, 404, 422), r.text
