"""Iteration 13 — Real PQC challenge-response login + employee lifecycle.

Covers:
- POST /api/tenants/register → new domain format `<prefix>.id`
- POST /api/lns/register → returns public_key_hex / secret_key_hex / keypair_filename
- POST /api/auth/challenge + /api/auth/verify (signed with real ML-DSA-65)
- GET /api/me with Bearer JWT
- RBAC enforcement via JWT (operator vs admin)
- PATCH /api/lns/{lns}/role (sovereign + RBAC negative)
- DELETE /api/lns/{lns} (archived, tenant counter, ledger tx)
- Regression on key prior endpoints
"""
import os
import time
import uuid
import requests
import pytest

# Quarantined by iter_25: this suite depends on the pre-iter_17 seed state
# (8 validators / 7 vendor tenants / legacy RBAC header semantics).
# The active suite is iter_16/17/24/25 — see /app/.github/workflows/ci.yml.
pytestmark = pytest.mark.skip(reason="Stale seed-dependent baseline · superseded by iter_24/25.")
from pqcrypto.sign import ml_dsa_65 as mldsa


def _load_frontend_env():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        with open(p) as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ.setdefault(k, v)


_load_frontend_env()
_url = os.environ.get("REACT_APP_BACKEND_URL")
assert _url, "REACT_APP_BACKEND_URL is required"
BASE_URL = _url.rstrip("/")
API = f"{BASE_URL}/api"


