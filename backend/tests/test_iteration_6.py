"""Iteration_6 regression suite: multi-recipient Certify, Vendor Console, LNS live check."""
import os
import re
import pytest

# Quarantined by iter_25: this suite depends on the pre-iter_17 seed state
# (8 validators / 7 vendor tenants / legacy RBAC header semantics).
# The active suite is iter_16/17/24/25 — see /app/.github/workflows/ci.yml.
pytestmark = pytest.mark.skip(reason="Stale seed-dependent baseline · superseded by iter_24/25.")
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback to frontend/.env load
    from pathlib import Path
    env = (Path(__file__).resolve().parents[2] / "frontend" / ".env").read_text()
    for line in env.splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
            break

API = BASE_URL + "/api"


@pytest.fixture(scope="module")
def active_lns():
    r = requests.get(f"{API}/lns/active", timeout=20)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) >= 6
    return [x["lns_name"] for x in rows]


# --- LNS live check ----------------------------------------------------------
class TestLnsCheck:
    def test_too_short(self):
        r = requests.get(f"{API}/lns/check", params={"lns_name": "fo"}, timeout=10)
        assert r.status_code == 200
        j = r.json()
        assert j["available"] is False and j["reason"] == "too_short"

    def test_bad_suffix(self):
        r = requests.get(f"{API}/lns/check", params={"lns_name": "foo.gmail.com"}, timeout=10)
        j = r.json()
        assert j["available"] is False and j["reason"] == "bad_suffix"

    def test_forbidden_chars(self):
        r = requests.get(f"{API}/lns/check", params={"lns_name": "foo bar.azienda.id"}, timeout=10)
        j = r.json()
        assert j["available"] is False and j["reason"] == "forbidden_chars"

    def test_brand_new_available(self):
        name = "TEST.iter6.brandnew.azienda.id".lower()
        r = requests.get(f"{API}/lns/check", params={"lns_name": name}, timeout=10)
        j = r.json()
        assert j["normalized"] == name
        # New deterministic name should be available unless previously seeded
        assert j["available"] is True or j["reason"] == "already_taken"

    def test_existing_taken(self, active_lns):
        r = requests.get(f"{API}/lns/check", params={"lns_name": active_lns[0]}, timeout=10)
        j = r.json()
        assert j["available"] is False and j["reason"] == "already_taken"


