"""Iter 14 backend regression — Transaction.kind Literal includes 'IdentityDelete'.

Goal: after DELETE /api/lns/{lns}, GET /api/transactions and
GET /api/transactions?kind=IdentityDelete must return 200 with the
IdentityDelete tx present (no pydantic ValidationError).
"""
import os
import uuid
import requests
import pytest


def _load_env():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        with open(p) as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ.setdefault(k, v)


_load_env()
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL required"
API = f"{BASE_URL}/api"
H = {"Content-Type": "application/json"}


@pytest.fixture(scope="module")
def deleted_ctx():
    # 1. tenant
    prefix = "iter14" + uuid.uuid4().hex[:5]
    r = requests.post(f"{API}/tenants/register", json={
        "name": "Iter14 SpA", "domain_prefix": prefix,
        "admin_lns_prefix": "ceo", "admin_display_name": "CEO",
    }, headers=H, timeout=60)
    assert r.status_code == 200, r.text
    tenant = r.json()

    # 2. employee
    lns = f"todelete{uuid.uuid4().hex[:5]}.{tenant['domain']}"
    r = requests.post(f"{API}/lns/register", json={
        "lns_name": lns, "department": "ops", "role": "operator",
        "tenant_id": tenant["tenant_id"], "admin": "X",
    }, headers=H, timeout=60)
    assert r.status_code == 200, r.text

    # 3. delete
    d = requests.delete(f"{API}/lns/{lns}", headers=H, timeout=60)
    assert d.status_code == 200, d.text
    body = d.json()
    return {"tenant": tenant, "lns": lns, "tx_id": body["tx_id"],
            "block_index": body["block_index"]}


class TestTransactionsRegression:
    def test_get_transactions_returns_200_with_identity_delete(self, deleted_ctx):
        r = requests.get(f"{API}/transactions", headers=H, timeout=30)
        assert r.status_code == 200, f"GET /api/transactions failed: {r.status_code} {r.text[:300]}"
        txs = r.json()
        assert isinstance(txs, list)
        # IdentityDelete tx must be present and parseable
        matched = [t for t in txs if t.get("tx_id") == deleted_ctx["tx_id"]]
        assert matched, f"IdentityDelete tx {deleted_ctx['tx_id']} not in /api/transactions"
        assert matched[0]["kind"] == "IdentityDelete"

    def test_get_transactions_filter_identity_delete(self, deleted_ctx):
        r = requests.get(f"{API}/transactions", params={"kind": "IdentityDelete"},
                         headers=H, timeout=30)
        assert r.status_code == 200, f"filter failed: {r.status_code} {r.text[:300]}"
        txs = r.json()
        assert isinstance(txs, list) and len(txs) >= 1
        for t in txs:
            assert t["kind"] == "IdentityDelete"
        assert any(t["tx_id"] == deleted_ctx["tx_id"] for t in txs)

    def test_get_block_with_identity_delete_tx(self, deleted_ctx):
        idx = deleted_ctx["block_index"]
        # Block list endpoint returns metadata only (no tx body). We assert
        # the block exists & is serialisable; tx<->block link is verified via
        # /api/ledger/verify/{tx_id}.
        r = requests.get(f"{API}/ledger/blocks", params={"limit": 200},
                         headers=H, timeout=30)
        assert r.status_code == 200
        blocks = r.json()
        matched = [b for b in blocks if b.get("index") == idx]
        assert matched, f"block {idx} not in latest 200 blocks"
        # And the IdentityDelete tx must be verifiable
        v = requests.get(f"{API}/ledger/verify/{deleted_ctx['tx_id']}",
                         headers=H, timeout=30)
        assert v.status_code == 200 and v.json().get("ok") is True

    def test_ledger_blocks_list_ok(self):
        # /api/ledger/recent does not exist in this build; use /api/ledger/blocks
        r = requests.get(f"{API}/ledger/blocks", headers=H, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        data = r.json()
        assert isinstance(data, list) and len(data) > 0
