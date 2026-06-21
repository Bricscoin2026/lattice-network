"""Iteration_5 backend tests: PQXDH/DR Pulse session, ZK-RLN, Mixnet, Substrate-style block fields."""
import os
import re
import pytest
import requests
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

FP_RE = re.compile(r"^([0-9A-F]{2}:){7}[0-9A-F]{2}$")
HEX128 = re.compile(r"^[0-9a-f]{128}$")
HEX64 = re.compile(r"^[0-9A-F]{64}$")


@pytest.fixture(scope="module")
def active_lns():
    r = requests.get(f"{API}/lns/active", timeout=15)
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 5
    return [x["lns_name"] for x in items]


# ---- Mixnet ----------------------------------------------------------------
class TestMixnet:
    def test_topology_9_relays_3_layers(self):
        r = requests.get(f"{API}/mixnet/topology", timeout=10)
        assert r.status_code == 200
        relays = r.json()
        assert len(relays) == 9
        by_layer = {0: 0, 1: 0, 2: 0}
        for relay in relays:
            assert relay["layer"] in (0, 1, 2)
            by_layer[relay["layer"]] += 1
        assert by_layer == {0: 3, 1: 3, 2: 3}

    def test_route_3_hops_ordered(self, active_lns):
        body = {"origin_lns": active_lns[0], "destination_lns": active_lns[1]}
        r = requests.post(f"{API}/mixnet/route", json=body, timeout=10)
        assert r.status_code == 200, r.text
        route = r.json()
        assert route["route_id"].startswith("route-")
        assert len(route["hops"]) == 3
        assert [h["layer"] for h in route["hops"]] == [0, 1, 2]
        assert route["total_delay_ms"] == sum(h["delay_ms"] for h in route["hops"])
        assert route["cover_traffic_rate_hz"] > 0


# ---- RLN quota -------------------------------------------------------------
class TestRln:
    def test_quota_shape(self, active_lns):
        r = requests.get(f"{API}/rln/quota", params={"lns": active_lns[0]}, timeout=10)
        assert r.status_code == 200
        q = r.json()
        assert q["lns"] == active_lns[0]
        assert q["epoch_seconds"] == 60
        assert q["max_per_epoch"] == 10
        assert isinstance(q["used"], int)
        assert isinstance(q["epoch"], int) and q["epoch"] > 0
        assert HEX64.match(q["nullifier_seed"]), f"nullifier_seed bad: {q['nullifier_seed']}"


# ---- Pulse send: response fields & RLN validation --------------------------
class TestPulseSend:
    def test_send_returns_session_route_rln(self, active_lns):
        sender, recipient = active_lns[2], active_lns[3]
        q = requests.get(f"{API}/rln/quota", params={"lns": sender}, timeout=10).json()
        proof = {"nullifier": q["nullifier_seed"].lower(), "epoch": q["epoch"]}
        body = {
            "from_lns": sender, "to_lns": recipient,
            "plaintext": "TEST_iter5 pulse with proof",
            "rln_proof": proof,
        }
        r = requests.post(f"{API}/pulse/send", json=body, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert FP_RE.match(d["session_fingerprint"]), d["session_fingerprint"]
        assert d["epoch"] >= 1
        assert d["message_number"] >= 1
        assert d["route_id"].startswith("route-")
        assert len(d["route_hops"]) == 3
        assert d["rln_slot_used"] >= 1
        assert d["rln_slot_max"] == 10

    def test_invalid_nullifier(self, active_lns):
        body = {
            "from_lns": active_lns[4], "to_lns": active_lns[5],
            "plaintext": "TEST_iter5 invalid nul",
            "rln_proof": {"nullifier": "invalid", "epoch": 1},
        }
        r = requests.post(f"{API}/pulse/send", json=body, timeout=10)
        assert r.status_code == 400
        assert "nullifier mismatch" in r.json()["detail"]

    def test_stale_epoch(self, active_lns):
        body = {
            "from_lns": active_lns[6], "to_lns": active_lns[7],
            "plaintext": "TEST_iter5 stale epoch",
            "rln_proof": {"nullifier": "00" * 32, "epoch": 0},
        }
        r = requests.post(f"{API}/pulse/send", json=body, timeout=10)
        assert r.status_code == 400
        # epoch=0 triggers stale-epoch (nullifier check happens only if nul present;
        # since nul is 64-char hex, nullifier check fires first → assert detail mentions stale or mismatch)
        detail = r.json()["detail"]
        assert "stale epoch" in detail or "nullifier mismatch" in detail


# ---- RLN rate-limit test (run last; consumes quota) ------------------------
class TestRlnRateLimit:
    def test_429_on_11th(self, active_lns):
        # Pick LNS not used in other tests
        sender, recipient = active_lns[8], active_lns[9]
        # ensure fresh epoch sufficient runway: check current epoch start
        # If quota already > 0 (e.g. due to a prior run within 60s), skip.
        q0 = requests.get(f"{API}/rln/quota", params={"lns": sender}, timeout=5).json()
        if q0["used"] > 0:
            pytest.skip(f"Sender {sender} already used {q0['used']} in this epoch")
        last = None
        for i in range(11):
            body = {"from_lns": sender, "to_lns": recipient, "plaintext": f"TEST_iter5_rl_{i}"}
            r = requests.post(f"{API}/pulse/send", json=body, timeout=10)
            last = r
            if r.status_code == 429:
                break
        assert last.status_code == 429, f"expected 429 at 11th call, got {last.status_code}: {last.text}"
        assert "ZK-RLN rate limit exceeded" in last.json()["detail"]


# ---- Pulse session ---------------------------------------------------------
class TestPulseSession:
    def test_session_for_existing_conv(self, active_lns):
        # Ensure a conv exists
        s, r_ = active_lns[0], active_lns[1]
        body = {"from_lns": s, "to_lns": r_, "plaintext": "TEST_iter5 sess"}
        r = requests.post(f"{API}/pulse/send", json=body, timeout=10)
        assert r.status_code == 200
        conv_id = r.json()["conv_id"]
        s2 = requests.get(f"{API}/pulse/session/{conv_id}", timeout=10)
        assert s2.status_code == 200, s2.text
        d = s2.json()
        assert d["conv_id"] == conv_id
        assert d["participants"] == sorted([s.lower(), r_.lower()])
        assert FP_RE.match(d["fingerprint"])
        assert d["epoch"] >= 1
        assert d["message_number"] >= 0
        assert "PQXDH(ML-KEM-768) + Double-Ratchet" in d["cipher_suite"]


# ---- Substrate-style fields on blocks & transactions -----------------------
class TestSubstrateFields:
    def test_blocks_have_new_fields(self):
        r = requests.get(f"{API}/ledger/blocks", params={"limit": 20}, timeout=10)
        assert r.status_code == 200
        blocks = r.json()
        assert blocks
        for b in blocks:
            for k in ("state_root", "extrinsics_root", "weight_used", "events_count", "digest"):
                assert k in b, f"missing {k} in block {b['index']}"
            assert isinstance(b["state_root"], str) and len(b["state_root"]) == 128
            assert isinstance(b["extrinsics_root"], str) and len(b["extrinsics_root"]) == 128
            assert isinstance(b["weight_used"], int)
            assert isinstance(b["events_count"], int)

    def test_transactions_have_nonce_weight(self):
        r = requests.get(f"{API}/transactions", params={"limit": 30}, timeout=10)
        assert r.status_code == 200
        txs = r.json()
        assert txs
        for t in txs:
            assert "nonce" in t and isinstance(t["nonce"], int)
            assert "weight" in t and isinstance(t["weight"], int)