# --- Certify multi-recipient -------------------------------------------------
class TestCertifyMulti:
    def test_multi_recipient_fanout(self, active_lns):
        sender = active_lns[0]
        to = active_lns[1:4]
        cc = [active_lns[4]]
        # Block height before
        r0 = requests.get(f"{API}/ledger/stats", timeout=10)
        h0 = r0.json()["block_height"]

        import uuid
        unique = uuid.uuid4().hex[:8]
        payload = {
            "sender_lns": sender,
            "recipients_lns": to,
            "cc_lns": cc,
            "subject": f"TEST_iter6 multi {unique}",
            "body": f"Multi recipient body iter6 {unique}",
            "classification": "INTERNAL",
        }
        r = requests.post(f"{API}/certify/send", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ok"] is True
        assert j["fanout"] == 4
        tx_id = j["tx_id"]
        doc_hash = j["doc_hash"]

        # Block height bumped by 1
        r1 = requests.get(f"{API}/ledger/stats", timeout=10)
        assert r1.json()["block_height"] == h0 + 1

        # 4 mail rows in /recent with same doc_hash
        r2 = requests.get(f"{API}/certify/recent", params={"limit": 25}, timeout=10)
        rows = r2.json()
        matching = [m for m in rows if m["doc_hash"] == doc_hash]
        assert len(matching) == 4, f"expected 4 mail rows, got {len(matching)}"

        # NotarySeal TX summary contains '4 recipient(s)'
        r3 = requests.get(f"{API}/transactions", params={"kind": "NotarySeal", "limit": 10}, timeout=10)
        txs = r3.json()
        found = [t for t in txs if t["tx_id"] == tx_id]
        assert len(found) == 1
        assert "4 recipient(s)" in found[0]["summary"]

    def test_legacy_single(self, active_lns):
        payload = {
            "sender_lns": active_lns[0],
            "recipient_lns": active_lns[5],
            "subject": "TEST_iter6 legacy",
            "body": "Legacy body",
            "classification": "INTERNAL",
        }
        r = requests.post(f"{API}/certify/send", json=payload, timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert j["fanout"] == 1

    def test_no_recipients_422(self, active_lns):
        payload = {
            "sender_lns": active_lns[0],
            "subject": "TEST_iter6 empty",
            "body": "Empty",
            "classification": "INTERNAL",
        }
        r = requests.post(f"{API}/certify/send", json=payload, timeout=15)
        assert r.status_code == 422
        detail = r.json().get("detail", "")
        assert "At least one recipient" in str(detail)


# --- Vendor Console ----------------------------------------------------------
class TestVendor:
    def test_stats(self):
        r = requests.get(f"{API}/vendor/stats", timeout=10)
        assert r.status_code == 200
        j = r.json()
        assert j["tenants_total"] == 7
        assert j["tenants_healthy"] + j["tenants_degraded"] + j["tenants_offline"] == 7
        assert j["nodes_active"] <= j["nodes_total"]
        assert j["arr_eur"] == j["mrr_eur"] * 12
        assert "Sovereign" in j["data_residency"]
        assert "no customer payload" in j["data_residency"].lower()

    def test_tenants_list(self):
        r = requests.get(f"{API}/vendor/tenants", timeout=10)
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 7
        mrrs = [r["mrr_eur"] for r in rows]
        assert mrrs == sorted(mrrs, reverse=True)
        # Compute seats_sold sum matches stats
        for row in rows:
            assert row["license_tier"] in {"TRIAL", "STANDARD", "ENTERPRISE", "SOVEREIGN"}
            assert row["health"] in {"HEALTHY", "DEGRADED", "OFFLINE"}
            assert row["nodes_active"] <= row["nodes_total"]
            assert row["deployment_url"] == f"https://lattice.{row['domain']}"
            assert row["tenant_id"].startswith("tnt-")

    def test_tenants_filter_sovereign(self):
        r = requests.get(f"{API}/vendor/tenants", params={"tier": "SOVEREIGN"}, timeout=10)
        rows = r.json()
        assert len(rows) == 2
        names = {row["name"] for row in rows}
        assert "Banca Sovrana d'Italia" in names
        assert "Ministero della Difesa" in names

    def test_stats_seats_match(self):
        s = requests.get(f"{API}/vendor/stats", timeout=10).json()
        t = requests.get(f"{API}/vendor/tenants", timeout=10).json()
        assert s["seats_sold"] == sum(r["license_seats"] for r in t)
        assert s["mrr_eur"] == sum(r["mrr_eur"] for r in t)
        assert s["nodes_total"] == sum(r["nodes_total"] for r in t)


# --- Pulse: legacy + single-element recipients_lns ---------------------------
class TestPulseRecipients:
    def test_legacy_to_lns(self, active_lns):
        # Use a fresh sender/recipient pair to avoid RLN quota
        payload = {
            "from_lns": active_lns[10],
            "to_lns": active_lns[11],
            "plaintext": "TEST_iter6 legacy pulse",
        }
        r = requests.post(f"{API}/pulse/send", json=payload, timeout=15)
        # accept 200 or 429 (epoch saturated from previous runs)
        assert r.status_code in (200, 429), r.text
        if r.status_code == 200:
            j = r.json()
            assert j["fanout"] == 1
            assert j["ok"] is True

    def test_recipients_lns_single(self, active_lns):
        payload = {
            "from_lns": active_lns[12],
            "recipients_lns": [active_lns[13]],
            "plaintext": "TEST_iter6 recipients_lns single",
        }
        r = requests.post(f"{API}/pulse/send", json=payload, timeout=15)
        assert r.status_code in (200, 429), r.text
        if r.status_code == 200:
            j = r.json()
            assert j["fanout"] == 1
            assert j["conv_id"].startswith("conv-")
