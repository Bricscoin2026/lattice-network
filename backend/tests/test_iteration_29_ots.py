"""Regression suite for /api/admin/ots/* — proves the routes survive
the modular extraction into routes/ots.py."""
from __future__ import annotations

import os
import pathlib
import re

import pytest
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def _base_url() -> str:
    env_path = ROOT / "frontend" / ".env"
    raw = env_path.read_text(encoding="utf-8")
    m = re.search(r'^REACT_APP_BACKEND_URL\s*=\s*"?([^"\n]+)"?', raw, re.M)
    assert m, "REACT_APP_BACKEND_URL not found"
    return m.group(1).strip()


BASE = _base_url()
SOV = {"X-Lattice-Role": "sovereign"}


@pytest.mark.parametrize("path", [
    "/api/admin/ots/status",
])
def test_ots_status_reachable(path):
    r = requests.get(BASE + path, timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "enabled" in body
    assert "calendars" in body
    assert "anchors" in body
    assert isinstance(body["calendars"], list)


def test_ots_status_lists_existing_anchor():
    r = requests.get(BASE + "/api/admin/ots/status", timeout=10)
    body = r.json()
    # We created at least one anchor during the iter_29 development.
    # If running on a fresh DB this is allowed to be empty.
    assert isinstance(body["anchors"], list)
    for a in body["anchors"]:
        assert a["anchor_id"].startswith("ots-")
        assert len(a["digest_hex"]) == 64       # 32-byte SHA-256
        assert "block_index" in a
        assert "btc_attested" in a


def test_ots_upgrade_unknown_anchor_returns_404():
    r = requests.post(
        BASE + "/api/admin/ots/upgrade/ots-does-not-exist",
        headers=SOV, timeout=10,
    )
    assert r.status_code == 404


def test_ots_proof_download_unknown_anchor_returns_404():
    r = requests.get(
        BASE + "/api/admin/ots/anchors/ots-nope/proof",
        headers=SOV, timeout=10,
    )
    assert r.status_code == 404
