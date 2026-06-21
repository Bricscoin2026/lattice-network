"""Iteration 9 - REAL PQC (NIST FIPS 204 · ML-DSA-65) + Certify Reply.

These tests exercise the new endpoints and the integration of ML-DSA-65
detached signatures across LNS register/revoke, Certify NotarySeal and
Pulse anchor TX, plus tamper detection.
"""
from __future__ import annotations

import os
import time
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    # Frontend env file is the source of truth in this stack.
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
                break
BASE_URL = (BASE_URL or "").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="session")
def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------------------------------------------------------------------------
# /api/pqc/info
# ---------------------------------------------------------------------------
def test_pqc_info(session: requests.Session) -> None:
    r = session.get(f"{API}/pqc/info", timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["algorithm"] == "ML-DSA-65"
    assert "FIPS 204" in data["standard"]
    assert data["public_key_size_bytes"] == 1952
    assert data["secret_key_size_bytes"] == 4032
    assert data["signature_size_bytes"] == 3309
    assert data["live"] is True


# ---------------------------------------------------------------------------
# LNS register → real ML-DSA-65 keypair → keystore consistency
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def registered_lns(session: requests.Session) -> dict:
    name = f"test.iter9.{uuid.uuid4().hex[:8]}.azienda.id"
    r = session.post(f"{API}/lns/register",
                     json={"lns_name": name, "department": "QA"}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()


def test_register_returns_real_pqc_fingerprint(registered_lns: dict) -> None:
    fp = registered_lns["public_key_fingerprint"]
    assert isinstance(fp, str)
    assert len(fp) == 32
    int(fp, 16)  # must be hex
    assert registered_lns["did"].startswith("did:lattice:")
    assert registered_lns["did"].endswith(fp.lower())


def test_keystore_matches_registered_lns(session: requests.Session,
                                         registered_lns: dict) -> None:
    name = registered_lns["lns_name"]
    r = session.get(f"{API}/keystore/{name}", timeout=15)
    assert r.status_code == 200, r.text
    ks = r.json()
    assert ks["algorithm"] == "ML-DSA-65"
    assert ks["public_key_size_bytes"] == 1952
    assert len(ks["public_key_hex"]) == 1952 * 2  # 3904 hex chars
    assert ks["fingerprint"] == registered_lns["public_key_fingerprint"]


# ---------------------------------------------------------------------------
# Certify send → signed with ML-DSA-65 → /ledger/verify ok=true
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def certify_tx(session: requests.Session, registered_lns: dict) -> dict:
    body = {
        "sender_lns": registered_lns["lns_name"],
        "recipients_lns": ["luca.bianchi.azienda.id"],
        "subject": "Iter9 PQC test",
        "body": "Real ML-DSA-65 signature integration test.",
        "classification": "INTERNAL",
    }
    r = session.post(f"{API}/certify/send", json=body, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()


def test_certify_verify_ok(session: requests.Session,
                           certify_tx: dict, registered_lns: dict) -> None:
    tx_id = certify_tx["tx_id"]
    r = session.get(f"{API}/ledger/verify/{tx_id}", timeout=20)
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["ok"] is True
    assert v["signed_with"] == "ML-DSA-65"
    assert v["signer_entity"] == registered_lns["lns_name"]
    assert "verified" in v["detail"].lower()


# ---------------------------------------------------------------------------
# Tamper detection — corrupt signature in mongo and re-verify.
# ---------------------------------------------------------------------------
def test_tamper_detection(session: requests.Session, certify_tx: dict) -> None:
    # Read backend .env to find the actual DB used by the running server.
    mongo_url = "mongodb://localhost:27017"
    db_name = "test_database"
    try:
        with open("/app/backend/.env") as fh:
            for line in fh:
                k, _, v = line.strip().partition("=")
                v = v.strip().strip('"').strip("'")
                if k == "MONGO_URL" and v:
                    mongo_url = v
                elif k == "DB_NAME" and v:
                    db_name = v
    except OSError:
        pass
    mc = MongoClient(mongo_url)
    db = mc[db_name]
    tx_id = certify_tx["tx_id"]
    orig = db.transactions.find_one({"tx_id": tx_id})
    assert orig is not None
    bad_sig = "deadbeef" + orig["signature"][8:]
    db.transactions.update_one({"tx_id": tx_id}, {"$set": {"signature": bad_sig}})
    try:
        r = session.get(f"{API}/ledger/verify/{tx_id}", timeout=20)
        assert r.status_code == 200, r.text
        v = r.json()
        assert v["ok"] is False
        assert v["signed_with"] == "ML-DSA-65"
    finally:
        # Restore the original signature so the rest of the suite still verifies.
        db.transactions.update_one(
            {"tx_id": tx_id}, {"$set": {"signature": orig["signature"]}}
        )
    # Sanity: after restore, verification must pass again.
    r2 = session.get(f"{API}/ledger/verify/{tx_id}", timeout=20)
    assert r2.json()["ok"] is True


# ---------------------------------------------------------------------------
# LNS revoke also signed + verifiable.
# ---------------------------------------------------------------------------
def test_revoke_signed_and_verifies(session: requests.Session) -> None:
    name = f"test.revoke.{uuid.uuid4().hex[:8]}.azienda.id"
    r = session.post(f"{API}/lns/register",
                     json={"lns_name": name, "department": "QA"}, timeout=20)
    assert r.status_code == 200, r.text
    rv = session.post(f"{API}/lns/revoke",
                      json={"lns_name": name, "reason": "iter9-test", "admin": "console.admin"},
                      timeout=20)
    assert rv.status_code == 200, rv.text
    tx_id = rv.json()["tx_id"]
    v = session.get(f"{API}/ledger/verify/{tx_id}", timeout=20).json()
    assert v["ok"] is True
    assert v["signed_with"] == "ML-DSA-65"
    assert v["signer_entity"] == "admin.console.admin"


# ---------------------------------------------------------------------------
# Pulse anchor TX: 3rd send creates a real-PQC signed anchor.
# ---------------------------------------------------------------------------
def test_pulse_anchor_signed_with_pqc(session: requests.Session) -> None:
    # Use two freshly-registered active identities to avoid quota interference.
    s = f"pulse.s.{uuid.uuid4().hex[:6]}.azienda.id"
    t = f"pulse.t.{uuid.uuid4().hex[:6]}.azienda.id"
    for n in (s, t):
        rr = session.post(f"{API}/lns/register",
                          json={"lns_name": n, "department": "QA"}, timeout=20)
        assert rr.status_code == 200, rr.text
    anchor_tx_id = None
    for i in range(3):
        r = session.post(f"{API}/pulse/send",
                         json={"from_lns": s, "to_lns": t, "plaintext": f"hi #{i + 1}"},
                         timeout=20)
        assert r.status_code == 200, r.text
        if r.json().get("anchor_tx_id"):
            anchor_tx_id = r.json()["anchor_tx_id"]
    assert anchor_tx_id is not None, "expected an anchor TX on the 3rd send"
    v = session.get(f"{API}/ledger/verify/{anchor_tx_id}", timeout=20).json()
    assert v["ok"] is True
    assert v["signed_with"] == "ML-DSA-65"
    assert v["signer_entity"] == s


# ---------------------------------------------------------------------------
# Seeded legacy TX returns ok=false with explanatory detail.
# ---------------------------------------------------------------------------
def test_legacy_seeded_tx_not_verifiable(session: requests.Session) -> None:
    """Production-grade systems should NOT have legacy-seed TX — they're
    a development artefact that gets wiped by `installa.sh`. If any
    survives, /ledger/verify must mark it as ok=false with a clear detail.
    This test is now informational: it asserts the property holds for
    any legacy-seed TX still in the ledger, but does NOT require one to
    exist (a clean production install has zero)."""
    txs = session.get(f"{API}/transactions?limit=200", timeout=20).json()
    assert txs
    found_any_legacy = False
    for tx in reversed(txs):
        v = session.get(f"{API}/ledger/verify/{tx['tx_id']}", timeout=10).json()
        if v["signed_with"] == "legacy-seed":
            found_any_legacy = True
            assert v["ok"] is False
            assert "seed" in v["detail"].lower()
    # Either no legacy-seed TX exist (production-clean) or each was reported correctly.
    if not found_any_legacy:
        print("OK · no legacy-seed TX in the ledger (production-clean state)")


# ---------------------------------------------------------------------------
# Pre-existing endpoints remain healthy.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path", [
    "/ledger/stats",
    "/qbft/nodes",
    "/lns/active",
    "/vendor/stats",
    "/mixnet/topology",
    "/rln/quota?lns=marco.rossi.azienda.id",
])
def test_legacy_endpoints_ok(session: requests.Session, path: str) -> None:
    r = session.get(f"{API}{path}", timeout=15)
    assert r.status_code == 200, r.text
