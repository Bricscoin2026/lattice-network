"""
Iteration 23 — Production-readiness blockers test suite.
Covers:
  - /api/admin/secrets/* (static envelope mode, Argon2id)
  - /api/admin/license/* (ML-DSA-65 signed)
  - /api/admin/health/overview (single-pane aggregate)
  - Core flow regressions (qbft, mixnet, ledger, certify, config)
  - Idempotent migration #3 (no-wipe-on-upgrade)
"""

import os
import time
import json
import secrets as _secrets
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://admin-console-59.preview.emergentagent.com").rstrip("/")
HDR = {"X-Lattice-Role": "sovereign", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update(HDR)
    return s


# ───────────────────────── secrets/* ─────────────────────────
class TestSecrets:
    def test_secrets_status_static_unlocked(self, api):
        r = api.get(f"{BASE_URL}/api/admin/secrets/status")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["mode"] == "static", d
        assert d["unlocked"] is True, d
        assert d.get("static_key_loaded") is True, d
        assert d["kdf"] == "argon2id", d
        kp = d.get("kdf_params") or {}
        for k in ("time_cost", "memory_cost_kb", "parallelism"):
            assert k in kp, f"missing kdf_params.{k}: {kp}"
            assert isinstance(kp[k], int) and kp[k] > 0

    def test_secrets_init_conflict_when_static_loaded(self, api):
        # When static key is loaded, /init MUST refuse with 409
        r = api.post(
            f"{BASE_URL}/api/admin/secrets/init",
            json={"passphrase": "TEST_should_be_refused_AAA12345!", "confirm": "TEST_should_be_refused_AAA12345!"},
        )
        assert r.status_code == 409, f"expected 409 got {r.status_code}: {r.text}"

    def test_secrets_unlock_noop_when_static_loaded(self, api):
        # passphrase has min_length=12; static mode ignores it but the payload must validate
        r = api.post(f"{BASE_URL}/api/admin/secrets/unlock", json={"passphrase": "irrelevant_static_noop_12+"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True or d.get("unlocked") is True, d
        # Per spec: returns ok + note
        assert "note" in d, f"unlock no-op should include 'note': {d}"


# ───────────────────────── license/* ─────────────────────────
class TestLicense:
    def test_license_status_enterprise_signed(self, api):
        r = api.get(f"{BASE_URL}/api/admin/license/status")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["edition"] == "enterprise", d
        assert d["signed"] is True, d
        assert d.get("vendor_pubkey_fpr"), d
        assert d.get("days_remaining", 0) > 500, d
        assert d.get("tenant_name") == "Lattice Demo Customer", d

    def test_license_reload_returns_same(self, api):
        before = api.get(f"{BASE_URL}/api/admin/license/status").json()
        r = api.post(f"{BASE_URL}/api/admin/license/reload")
        assert r.status_code == 200, r.text
        after = r.json()
        # license_id and fingerprint should match exactly
        # accept either {status:{...}} envelope or direct
        if "license" in after or "status" in after:
            after = after.get("license") or after.get("status") or after
        assert after.get("license_id") == before.get("license_id"), (before, after)
        assert after.get("vendor_pubkey_fpr") == before.get("vendor_pubkey_fpr"), (before, after)
        # Re-fetch status and confirm identical
        again = api.get(f"{BASE_URL}/api/admin/license/status").json()
        assert again["license_id"] == before["license_id"]
        assert again["signed"] is True

    def test_license_install_invalid_signature_rejected(self, api):
        # Build a syntactically valid-ish license JSON with a random ML-DSA-style signature
        # NOTE: ML-DSA-65 signature is 3309 bytes (variable up to ~3309). We send a deliberately
        # wrong-size random hex string — verification MUST reject it.
        bogus = {
            "license_id": "TEST_lic_invalid_sig",
            "edition": "enterprise",
            "tenant_name": "TEST Fake Customer",
            "max_tenants": 1,
            "max_users": 1,
            "features": ["pulse"],
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_until": "2027-01-01T00:00:00Z",
            "signature_hex": _secrets.token_hex(3309),  # ML-DSA-65 sig size
            "vendor_pubkey_fpr": "DEADBEEFDEADBEEF",
        }
        r = api.post(f"{BASE_URL}/api/admin/license/install", json={"license": bogus})
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"
        body = r.text.lower()
        assert "signature" in body or "rejected" in body or "verification" in body, r.text

    def test_license_install_invalid_signature_rejected_short_sig(self, api):
        # Same test but with deliberately wrong-size signature (definitely invalid)
        bogus = {
            "license_id": "TEST_lic_short_sig",
            "edition": "enterprise",
            "tenant_name": "TEST Bad Sig",
            "max_tenants": 1,
            "max_users": 1,
            "features": ["pulse"],
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_until": "2027-01-01T00:00:00Z",
            "signature_hex": "00" * 100,  # way too short for ML-DSA-65
            "vendor_pubkey_fpr": "DEADBEEFDEADBEEF",
        }
        r = api.post(f"{BASE_URL}/api/admin/license/install", json={"license": bogus})
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"


# ───────────────────────── health/overview ─────────────────────────
class TestHealthOverview:
    def test_health_overview_aggregate(self, api):
        r = api.get(f"{BASE_URL}/api/admin/health/overview")
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("timestamp", "secrets", "license", "compliance_mode",
                  "chain_id", "validators", "mixnet", "chain", "disk", "alerts"):
            assert k in d, f"missing top-level key: {k}"

        # validators
        v = d["validators"]
        assert v["total"] == 4, v
        assert v["online"] == 4, v
        assert v["quorum_reached"] is True, v
        assert isinstance(v.get("nodes"), list) and len(v["nodes"]) == 4, v

        # mixnet: compliance mode → enabled False, total 3
        m = d["mixnet"]
        assert m["enabled"] is False, m
        assert m["total"] == 3, m

        # chain
        assert d["chain"]["blocks"] >= 1, d["chain"]

        # disk
        assert "used_pct" in d["disk"], d["disk"]
        assert isinstance(d["disk"]["used_pct"], (int, float))

        # alerts
        assert isinstance(d["alerts"], list)

    def test_health_overview_public_no_auth(self):
        # Endpoint must work without the sovereign header (public by design)
        r = requests.get(f"{BASE_URL}/api/admin/health/overview")
        assert r.status_code == 200, r.text


# ───────────────────────── core regressions ─────────────────────────
class TestCoreRegressions:
    @pytest.mark.parametrize("path", [
        "/api/qbft/status",
        "/api/mixnet/status",
        "/api/ledger/stats",
        "/api/certify/stats",
        "/api/config/runtime",
    ])
    def test_core_endpoint_200(self, api, path):
        r = api.get(f"{BASE_URL}{path}")
        assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:200]}"
        # must be JSON
        d = r.json()
        assert isinstance(d, (dict, list))


# ───────────────────────── idempotent migration #3 ─────────────────────────
class TestIdempotentMigration:
    def test_block_count_stable_across_restart(self, api):
        """Capture block count, restart backend, ensure count >= before (no wipe)."""
        before_stats = api.get(f"{BASE_URL}/api/ledger/stats").json()
        before_blocks = before_stats.get("total_blocks") or before_stats.get("blocks") or 0
        before_txs = before_stats.get("total_transactions") or before_stats.get("transactions") or 0

        # Restart backend via supervisor (local action)
        rc = os.system("sudo supervisorctl restart backend >/dev/null 2>&1")
        assert rc == 0, "supervisorctl restart failed"

        # Wait for it to come back
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                rr = requests.get(f"{BASE_URL}/api/qbft/status", timeout=5)
                if rr.status_code == 200:
                    break
            except Exception:
                pass
            time.sleep(2)
        else:
            pytest.fail("backend did not recover after restart")

        # Re-read
        after_stats = api.get(f"{BASE_URL}/api/ledger/stats").json()
        after_blocks = after_stats.get("total_blocks") or after_stats.get("blocks") or 0
        after_txs = after_stats.get("total_transactions") or after_stats.get("transactions") or 0

        # Must NOT have been wiped: counts should be >= what we had before
        assert after_blocks >= before_blocks, f"blocks dropped: {before_blocks} -> {after_blocks}"
        assert after_txs >= before_txs, f"txs dropped: {before_txs} -> {after_txs}"

    def test_skip_log_on_restart(self):
        """Backend log should contain idempotent-migration skip line (best-effort)."""
        import subprocess
        out = subprocess.run(
            ["bash", "-lc", "tail -n 400 /var/log/supervisor/backend.*.log 2>/dev/null"],
            capture_output=True, text=True, timeout=10,
        ).stdout.lower()
        # accept variants
        keywords = ["already initialised", "already initialized", "skipping"]
        assert any(k in out for k in keywords), \
            f"no idempotent-migration skip log line found. Tail snippet: {out[-600:]}"
