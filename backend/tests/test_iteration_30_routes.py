"""Iter_30 — quota enforcement + modular routes + OTS auto-upgrade smoke."""
from __future__ import annotations

import json
import os
import pathlib
import re
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


# --- modular routes smoke ----------------------------------------------------


@pytest.mark.parametrize("path", [
    "/api/admin/secrets/status",
    "/api/admin/license/status",
    "/api/admin/health/overview",
    "/api/admin/ots/status",
])
def test_extracted_routes_reachable(path):
    r = requests.get(BASE + path, timeout=10)
    assert r.status_code == 200, f"{path} → {r.status_code} {r.text[:200]}"


def test_backup_snapshot_after_extraction():
    r = requests.get(BASE + "/api/admin/backup/snapshot", headers=SOV, timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert "collections" in body
    assert "version" in body


# --- license quota enforcement ----------------------------------------------


def _issue_license(edition: str, max_tenants: int, max_users: int) -> dict:
    """Helper: issue + install a fresh license, return the active status."""
    import subprocess
    out = BACKEND_DIR / "data" / "_quota_test.lic"
    cmd = [
        "python", "-m", "scripts.issue_license", "sign",
        "--priv", "data/vendor_keypair.json",
        "--edition", edition,
        "--tenant", f"Quota-Test-{edition}",
        "--valid-until", "2027-12-31T23:59:59Z",
        "--max-tenants", str(max_tenants),
        "--max-users", str(max_users),
        "--feature", "pulse", "--feature", "certify",
        "--out", str(out),
    ]
    res = subprocess.run(cmd, cwd=str(BACKEND_DIR), capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    with out.open() as f:
        license_doc = json.load(f)
    r = requests.post(
        BASE + "/api/admin/license/install",
        headers=SOV, json={"license": license_doc}, timeout=10,
    )
    assert r.status_code == 200, r.text
    return r.json()["status"]


def _restore_enterprise_license() -> None:
    """Helper to bring the system back to enterprise after a quota test."""
    import subprocess
    out = BACKEND_DIR / "data" / "license.lic"
    cmd = [
        "python", "-m", "scripts.issue_license", "sign",
        "--priv", "data/vendor_keypair.json",
        "--edition", "enterprise",
        "--tenant", "Lattice Demo Customer",
        "--valid-until", "2027-12-31T23:59:59Z",
        "--max-tenants", "50", "--max-users", "1000",
        "--feature", "pulse", "--feature", "certify", "--feature", "mixnet",
        "--feature", "banking_audit", "--feature", "ots_anchor",
        "--out", str(out),
    ]
    subprocess.run(cmd, cwd=str(BACKEND_DIR), check=True, capture_output=True)
    requests.post(BASE + "/api/admin/license/reload", headers=SOV, timeout=5)


def test_tenant_register_rejected_when_max_tenants_reached():
    """Install a max_tenants=1 license, ensure 2nd tenant gets 402."""
    # Snapshot current tenant count
    current = requests.get(BASE + "/api/admin/health/overview", timeout=10).json()["chain"]["tenants"]

    try:
        # Install a license that just allows the existing count + 1 more
        _issue_license("community", max_tenants=current + 1, max_users=1000)

        # First registration should succeed (we're at current, license allows current+1)
        ts = int(time.time())
        body1 = {
            "name": f"Quota Tenant {ts}",
            "domain_prefix": f"qa{ts}",
            "admin_lns_prefix": "ceo",
            "admin_display_name": "Mario Rossi",
        }
        r1 = requests.post(BASE + "/api/tenants/register", headers=SOV, json=body1, timeout=10)
        assert r1.status_code == 200, r1.text

        # Second registration must be 402
        body2 = {**body1, "domain_prefix": f"qb{ts}"}
        r2 = requests.post(BASE + "/api/tenants/register", headers=SOV, json=body2, timeout=10)
        assert r2.status_code == 402, f"expected 402, got {r2.status_code}: {r2.text}"
        assert "quota" in r2.json()["detail"].lower()
    finally:
        _restore_enterprise_license()


def test_lns_register_rejected_when_max_users_reached():
    """Install a max_users license tight to current_active+1, verify next LNS is 402."""
    overview = requests.get(BASE + "/api/admin/health/overview", timeout=10).json()

    # Need at least one tenant to register an LNS into
    tenants = requests.get(BASE + "/api/admin/health/overview").json()["chain"]["tenants"]
    if tenants == 0:
        pytest.skip("no tenants available — cannot test LNS quota")

    # Use ACTIVE-only count (backend counts {status: {$ne: REVOKED}})
    active_lns = requests.get(BASE + "/api/lns/active", headers=SOV, timeout=10).json()
    current_active = len(active_lns)

    try:
        _issue_license("community", max_tenants=999, max_users=current_active + 1)
        # Find any tenant domain
        # Use /api/lns to identify a domain (admin LNS already exists there)
        lns_list = requests.get(
            BASE + "/api/lns", headers=SOV, timeout=10,
        ).json()
        assert lns_list, "no lns identities to derive a domain from"
        existing_lns = lns_list[0]["lns_name"]      # e.g. ceo.quota1.lns
        # tenant domain = everything after the first "."
        domain = existing_lns.split(".", 1)[1]
        tenant_id = lns_list[0].get("tenant_id")
        ts = int(time.time())

        body_ok = {
            "lns_name": f"quotaok{ts}.{domain}",
            "display_name": "Quota OK",
            "admin": "sysadmin",
            "department": "IT",
            "role": "operator",
            "tenant_id": tenant_id,
        }
        rok = requests.post(BASE + "/api/lns/register", headers=SOV, json=body_ok, timeout=10)
        assert rok.status_code == 200, rok.text

        body_ko = {**body_ok, "lns_name": f"quotako{ts}.{domain}"}
        rko = requests.post(BASE + "/api/lns/register", headers=SOV, json=body_ko, timeout=10)
        assert rko.status_code == 402, f"expected 402, got {rko.status_code}: {rko.text}"
        assert "quota" in rko.json()["detail"].lower()
    finally:
        _restore_enterprise_license()


# --- OTS auto-upgrade loop ---------------------------------------------------


def test_ots_auto_upgrade_loop_running():
    """Smoke: backend log should contain the 'OTS auto-upgrade loop started' line.

    We grep the supervisor log file directly because the loop is fire-and-forget
    and exposes no public status endpoint other than the per-anchor fields.
    """
    log = pathlib.Path("/var/log/supervisor/backend.err.log")
    assert log.exists()
    raw = log.read_text(encoding="utf-8", errors="ignore")
    assert "OTS auto-upgrade loop started" in raw, "loop not started"


def test_ots_upgrade_all_endpoint():
    """POST /api/admin/ots/upgrade-all sweeps all pending anchors."""
    r = requests.post(BASE + "/api/admin/ots/upgrade-all", headers=SOV, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert "pending" in body
    assert "promoted" in body
    assert "results" in body
    assert isinstance(body["results"], list)


def test_lattice_admin_cli_health_smoke(capfd):
    """Exercise the lattice-admin CLI's `health` command via subprocess."""
    import subprocess
    cli = ROOT / "deploy" / "lattice-admin"
    res = subprocess.run(
        ["python", str(cli), "health"],
        capture_output=True, text=True, timeout=30,
        env={**os.environ, "LATTICE_ADMIN_URL": BASE},
    )
    assert res.returncode == 0, res.stderr
    assert "Lattice Network" in res.stdout
    assert "Validators" in res.stdout
    assert "License" in res.stdout
