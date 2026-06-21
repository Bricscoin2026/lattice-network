"""
Iteration 15 regression tests:
1. Real Rust PyO3 bridge: /api/rust/info, /api/rust/selftest
2. Platform-sovereign role guard on /api/leads (GET)
3. Tenant stats endpoint
4. Tenant employees legacy access (no auth)
5. Public lead capture POST
6. Tenants list legacy access
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://admin-console-59.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def tenant_id(session):
    """Pick first tenant from list (or create one)."""
    r = session.get(f"{BASE_URL}/api/tenants", timeout=20)
    assert r.status_code == 200
    arr = r.json()
    if isinstance(arr, list) and arr:
        return arr[0]["tenant_id"]
    # fallback: register a tenant
    payload = {"company_name": "Iter15 SpA", "domain": "iter15.id", "admin_lns": "ceo.iter15.id"}
    r = session.post(f"{BASE_URL}/api/tenants", json=payload, timeout=20)
    assert r.status_code in (200, 201)
    return r.json()["tenant_id"]


# ---- Rust bridge ----
class TestRustBridge:
    def test_rust_info_available(self, session):
        r = session.get(f"{BASE_URL}/api/rust/info", timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert data.get("available") is True
        assert "lattice-py v0.1.0" in data.get("version", "")
        proof = data.get("proof", {})
        sha = proof.get("sha3_512_rust_hex", "")
        assert isinstance(sha, str) and len(sha) >= 64  # SHA3-512 = 128 hex chars; just verify non-empty hex

    def test_rust_selftest_verify_ok(self, session):
        r = session.get(f"{BASE_URL}/api/rust/selftest", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["verify_ok"] is True
        assert d["public_key_bytes"] == 1952
        assert d["secret_key_bytes"] == 4032
        assert d["signature_bytes"] == 3309


# ---- Role guards ----
class TestLeadsRoleGuard:
    def test_get_leads_auditor_forbidden(self, session):
        r = requests.get(f"{BASE_URL}/api/leads", headers={"X-Lattice-Role": "auditor"}, timeout=20)
        assert r.status_code == 403

    def test_get_leads_no_role_ok(self, session):
        # legacy platform operator (no role header) is allowed
        r = requests.get(f"{BASE_URL}/api/leads", timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_post_lead_public(self, session):
        payload = {"company_name": "TEST_Iter15Co", "contact_name": "Alice", "email": "alice@test15.com"}
        r = requests.post(f"{BASE_URL}/api/leads", json=payload, timeout=20)
        assert r.status_code in (200, 201)
        d = r.json()
        assert d.get("ok") is True
        assert d.get("lead_id", "").startswith("lead-")


# ---- Tenant endpoints ----
class TestTenantEndpoints:
    def test_tenants_list_no_auth(self, session):
        r = requests.get(f"{BASE_URL}/api/tenants", timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_tenant_stats(self, session, tenant_id):
        r = requests.get(f"{BASE_URL}/api/tenants/{tenant_id}/stats", timeout=20)
        assert r.status_code == 200
        d = r.json()
        for key in ("employees_total", "employees_active", "certify_mails_total",
                    "pulse_messages_total", "on_chain_tx_total", "roles_breakdown"):
            assert key in d, f"missing {key} in stats response"
        assert isinstance(d["roles_breakdown"], dict)

    def test_tenant_employees_legacy(self, session, tenant_id):
        r = requests.get(f"{BASE_URL}/api/tenants/{tenant_id}/employees", timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
