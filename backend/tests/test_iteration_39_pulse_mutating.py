"""Iter_39 — coverage tests for /pulse/send + /pulse/session/{conv_id}.

TDD safety net BEFORE extracting these into routes/pulse_mutating.py.
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


def _tenant_domain() -> str:
    tenants = requests.get(BASE + "/api/tenants/public", headers=SOV, timeout=10).json()
    assert tenants, "no tenants — seed first"
    return tenants[0]["domain"]


def _new_lns() -> dict:
    domain = _tenant_domain()
    ts = int(time.time() * 1000)
    body = {
        "lns_name": f"pulsetest{ts}.{domain}",
        "department": "QA", "admin": "test",
        "display_name": "Pulse Test", "role": "operator",
    }
    r = requests.post(BASE + "/api/lns/register", headers=SOV, json=body, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# /pulse/send — smoke
# ---------------------------------------------------------------------------


def test_pulse_send_smoke():
    """Basic happy path: sender mails recipient → ciphertext + RLN slot."""
    sender = _new_lns()
    recipient = _new_lns()
    r = requests.post(BASE + "/api/pulse/send", headers=SOV, json={
        "from_lns": sender["lns_name"],
        "to_lns": recipient["lns_name"],
        "plaintext": f"Hello {time.time():.3f}",
    }, timeout=15)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["ok"] is True
    assert out["msg_id"].startswith("pulse-")
    assert out["conv_id"]
    assert len(out["ciphertext_hex"]) > 0
    assert len(out["nonce_hex"]) == 24       # 12 bytes
    assert out["rln_slot_used"] >= 1
    assert out["rln_slot_max"] >= 1
    assert out["session_fingerprint"]
    assert out["epoch"] >= 1
    assert isinstance(out["route_hops"], list) and len(out["route_hops"]) == 3
    assert out["route_id"].startswith("route-")


def test_pulse_send_same_sender_recipient_returns_422():
    """from_lns == to_lns must 422 (no self-messaging)."""
    user = _new_lns()
    r = requests.post(BASE + "/api/pulse/send", headers=SOV, json={
        "from_lns": user["lns_name"], "to_lns": user["lns_name"],
        "plaintext": "x",
    }, timeout=10)
    assert r.status_code == 422, r.text


def test_pulse_send_unknown_recipient_returns_404():
    """Unknown recipient (tenant user) → 404."""
    from pqcrypto.sign import ml_dsa_65 as mldsa
    sender = _new_lns()
    # Log in as a real tenant user so cross-tenant + recipient checks fire.
    chal = requests.post(BASE + "/api/auth/challenge",
        json={"lns_name": sender["lns_name"]}, timeout=10).json()
    sig = mldsa.sign(bytes.fromhex(sender["secret_key_hex"]),
                     bytes.fromhex(chal["nonce_hex"]))
    token = requests.post(BASE + "/api/auth/verify", json={
        "challenge_id": chal["challenge_id"],
        "lns_name": sender["lns_name"],
        "signature_hex": sig.hex(),
    }, timeout=15).json()["token"]
    r = requests.post(BASE + "/api/pulse/send",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "from_lns": sender["lns_name"],
            "to_lns": "ghost@nope.banca-test.lns",
            "plaintext": "x",
        }, timeout=10)
    assert r.status_code == 404, r.text


def test_pulse_send_empty_message_returns_422():
    """No text + no attachments → 422."""
    sender = _new_lns()
    recipient = _new_lns()
    r = requests.post(BASE + "/api/pulse/send", headers=SOV, json={
        "from_lns": sender["lns_name"], "to_lns": recipient["lns_name"],
        "plaintext": "",
    }, timeout=10)
    assert r.status_code == 422, r.text


def test_pulse_send_rln_quota_enforced():
    """RLN rate limiting kicks in after RLN_MAX_PER_EPOCH messages."""
    sender = _new_lns()
    recipient = _new_lns()
    last_status = None
    for i in range(20):
        r = requests.post(BASE + "/api/pulse/send", headers=SOV, json={
            "from_lns": sender["lns_name"],
            "to_lns": recipient["lns_name"],
            "plaintext": f"msg #{i}",
        }, timeout=10)
        last_status = r.status_code
        if r.status_code == 429:
            break
    assert last_status == 429, f"never hit RLN quota, last={last_status}"


def test_pulse_send_anchor_on_third_message():
    """Every 3rd message emits an on-chain NotarySeal anchor."""
    sender = _new_lns()
    recipient = _new_lns()
    anchor_seen = False
    for i in range(3):
        r = requests.post(BASE + "/api/pulse/send", headers=SOV, json={
            "from_lns": sender["lns_name"],
            "to_lns": recipient["lns_name"],
            "plaintext": f"anchor test #{i}",
        }, timeout=15).json()
        if r.get("anchor_tx_id"):
            anchor_seen = True
            assert r["anchor_tx_id"].startswith("tx-")
            assert r["anchor_block_index"] >= 1
    assert anchor_seen, "third message must produce an anchor TX"


# ---------------------------------------------------------------------------
# /pulse/session/{conv_id}
# ---------------------------------------------------------------------------


def test_pulse_session_lazy_materialise():
    """After sending a message, GET /pulse/session/{conv_id} returns session."""
    sender = _new_lns()
    recipient = _new_lns()
    out = requests.post(BASE + "/api/pulse/send", headers=SOV, json={
        "from_lns": sender["lns_name"], "to_lns": recipient["lns_name"],
        "plaintext": "session test",
    }, timeout=15).json()
    r = requests.get(BASE + f"/api/pulse/session/{out['conv_id']}",
                     headers=SOV, timeout=10)
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["conv_id"] == out["conv_id"]
    assert sender["lns_name"] in s["participants"]
    assert recipient["lns_name"] in s["participants"]
    assert s["fingerprint"]
    assert s["epoch"] >= 1
    assert s["message_number"] >= 1
    assert s["root_key_fingerprint"]


def test_pulse_session_unknown_returns_404():
    r = requests.get(BASE + "/api/pulse/session/does-not-exist",
                     headers=SOV, timeout=10)
    assert r.status_code == 404
