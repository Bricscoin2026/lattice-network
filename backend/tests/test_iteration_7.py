"""Iteration_7: plaintext visibility, multi-recipient certify, endpoints."""
import os, uuid, pytest, requests
BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    from pathlib import Path
    for line in (Path(__file__).resolve().parents[2] / "frontend" / ".env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE = line.split("=", 1)[1].strip().rstrip("/")
API = BASE + "/api"


@pytest.fixture(scope="module")
def lns():
    r = requests.get(f"{API}/lns/active", timeout=20)
    assert r.status_code == 200
    return [x["lns_name"] for x in r.json()]


class TestPulsePlaintext:
    def test_send_and_get_plaintext(self, lns):
        unique = uuid.uuid4().hex[:8]
        pt = f"TEST_iter7 plaintext visible {unique}"
        r = requests.post(f"{API}/pulse/send",
                          json={"from_lns": lns[20], "to_lns": lns[21], "plaintext": pt}, timeout=15)
        assert r.status_code in (200, 429), r.text
        if r.status_code == 429:
            pytest.skip("RLN saturated")
        j = r.json()
        conv_id = j["conv_id"]
        m = requests.get(f"{API}/pulse/messages", params={"conv_id": conv_id}, timeout=10)
        assert m.status_code == 200
        msgs = m.json()
        found = [x for x in msgs if x.get("plaintext") == pt]
        assert len(found) >= 1, "plaintext field must be present and equal to sent text"
        assert "ciphertext_hex" in found[0]


class TestCertifyMulti:
    def test_multi_fanout(self, lns):
        u = uuid.uuid4().hex[:8]
        payload = {"sender_lns": lns[0], "recipients_lns": lns[1:4], "cc_lns": [lns[4]],
                   "subject": f"TEST_iter7 multi {u}", "body": f"body {u}", "classification": "INTERNAL"}
        r = requests.post(f"{API}/certify/send", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["fanout"] == 4
        # verify rows
        rec = requests.get(f"{API}/certify/recent", params={"limit": 50}, timeout=10).json()
        matching = [m for m in rec if m["doc_hash"] == j["doc_hash"]]
        assert len(matching) == 4
        tx_ids = {m.get("tx_id") for m in matching}
        assert tx_ids == {j["tx_id"]}


class TestEndpoints:
    @pytest.mark.parametrize("path", [
        "/ledger/stats", "/qbft/nodes", "/lns/active", "/mixnet/topology",
        "/vendor/stats", "/vendor/tenants",
    ])
    def test_get_ok(self, path):
        r = requests.get(f"{API}{path}", timeout=15)
        assert r.status_code == 200, f"{path} -> {r.status_code}"

    def test_lns_check(self, lns):
        r = requests.get(f"{API}/lns/check", params={"lns_name": lns[0]}, timeout=10)
        assert r.json()["available"] is False
        assert r.json()["reason"] == "already_taken"

    def test_rln_quota(self, lns):
        r = requests.get(f"{API}/rln/quota", params={"lns": lns[0]}, timeout=10)
        assert r.status_code == 200
        assert "epoch" in r.json()