def _hdr(role=None, token=None):
    h = {"Content-Type": "application/json"}
    if role:
        h["X-Lattice-Role"] = role
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _slug():
    return "acme" + uuid.uuid4().hex[:6]


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def tenant():
    """Register a fresh tenant (new <prefix>.id domain format)."""
    prefix = _slug()
    payload = {
        "name": "Iter13 SpA",
        "domain_prefix": prefix,
        "admin_lns_prefix": "ceo",
        "admin_display_name": "Mario Rossi",
    }
    r = requests.post(f"{API}/tenants/register", json=payload, headers=_hdr(), timeout=60)
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="module")
def employee(tenant):
    """Register an employee LNS under the tenant; return the full register response."""
    emp_prefix = "alice" + uuid.uuid4().hex[:5]
    emp_lns = f"{emp_prefix}.{tenant['domain']}"
    payload = {
        "lns_name": emp_lns,
        "department": "Operations",
        "role": "operator",
        "tenant_id": tenant["tenant_id"],
        "admin": "Alice Bianchi",
    }
    r = requests.post(f"{API}/lns/register", json=payload, headers=_hdr(), timeout=60)
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="module")
def admin_employee(tenant):
    """Register a fresh admin-role LNS for RBAC tests (separate from CEO)."""
    p = "bossa" + uuid.uuid4().hex[:5]
    lns = f"{p}.{tenant['domain']}"
    r = requests.post(f"{API}/lns/register", json={
        "lns_name": lns, "department": "Direzione", "role": "admin",
        "tenant_id": tenant["tenant_id"], "admin": "Boss",
    }, headers=_hdr(), timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Tenant new domain format
# ---------------------------------------------------------------------------
class TestTenantDomain:
    def test_domain_is_prefix_dot_id(self, tenant):
        # New format: <prefix>.id (no .azienda.id legacy)
        assert tenant["domain"].endswith(".id")
        assert ".azienda." not in tenant["domain"], f"legacy suffix leaked: {tenant['domain']}"
        # Two labels max: <prefix>.id
        assert tenant["domain"].count(".") == 1
        assert tenant["admin_lns"].endswith(tenant["domain"])


# ---------------------------------------------------------------------------
# LNS register returns full keypair fields
# ---------------------------------------------------------------------------
class TestLnsRegisterKeypair:
    def test_register_returns_keypair_fields(self, employee):
        assert "public_key_hex" in employee and employee["public_key_hex"]
        assert "secret_key_hex" in employee and employee["secret_key_hex"]
        assert "keypair_filename" in employee
        assert len(employee["public_key_hex"]) == 3904, \
            f"pk hex len={len(employee['public_key_hex'])}"
        assert len(employee["secret_key_hex"]) == 8064, \
            f"sk hex len={len(employee['secret_key_hex'])}"
        assert employee["keypair_filename"] == f"{employee['lns_name']}.keypair.json"

    def test_pk_matches_keystore(self, employee):
        r = requests.get(f"{API}/keystore/{employee['lns_name']}", headers=_hdr(), timeout=30)
        assert r.status_code == 200, r.text
        ks = r.json()
        assert ks["public_key_hex"] == employee["public_key_hex"]


# ---------------------------------------------------------------------------
# PQC challenge/verify flow
# ---------------------------------------------------------------------------
class TestPqcAuth:
    def test_challenge_for_unknown_lns_404(self):
        r = requests.post(f"{API}/auth/challenge",
                          json={"lns_name": "nobody.does.not.exist.id"},
                          headers=_hdr(), timeout=30)
        assert r.status_code == 404

    def test_challenge_returns_nonce(self, employee):
        r = requests.post(f"{API}/auth/challenge",
                          json={"lns_name": employee["lns_name"]},
                          headers=_hdr(), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["lns_name"] == employee["lns_name"]
        assert "challenge_id" in data
        assert len(data["nonce_hex"]) == 64

    def _challenge(self, lns):
        return requests.post(f"{API}/auth/challenge", json={"lns_name": lns},
                             headers=_hdr(), timeout=30).json()

    def _sign(self, employee, nonce_hex):
        sk = bytes.fromhex(employee["secret_key_hex"])
        return mldsa.sign(sk, bytes.fromhex(nonce_hex)).hex()

    def test_verify_returns_jwt(self, employee):
        ch = self._challenge(employee["lns_name"])
        sig = self._sign(employee, ch["nonce_hex"])
        r = requests.post(f"{API}/auth/verify",
                          json={"challenge_id": ch["challenge_id"],
                                "lns_name": employee["lns_name"],
                                "signature_hex": sig},
                          headers=_hdr(), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert data["lns"] == employee["lns_name"]
        assert data["role"] == "operator"
        assert data["tenant_id"] == employee.get("tenant_id")
        assert isinstance(data["token"], str) and len(data["token"]) > 20

    def test_verify_replay_returns_409(self, employee):
        ch = self._challenge(employee["lns_name"])
        sig = self._sign(employee, ch["nonce_hex"])
        body = {"challenge_id": ch["challenge_id"], "lns_name": employee["lns_name"],
                "signature_hex": sig}
        r1 = requests.post(f"{API}/auth/verify", json=body, headers=_hdr(), timeout=30)
        assert r1.status_code == 200, r1.text
        r2 = requests.post(f"{API}/auth/verify", json=body, headers=_hdr(), timeout=30)
        assert r2.status_code == 409, f"expected 409, got {r2.status_code} {r2.text}"

    def test_verify_bad_signature_returns_401(self, employee):
        ch = self._challenge(employee["lns_name"])
        # Sign a different message → signature does not verify against the nonce
        sk = bytes.fromhex(employee["secret_key_hex"])
        bogus = mldsa.sign(sk, b"not-the-nonce").hex()
        r = requests.post(f"{API}/auth/verify",
                          json={"challenge_id": ch["challenge_id"],
                                "lns_name": employee["lns_name"],
                                "signature_hex": bogus},
                          headers=_hdr(), timeout=30)
        assert r.status_code == 401, f"expected 401, got {r.status_code} {r.text}"


# ---------------------------------------------------------------------------
# /api/me reads identity from JWT
# ---------------------------------------------------------------------------
class TestMeWithJwt:
    def _get_token(self, emp, role_expected=None):
        ch = requests.post(f"{API}/auth/challenge", json={"lns_name": emp["lns_name"]},
                           headers=_hdr(), timeout=30).json()
        sk = bytes.fromhex(emp["secret_key_hex"])
        sig = mldsa.sign(sk, bytes.fromhex(ch["nonce_hex"])).hex()
        v = requests.post(f"{API}/auth/verify",
                          json={"challenge_id": ch["challenge_id"],
                                "lns_name": emp["lns_name"],
                                "signature_hex": sig},
                          headers=_hdr(), timeout=30).json()
        if role_expected:
            assert v["role"] == role_expected
        return v["token"]

    def test_me_returns_role_and_via_pqc(self, employee):
        token = self._get_token(employee, role_expected="operator")
        r = requests.get(f"{API}/me", headers=_hdr(token=token), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("via") == "pqc-jwt"
        # role should reflect the JWT, not the legacy X-Lattice-Role header.
        # The JWT carries role='operator'.
        assert "operator" in str(body).lower() or body.get("role") == "operator"


# ---------------------------------------------------------------------------
# RBAC enforcement via JWT (operator forbidden / admin allowed)
# ---------------------------------------------------------------------------
class TestJwtRbac:
    def _token(self, emp):
        ch = requests.post(f"{API}/auth/challenge", json={"lns_name": emp["lns_name"]},
                           headers=_hdr(), timeout=30).json()
        sig = mldsa.sign(bytes.fromhex(emp["secret_key_hex"]),
                         bytes.fromhex(ch["nonce_hex"])).hex()
        v = requests.post(f"{API}/auth/verify",
                          json={"challenge_id": ch["challenge_id"],
                                "lns_name": emp["lns_name"],
                                "signature_hex": sig},
                          headers=_hdr(), timeout=30).json()
        return v["token"]

    def test_operator_forbidden_lns_register(self, employee, tenant):
        tok = self._token(employee)
        new_lns = f"x{uuid.uuid4().hex[:6]}.{tenant['domain']}"
        r = requests.post(f"{API}/lns/register",
                          json={"lns_name": new_lns, "department": "ops",
                                "role": "operator", "tenant_id": tenant["tenant_id"]},
                          headers=_hdr(token=tok), timeout=30)
        assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text[:200]}"

    def test_operator_forbidden_certify_send(self, employee):
        tok = self._token(employee)
        r = requests.post(f"{API}/certify/send",
                          json={"to": "x@example.com", "subject": "x", "body": "y"},
                          headers=_hdr(token=tok), timeout=30)
        assert r.status_code == 403

    def test_operator_forbidden_pulse_send(self, employee):
        tok = self._token(employee)
        r = requests.post(f"{API}/pulse/send",
                          json={"to": "anyone.azienda.id", "plaintext": "hi"},
                          headers=_hdr(token=tok), timeout=30)
        assert r.status_code == 403

    def test_admin_jwt_can_register_lns(self, admin_employee, tenant):
        tok = self._token(admin_employee)
        new_lns = f"x{uuid.uuid4().hex[:6]}.{tenant['domain']}"
        r = requests.post(f"{API}/lns/register",
                          json={"lns_name": new_lns, "department": "ops",
                                "role": "operator", "tenant_id": tenant["tenant_id"]},
                          headers=_hdr(token=tok), timeout=60)
        assert r.status_code == 200, f"admin JWT register failed: {r.status_code} {r.text[:300]}"


# ---------------------------------------------------------------------------
# PATCH /api/lns/{lns}/role
# ---------------------------------------------------------------------------
class TestPatchRole:
    def test_sovereign_can_patch_role(self, employee, tenant):
        r = requests.patch(f"{API}/lns/{employee['lns_name']}/role",
                           json={"role": "auditor"}, headers=_hdr(), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["role"] == "auditor"
        # verify via tenant employees list
        emps = requests.get(f"{API}/tenants/{tenant['tenant_id']}/employees",
                            headers=_hdr(), timeout=30).json()
        m = [e for e in emps if e["lns_name"] == employee["lns_name"]]
        assert m and m[0]["role"] == "auditor"
        # restore so other tests using employee fixture see operator-like flow if needed
        requests.patch(f"{API}/lns/{employee['lns_name']}/role",
                       json={"role": "operator"}, headers=_hdr(), timeout=30)

    def test_auditor_role_forbidden(self, employee):
        r = requests.patch(f"{API}/lns/{employee['lns_name']}/role",
                           json={"role": "vendor"}, headers=_hdr("auditor"), timeout=30)
        assert r.status_code == 403

    def test_vendor_role_forbidden(self, employee):
        r = requests.patch(f"{API}/lns/{employee['lns_name']}/role",
                           json={"role": "vendor"}, headers=_hdr("vendor"), timeout=30)
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /api/lns/{lns}
# ---------------------------------------------------------------------------
class TestDeleteLns:
    def test_delete_removes_and_notarises(self, tenant):
        # Register a throwaway employee
        lns = f"todelete{uuid.uuid4().hex[:5]}.{tenant['domain']}"
        r = requests.post(f"{API}/lns/register",
                          json={"lns_name": lns, "department": "ops",
                                "role": "operator", "tenant_id": tenant["tenant_id"]},
                          headers=_hdr(), timeout=60)
        assert r.status_code == 200, r.text

        # employees_count before delete
        t_before = next(t for t in requests.get(f"{API}/tenants", headers=_hdr(), timeout=30).json()
                        if t["tenant_id"] == tenant["tenant_id"])
        count_before = t_before["employees_count"]

        # delete
        d = requests.delete(f"{API}/lns/{lns}", headers=_hdr(), timeout=60)
        assert d.status_code == 200, d.text
        body = d.json()
        assert body["ok"] is True
        assert body["tx_id"].startswith("tx-")
        assert isinstance(body["block_index"], int) and body["block_index"] > 0

        # Not in /api/lns list
        all_lns = requests.get(f"{API}/lns", headers=_hdr(), timeout=30).json()
        assert not any(e["lns_name"] == lns for e in all_lns), "lns still in /api/lns"

        # Not in tenant employees
        emps = requests.get(f"{API}/tenants/{tenant['tenant_id']}/employees",
                            headers=_hdr(), timeout=30).json()
        assert not any(e["lns_name"] == lns for e in emps), "lns still in employees"

        # employees_count decremented
        t_after = next(t for t in requests.get(f"{API}/tenants", headers=_hdr(), timeout=30).json()
                       if t["tenant_id"] == tenant["tenant_id"])
        assert t_after["employees_count"] == count_before - 1, \
            f"counter not decremented: before={count_before} after={t_after['employees_count']}"

        # Block was finalised through QBFT (≥3 votes)
        b = requests.get(f"{API}/ledger/blocks/{body['block_index']}", headers=_hdr(), timeout=30)
        if b.status_code == 200:
            votes = (b.json().get("qbft_votes") or [])
            assert len(votes) >= 3, f"QBFT votes={len(votes)}"

        # IdentityDelete tx exists with matching tx_id
        tx = requests.get(f"{API}/ledger/verify/{body['tx_id']}", headers=_hdr(), timeout=30)
        assert tx.status_code == 200 and tx.json().get("ok") is True

    def test_delete_unknown_returns_404(self):
        r = requests.delete(f"{API}/lns/nobody.nonexistent.id", headers=_hdr(), timeout=30)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Regression — prior endpoints still healthy
# ---------------------------------------------------------------------------
class TestRegression:
    @pytest.mark.parametrize("path", [
        "/ledger/stats", "/qbft/status", "/mixnet/status", "/pqc/info", "/tenants",
    ])
    def test_endpoint_ok(self, path):
        r = requests.get(f"{API}{path}", headers=_hdr(), timeout=30)
        assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"

    def test_zk_prove(self):
        # Some tests previously used /rln/zk/prove — keep regression light
        r = requests.post(f"{API}/rln/zk/prove",
                          json={"lns": "ceo.acme.azienda.id", "epoch": 1, "message": "hi"},
                          headers=_hdr(), timeout=30)
        # Either ok or 404 if lns missing — accept 200/404, fail on 5xx
        assert r.status_code < 500, r.text
