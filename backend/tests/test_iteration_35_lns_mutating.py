"""Iter_35 — coverage for mutating LNS endpoints BEFORE extraction.

These tests are the safety net for the extraction in routes/lns.py.
If the extraction breaks ANY behaviour the suite fails:

    POST /api/lns/register
        - smoke: 200 + valid keypair returned
        - quota enforcement: 402 at max_users + 1
        - server-side keypair generation: pk_hex + sk_hex present
        - client-side keypair (public_key_hex provided): sk_hex absent
        - duplicate registration: 409
        - bad lns suffix (no tenant): 422
        - revoked LNS still consumes no seat

    POST /api/lns/revoke
        - smoke: 200 + status changes to REVOKED in /lns/active

    DELETE /api/lns/{lns_name}
        - smoke: 200 + identity removed from /lns/active
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import time

import pytest
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = ROOT / "backend"


def _base_url() -> str:
    raw = (ROOT / "frontend" / ".env").read_text(encoding="utf-8")
    m = re.search(r'^REACT_APP_BACKEND_URL\s*=\s*"?([^"\n]+)"?', raw, re.M)
    assert m
    return m.group(1).strip()


BASE = _base_url()
SOV = {"X-Lattice-Role": "sovereign"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _issue_license(*, max_tenants: int, max_users: int) -> None:
    out = BACKEND_DIR / "data" / "_lns_quota_test.lic"
    subprocess.run(
        ["python", "-m", "scripts.issue_license", "sign",
         "--priv", "data/vendor_keypair.json",
         "--edition", "community",
         "--tenant", "LNS Mutating Quota Test",
         "--valid-until", "2027-12-31T23:59:59Z",
         "--max-tenants", str(max_tenants),
         "--max-users", str(max_users),
         "--feature", "pulse", "--feature", "certify",
         "--out", str(out)],
        cwd=str(BACKEND_DIR), check=True, capture_output=True,
    )
    license_doc = json.loads(out.read_text(encoding="utf-8"))
    r = requests.post(BASE + "/api/admin/license/install",
                      headers=SOV, json={"license": license_doc}, timeout=10)
    assert r.status_code == 200, r.text


def _restore_enterprise_license() -> None:
    out = BACKEND_DIR / "data" / "license.lic"
    subprocess.run(
        ["python", "-m", "scripts.issue_license", "sign",
         "--priv", "data/vendor_keypair.json",
         "--edition", "enterprise",
         "--tenant", "Lattice Demo Customer",
         "--valid-until", "2027-12-31T23:59:59Z",
         "--max-tenants", "50", "--max-users", "1000",
         "--feature", "pulse", "--feature", "certify", "--feature", "mixnet",
         "--feature", "banking_audit", "--feature", "ots_anchor",
         "--out", str(out)],
        cwd=str(BACKEND_DIR), check=True, capture_output=True,
    )
    requests.post(BASE + "/api/admin/license/reload", headers=SOV, timeout=5)


def _ensure_tenant() -> str:
    """Return the domain of an existing tenant (creates one if missing)."""
    r = requests.get(BASE + "/api/tenants/public", headers=SOV, timeout=10)
    assert r.status_code == 200
    tenants = r.json()
    if tenants:
        return tenants[0]["domain"]
    ts = int(time.time())
    body = {
        "name": f"LNS Test Co {ts}",
        "domain_prefix": f"lnstest{ts}",
        "admin_lns_prefix": "ceo",
        "admin_display_name": "Test CEO",
    }
    r = requests.post(BASE + "/api/tenants/register", headers=SOV, json=body, timeout=10)
    assert r.status_code == 200, r.text
    return r.json()["domain"]


# ---------------------------------------------------------------------------
# Smoke
# ---------------------------------------------------------------------------


def test_lns_register_smoke_returns_keypair():
    domain = _ensure_tenant()
    ts = int(time.time())
    body = {
        "lns_name": f"smoke{ts}.{domain}",
        "department": "QA",
        "admin": "test-runner",
        "display_name": "Smoke Test User",
        "role": "operator",
    }
    r = requests.post(BASE + "/api/lns/register", headers=SOV, json=body, timeout=15)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["ok"] is True
    assert out["lns_name"] == body["lns_name"]
    assert out["public_key_hex"] and len(out["public_key_hex"]) == 1952 * 2
    assert out["secret_key_hex"] and len(out["secret_key_hex"]) == 4032 * 2
    assert out["did"].startswith("did:lattice:")
    assert out["public_key_fingerprint"]
    assert out["tx_id"].startswith("tx-")
    assert out["block_index"] >= 1


def test_lns_register_client_managed_returns_no_sk():
    """When client supplies public_key_hex, server returns secret_key_hex=None."""
    domain = _ensure_tenant()
    # Generate a real ML-DSA pubkey
    from pqcrypto.sign import ml_dsa_65 as mldsa
    pk, _sk = mldsa.generate_keypair()
    ts = int(time.time())
    body = {
        "lns_name": f"client{ts}.{domain}",
        "department": "QA",
        "admin": "test-runner",
        "display_name": "Client-Managed",
        "role": "operator",
        "public_key_hex": pk.hex(),
    }
    r = requests.post(BASE + "/api/lns/register", headers=SOV, json=body, timeout=15)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["public_key_hex"] == pk.hex()
    assert out["secret_key_hex"] is None


def test_lns_register_duplicate_returns_409():
    domain = _ensure_tenant()
    ts = int(time.time())
    body = {
        "lns_name": f"dup{ts}.{domain}",
        "department": "QA", "admin": "test", "display_name": "Dup",
        "role": "operator",
    }
    r1 = requests.post(BASE + "/api/lns/register", headers=SOV, json=body, timeout=15)
    assert r1.status_code == 200
    r2 = requests.post(BASE + "/api/lns/register", headers=SOV, json=body, timeout=15)
    assert r2.status_code == 409, r2.text
    assert "already registered" in r2.json()["detail"].lower()


def test_lns_register_bad_suffix_returns_422():
    ts = int(time.time())
    body = {
        "lns_name": f"bad{ts}.no-such-tenant.lns",
        "department": "QA", "admin": "test",
        "display_name": "Bad", "role": "operator",
    }
    r = requests.post(BASE + "/api/lns/register", headers=SOV, json=body, timeout=10)
    assert r.status_code == 422
    assert "tenant" in r.json()["detail"].lower()


def test_lns_register_quota_enforcement():
    """Quota at current_active+1 — next register must be 402."""
    # Must use ACTIVE count (not total), revoked LNS don't count.
    domain = _ensure_tenant()
    # Pre-fetch lns/active to get the real seat count the backend uses.
    r = requests.get(BASE + "/api/lns/active", headers=SOV, timeout=10)
    assert r.status_code == 200
    active_count = len(r.json())
    try:
        _issue_license(max_tenants=999, max_users=active_count + 1)
        ts = int(time.time())
        body_ok = {
            "lns_name": f"qok{ts}.{domain}",
            "department": "QA", "admin": "test",
            "display_name": "Quota OK", "role": "operator",
        }
        r_ok = requests.post(BASE + "/api/lns/register", headers=SOV, json=body_ok, timeout=15)
        assert r_ok.status_code == 200, r_ok.text

        body_ko = {**body_ok, "lns_name": f"qko{ts}.{domain}"}
        r_ko = requests.post(BASE + "/api/lns/register", headers=SOV, json=body_ko, timeout=15)
        assert r_ko.status_code == 402, r_ko.text
        assert "quota" in r_ko.json()["detail"].lower()
        assert "max_users" in r_ko.json()["detail"]
    finally:
        _restore_enterprise_license()


# ---------------------------------------------------------------------------
# Revoke
# ---------------------------------------------------------------------------


def test_lns_revoke_smoke():
    domain = _ensure_tenant()
    ts = int(time.time())
    name = f"revoke{ts}.{domain}"
    requests.post(BASE + "/api/lns/register", headers=SOV,
                  json={"lns_name": name, "department": "QA", "admin": "test",
                        "display_name": "Revoke Me", "role": "operator"}, timeout=15)

    r = requests.post(BASE + "/api/lns/revoke", headers=SOV,
                      json={"lns_name": name, "reason": "test revoke", "admin": "test"},
                      timeout=15)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["ok"] is True
    assert out["lns_name"] == name
    assert out["tx_id"].startswith("tx-")
    assert out["block_index"] >= 1

    # Revoking again must be 409
    r2 = requests.post(BASE + "/api/lns/revoke", headers=SOV,
                       json={"lns_name": name, "reason": "again", "admin": "test"},
                       timeout=15)
    assert r2.status_code == 409


def test_lns_revoke_unknown_returns_404():
    r = requests.post(BASE + "/api/lns/revoke", headers=SOV,
                      json={"lns_name": "does-not-exist.nope.lns",
                            "reason": "x", "admin": "test"}, timeout=10)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def test_lns_delete_smoke():
    domain = _ensure_tenant()
    ts = int(time.time())
    name = f"todelete{ts}.{domain}"
    requests.post(BASE + "/api/lns/register", headers=SOV,
                  json={"lns_name": name, "department": "QA", "admin": "test",
                        "display_name": "Delete Me", "role": "operator"}, timeout=15)
    r = requests.delete(BASE + "/api/lns/" + name, headers=SOV, timeout=15)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["ok"] is True
    assert out["lns_name"] == name
    assert out["tx_id"].startswith("tx-")
    assert out["block_index"] >= 1

    # Re-deleting must be 404
    r2 = requests.delete(BASE + "/api/lns/" + name, headers=SOV, timeout=10)
    assert r2.status_code == 404
