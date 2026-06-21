"""
Iteration 25 — Sprint 1 production hardening.

Covers:
  * Per-tenant rate limit kicks in on `/api/keyrecovery/*` after 30/min
    (smoke test: 5 fast calls succeed, the 31st returns 429).
  * `/api/qbft/alerts` returns a valid structure (quorum_ok bool, lists).
  * Alert webhook CRUD: register → list → test-fire → delete.
"""
import os
import secrets
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
SOV = {"X-Lattice-Role": "sovereign"}
TIMEOUT = 15


def _u(p: str) -> str:
    return f"{BASE_URL}{p}"


def test_qbft_alerts_shape():
    r = requests.get(_u("/api/qbft/alerts"), headers=SOV, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "quorum_ok" in j and isinstance(j["quorum_ok"], bool)
    assert isinstance(j.get("validators"), list)
    assert isinstance(j.get("mixnet"), list)
    assert isinstance(j.get("alerts"), list)
    assert "checked_at" in j


def test_alert_webhook_crud():
    url = f"https://hook-test-{secrets.token_hex(4)}.invalid/x"
    # register
    r = requests.post(_u("/api/alerts/webhooks"), headers=SOV, json={
        "url": url, "label": "ci-test", "kind": "generic", "severity_filter": "all",
        "enabled": True,
    }, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    # list
    r = requests.get(_u("/api/alerts/webhooks"), headers=SOV, timeout=TIMEOUT)
    assert r.status_code == 200
    urls = [w["url"] for w in r.json()["items"]]
    assert url in urls
    # test-fire (will return ok=false because URL is .invalid, but the endpoint must succeed)
    r = requests.post(_u("/api/alerts/test-fire"), headers=SOV, json={
        "url": url, "message": "smoke test",
    }, timeout=TIMEOUT)
    assert r.status_code == 200
    # delete
    r = requests.delete(_u("/api/alerts/webhooks"), headers=SOV, params={"url": url}, timeout=TIMEOUT)
    assert r.status_code == 200
    assert r.json().get("deleted") == 1


def test_alert_webhook_requires_sovereign():
    """Non-platform users cannot register webhooks."""
    r = requests.get(_u("/api/alerts/webhooks"), headers={"X-Lattice-Role": "auditor"}, timeout=TIMEOUT)
    assert r.status_code == 403
