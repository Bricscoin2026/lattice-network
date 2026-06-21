"""Tests for Public Block Explorer endpoints (Iter_41).

All endpoints are public (no auth). Backend URL is taken from
REACT_APP_BACKEND_URL (frontend/.env) — that is the public ingress.
"""
import os
import re
import pytest
import requests

# Use the public external URL just like the frontend does.
BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://admin-console-59.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def stats():
    r = requests.get(f"{API}/explorer/stats", timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


# --- /stats ---------------------------------------------------------------
class TestExplorerStats:
    def test_stats_shape(self, stats):
        for key in (
            "chain_id", "algorithm", "block_height", "total_transactions",
            "total_lns", "total_mails", "total_pulses", "recent_blocks",
            "recent_transactions",
        ):
            assert key in stats, f"missing key {key}"
        assert stats["algorithm"] == "ML-DSA-65"
        assert isinstance(stats["block_height"], int) and stats["block_height"] > 0
        assert isinstance(stats["recent_blocks"], list)
        assert isinstance(stats["recent_transactions"], list)
        assert len(stats["recent_blocks"]) <= 10
        assert len(stats["recent_transactions"]) <= 10

    def test_stats_no_mongo_id(self, stats):
        for b in stats["recent_blocks"]:
            assert "_id" not in b
        for t in stats["recent_transactions"]:
            assert "_id" not in t


# --- /tx/{id} -------------------------------------------------------------
class TestExplorerTx:
    def test_tx_verified_real_mldsa(self, stats):
        # find a tx signed with ML-DSA-65 to validate the real verifier
        real = next(
            (t for t in stats["recent_transactions"] if t.get("signed_with") == "ML-DSA-65"),
            None,
        )
        assert real is not None, "no ML-DSA-65 signed tx in recent set"
        r = requests.get(f"{API}/explorer/tx/{real['tx_id']}", timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["transaction"]["tx_id"] == real["tx_id"]
        # ML-DSA-65 signed → verified must be a real bool
        assert body["verified"] in (True, False)
        assert isinstance(body["verify_detail"], str) and body["verify_detail"]
        assert body["algorithm"] == "ML-DSA-65"

    def test_tx_not_found(self):
        r = requests.get(f"{API}/explorer/tx/tx-does-not-exist", timeout=15)
        assert r.status_code == 404


# --- /block/{idx} ---------------------------------------------------------
class TestExplorerBlock:
    def test_block_detail(self, stats):
        idx = stats["block_height"]
        r = requests.get(f"{API}/explorer/block/{idx}", timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["block"]["index"] == idx
        assert "transactions" in body and isinstance(body["transactions"], list)
        # latest block has no next
        assert body["next"] in (None,)
        if idx > 0:
            assert body["prev"] and body["prev"]["index"] == idx - 1

    def test_block_not_found(self):
        r = requests.get(f"{API}/explorer/block/99999999", timeout=15)
        assert r.status_code == 404


# --- /lns/{name} ----------------------------------------------------------
class TestExplorerLns:
    def test_lns_detail(self, stats):
        signer = next(
            (t.get("signer_entity") for t in stats["recent_transactions"] if t.get("signer_entity")),
            None,
        )
        assert signer, "no signer_entity in recent txs"
        r = requests.get(f"{API}/explorer/lns/{signer}", timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["lns"]["lns_name"] == signer
        assert "recent_transactions" in body and isinstance(body["recent_transactions"], list)
        assert len(body["recent_transactions"]) <= 20

    def test_lns_not_found(self):
        r = requests.get(f"{API}/explorer/lns/no.such.identity.lns", timeout=15)
        assert r.status_code == 404


# --- /search --------------------------------------------------------------
class TestExplorerSearch:
    def test_search_block_number(self, stats):
        r = requests.get(f"{API}/explorer/search", params={"q": str(stats["block_height"])}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["type"] == "block"

    def test_search_tx_prefix(self, stats):
        tx_id = stats["recent_transactions"][0]["tx_id"]
        r = requests.get(f"{API}/explorer/search", params={"q": tx_id}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["type"] == "transaction"

    def test_search_lns(self, stats):
        signer = next(
            (t.get("signer_entity") for t in stats["recent_transactions"] if t.get("signer_entity") and "." in t["signer_entity"]),
            None,
        )
        if not signer:
            pytest.skip("no LNS-style signer present")
        r = requests.get(f"{API}/explorer/search", params={"q": signer}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["type"] == "lns"

    def test_search_doc_hash(self, stats):
        # try to find a tx with a doc_hash
        # only NotarySeal / cert kinds usually carry one. Probe a few recent.
        tx_with_hash = None
        for t in stats["recent_transactions"]:
            full = requests.get(f"{API}/explorer/tx/{t['tx_id']}", timeout=15).json()
            if full["transaction"].get("doc_hash"):
                tx_with_hash = full["transaction"]
                break
        if not tx_with_hash:
            pytest.skip("no doc_hash in recent txs")
        h = tx_with_hash["doc_hash"]
        assert re.fullmatch(r"[0-9a-fA-F]{32,256}", h)
        r = requests.get(f"{API}/explorer/search", params={"q": h}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["type"] in ("transaction", "mail")

    def test_search_unknown(self):
        r = requests.get(f"{API}/explorer/search", params={"q": "zzzznomatch12345"}, timeout=15)
        assert r.status_code == 404

    def test_search_too_short(self):
        r = requests.get(f"{API}/explorer/search", params={"q": "ab"}, timeout=15)
        assert r.status_code == 422  # validation


# --- No auth required (smoke) --------------------------------------------
class TestNoAuth:
    def test_all_endpoints_public(self, stats):
        # send a random Authorization header — should still be 200
        h = {"Authorization": "Bearer garbage", "X-Lattice-Role": "anonymous"}
        for path in ("/explorer/stats",
                     f"/explorer/block/{stats['block_height']}"):
            r = requests.get(f"{API}{path}", headers=h, timeout=15)
            assert r.status_code == 200, f"{path} => {r.status_code}"
