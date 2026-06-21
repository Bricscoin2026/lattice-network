"""
Lattice Network — OpenTimestamps Bitcoin anchor (Iter_29)
==========================================================

OPTIONAL hardening: anchor the Lattice ledger state to the Bitcoin
blockchain via OpenTimestamps. The anchor is opt-in (an operator-driven
action) and works exactly like the public-good `ots stamp` CLI:

  1. Compute a SHA-256 digest of the Lattice "chain anchor payload"
     (= concatenation of {chain_id}|{last_block_index}|{last_block_hash}|
        {last_block_merkle_root}|{ts}).
  2. Submit it to a public OTS calendar (`a.pool.opentimestamps.org` by
     default — Peter Todd's pool; ~5 federated calendar servers).
  3. Persist the returned `.ots` proof bytes in MongoDB
     (`db.ots_anchors`) so the operator can download / re-verify later.
  4. After ~3 hours the calendar bundles thousands of digests into a
     single OP_RETURN Bitcoin transaction. The `.ots` proof becomes
     "Bitcoin-attested" automatically — no need to re-stamp.

Why this matters for sovereign deployments:
    A bank's regulator (Banca d'Italia / BCE) asks: "what if Lattice
    S.r.l. goes bankrupt next year?". With OTS, EVERY notarised
    document's certificate timestamp can be proven against Bitcoin —
    the most-verifiable immutable object in existence — even if every
    Lattice validator + the vendor company disappears.

Costs:
    Zero. The calendar pools are public goods. OTS aggregates millions
    of digests into one Bitcoin tx so per-anchor cost is sub-cent and
    paid by the calendar operators (donations / Peter Todd / Eternity
    Wall etc.).

This module gates on `LATTICE_OTS_ENABLED=1` so air-gapped deployments
(no outbound Internet) simply skip the feature.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from opentimestamps.calendar import RemoteCalendar
from opentimestamps.core.op import OpSHA256
from opentimestamps.core.serialize import (
    BytesDeserializationContext,
    BytesSerializationContext,
)
from opentimestamps.core.timestamp import DetachedTimestampFile, Timestamp

_log = logging.getLogger("lattice.ots")

# Public-good calendar pool. Operators can override to ship their own
# (e.g. a corporate calendar that proxies the public pool over an HTTPS
# bastion host, or for air-gapped environments — leave OTS disabled).
DEFAULT_CALENDARS = [
    "https://a.pool.opentimestamps.org",
    "https://b.pool.opentimestamps.org",
    "https://alice.btc.calendar.catallaxy.com",
]


def is_enabled() -> bool:
    return os.environ.get("LATTICE_OTS_ENABLED", "0").strip() in ("1", "true", "yes")


def _calendars() -> list[str]:
    raw = os.environ.get("LATTICE_OTS_CALENDARS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    return list(DEFAULT_CALENDARS)


def compute_anchor_digest(*, chain_id: str, block_index: int, block_hash: str,
                          merkle_root: str, ts_iso: str) -> bytes:
    """Build the canonical Lattice-anchor payload + SHA-256 hash it.

    The payload is intentionally human-debuggable: a pipe-separated
    string with all the fields a notary or judge needs to identify
    *which* state of the Lattice ledger this anchor pins down.
    """
    payload = (
        f"lattice-ots-v1|chain={chain_id}|height={block_index}|"
        f"block={block_hash}|merkle={merkle_root}|ts={ts_iso}"
    ).encode("utf-8")
    return hashlib.sha256(payload).digest()


async def submit_anchor(digest: bytes, *, timeout: float = 15.0) -> tuple[Timestamp, str]:
    """Submit a digest to the first calendar that accepts it.

    Returns (timestamp, calendar_url_used). The Timestamp returned by
    the calendar is a single-attestation Timestamp; once the bitcoin
    block is mined ~3h later the proof is upgraded with the bitcoin
    block-header attestation by anyone calling `upgrade()`.
    """
    if len(digest) != 32:
        raise ValueError("digest must be 32 bytes (SHA-256)")
    loop = asyncio.get_event_loop()
    last_err: Optional[str] = None
    for url in _calendars():
        try:
            cal = RemoteCalendar(url, user_agent="lattice-network/0.28")
            ts = await loop.run_in_executor(None, lambda: cal.submit(digest, timeout=timeout))
            _log.info("OTS calendar accepted digest at %s", url)
            return ts, url
        except Exception as e:  # network, http, schema, …
            last_err = f"{url}: {e}"
            _log.warning("OTS calendar %s failed: %s", url, e)
            continue
    raise RuntimeError(f"all OTS calendars failed (last_err={last_err})")


def serialize_proof(timestamp: Timestamp) -> bytes:
    """Serialize to the standard `.ots` binary format (DetachedTimestampFile)."""
    dtf = DetachedTimestampFile(OpSHA256(), timestamp)
    ctx = BytesSerializationContext()
    dtf.serialize(ctx)
    return ctx.getbytes()


def deserialize_proof(blob: bytes) -> DetachedTimestampFile:
    ctx = BytesDeserializationContext(blob)
    return DetachedTimestampFile.deserialize(ctx)


async def create_anchor(db: Any, *, chain_id: str) -> dict:
    """End-to-end: pick the current tip of the ledger, compute the
    digest, submit it to OTS, persist the proof.

    Returns a dict suitable for the admin UI / API response.
    """
    if not is_enabled():
        raise RuntimeError("OpenTimestamps anchoring is disabled (set LATTICE_OTS_ENABLED=1)")

    tip = await db.blocks.find_one(sort=[("index", -1)])
    if not tip:
        raise RuntimeError("ledger is empty — nothing to anchor")

    ts_iso = datetime.now(timezone.utc).isoformat()
    digest = compute_anchor_digest(
        chain_id=chain_id,
        block_index=int(tip.get("index", 0)),
        block_hash=str(tip.get("block_hash", "")),
        merkle_root=str(tip.get("merkle_root", "") or tip.get("block_hash", "")),
        ts_iso=ts_iso,
    )

    timestamp, calendar_url = await submit_anchor(digest)
    proof_bytes = serialize_proof(timestamp)

    doc = {
        "anchor_id": f"ots-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{digest.hex()[:8]}",
        "created_at": ts_iso,
        "chain_id": chain_id,
        "block_index": int(tip.get("index", 0)),
        "block_hash": str(tip.get("block_hash", "")),
        "merkle_root": str(tip.get("merkle_root", "") or tip.get("block_hash", "")),
        "digest_hex": digest.hex(),
        "calendar_url": calendar_url,
        "proof_b64": base64.b64encode(proof_bytes).decode("ascii"),
        "proof_size": len(proof_bytes),
        "btc_attested": False,    # promoted to True after an `upgrade` succeeds
    }
    await db.ots_anchors.insert_one(doc)
    doc.pop("_id", None)
    _log.info("OTS anchor created · %s · digest=%s", doc["anchor_id"], doc["digest_hex"][:16])
    return doc


async def upgrade_anchor(db: Any, anchor_id: str, *, timeout: float = 15.0) -> dict:
    """Ask the calendar to upgrade a previously-submitted timestamp with
    its Bitcoin block-header attestation. Returns the refreshed doc."""
    if not is_enabled():
        raise RuntimeError("OpenTimestamps anchoring is disabled")
    doc = await db.ots_anchors.find_one({"anchor_id": anchor_id})
    if not doc:
        raise KeyError(f"anchor not found: {anchor_id}")
    proof_bytes = base64.b64decode(doc["proof_b64"])
    dtf = deserialize_proof(proof_bytes)
    digest = bytes.fromhex(doc["digest_hex"])

    loop = asyncio.get_event_loop()
    upgraded = False
    last_err = ""
    for url in _calendars():
        try:
            cal = RemoteCalendar(url, user_agent="lattice-network/0.28")
            new_ts = await loop.run_in_executor(None, lambda: cal.get_timestamp(digest, timeout=timeout))
            dtf.timestamp.merge(new_ts)
            upgraded = True
            break
        except KeyError:
            last_err = f"{url}: not yet known"
            continue
        except Exception as e:
            last_err = f"{url}: {e}"
            continue

    new_proof = serialize_proof(dtf.timestamp)
    # Mark as bitcoin-attested if any attestation in the merged proof is
    # a Bitcoin header attestation (BitcoinBlockHeaderAttestation tag).
    btc_attested = _has_bitcoin_attestation(dtf.timestamp)
    await db.ots_anchors.update_one(
        {"anchor_id": anchor_id},
        {"$set": {
            "proof_b64": base64.b64encode(new_proof).decode("ascii"),
            "proof_size": len(new_proof),
            "btc_attested": btc_attested,
            "last_upgrade_at": datetime.now(timezone.utc).isoformat(),
            "last_upgrade_status": "ok" if upgraded else f"pending ({last_err})",
        }},
    )
    refreshed = await db.ots_anchors.find_one({"anchor_id": anchor_id})
    refreshed.pop("_id", None)
    return refreshed


def _has_bitcoin_attestation(timestamp: Timestamp) -> bool:
    """Walk the proof tree looking for BitcoinBlockHeaderAttestation."""
    try:
        from opentimestamps.core.notary import BitcoinBlockHeaderAttestation as Btc
    except Exception:
        return False
    seen = [timestamp]
    while seen:
        t = seen.pop()
        for att in t.attestations:
            if isinstance(att, Btc):
                return True
        for _op, sub in t.ops.items():
            seen.append(sub)
    return False


async def list_anchors(db: Any, limit: int = 50) -> list[dict]:
    cursor = db.ots_anchors.find({}, {"_id": 0, "proof_b64": 0}).sort("created_at", -1).limit(limit)
    return [r async for r in cursor]


async def get_proof_bytes(db: Any, anchor_id: str) -> Optional[bytes]:
    doc = await db.ots_anchors.find_one({"anchor_id": anchor_id}, {"_id": 0, "proof_b64": 1})
    if not doc:
        return None
    return base64.b64decode(doc["proof_b64"])


# ---------------------------------------------------------------------------
# Background upgrade loop (Iter_30)
# ---------------------------------------------------------------------------

async def auto_upgrade_loop(db: Any, *, interval_sec: float = 21600.0) -> None:
    """Every ~6h, iterate all anchors with btc_attested=False and try
    to fetch a fresh proof from the calendar. The Bitcoin block-header
    attestation typically lands ~3h after submission, so a daily cadence
    is more than enough but we run faster to make the UI feel alive.

    Skipped automatically when LATTICE_OTS_ENABLED != 1 — the function
    returns immediately on each tick so it costs nothing in disabled mode.
    """
    _log.info("OTS auto-upgrade loop started · interval=%ds", int(interval_sec))
    # Initial delay so we don't slam the calendar right after process boot
    # (gives the validators time to settle).
    await asyncio.sleep(60)
    while True:
        try:
            if not is_enabled():
                # Re-check every interval — operator may flip the env mid-flight.
                await asyncio.sleep(interval_sec)
                continue
            pending_cursor = db.ots_anchors.find(
                {"btc_attested": False}, {"_id": 0, "anchor_id": 1}
            ).limit(100)
            pending = [doc["anchor_id"] async for doc in pending_cursor]
            if pending:
                _log.info("OTS auto-upgrade tick · %d pending anchors", len(pending))
            promoted = 0
            for anchor_id in pending:
                try:
                    refreshed = await upgrade_anchor(db, anchor_id)
                    if refreshed.get("btc_attested"):
                        promoted += 1
                        _log.info("OTS anchor %s → btc_attested=True", anchor_id)
                except Exception as e:  # pragma: no cover — defensive
                    _log.warning("OTS auto-upgrade failed for %s: %s", anchor_id, e)
                # Small pause between calls to avoid hammering the calendar.
                await asyncio.sleep(2.0)
            if promoted:
                _log.info("OTS auto-upgrade tick · promoted %d anchors", promoted)
        except asyncio.CancelledError:
            _log.info("OTS auto-upgrade loop cancelled")
            return
        except Exception as e:  # pragma: no cover — first-boot resilience
            _log.exception("OTS auto-upgrade tick crashed: %s", e)
        await asyncio.sleep(interval_sec)
