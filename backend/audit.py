"""
Lattice — append-only audit log with Merkle-style hash chain
=============================================================

Every entry includes the SHA3-512 hash of the previous entry, forming an
immutable chain. Tampering with any past entry (deletion, edit) breaks
the chain — verifiable by `verify_chain()`.

API:
    await audit.append(db, event_type, **fields)
    await audit.verify_chain(db)  → (ok: bool, broken_at: Optional[int])
"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone
from typing import Any, Optional


GENESIS = "0" * 128  # 64-byte zero hash kicks off the chain


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canon(payload: dict[str, Any]) -> bytes:
    """Deterministic JSON serialisation for hashing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


async def append(db, event_type: str, **fields) -> dict:
    """Insert a new audit entry chained to the previous one.

    Returns the entry document (including `prev_hash` and `entry_hash`).
    """
    last = await db.audit_log.find_one({}, sort=[("seq", -1)])
    prev_hash = last.get("entry_hash", GENESIS) if last else GENESIS
    seq = (last.get("seq", -1) if last else -1) + 1
    entry = {
        "seq": seq,
        "ts": _utc_iso(),
        "event": event_type,
        "nonce": secrets.token_hex(8),
        **fields,
        "prev_hash": prev_hash,
    }
    entry["entry_hash"] = hashlib.sha3_512(_canon(entry)).hexdigest()
    await db.audit_log.insert_one(entry)
    return entry


async def verify_chain(db, max_entries: int = 10_000) -> tuple[bool, Optional[int]]:
    """Walk the chain from seq=0 forward and check every prev_hash link.

    Returns `(True, None)` if the chain is intact, otherwise
    `(False, seq_of_first_broken_entry)`.
    """
    expected = GENESIS
    seq = 0
    cursor = db.audit_log.find({}, {"_id": 0}).sort("seq", 1).limit(max_entries)
    async for entry in cursor:
        if entry.get("seq") != seq:
            return False, seq
        if entry.get("prev_hash") != expected:
            return False, seq
        recomputed = hashlib.sha3_512(
            _canon({k: v for k, v in entry.items() if k != "entry_hash"})
        ).hexdigest()
        if recomputed != entry.get("entry_hash"):
            return False, seq
        expected = entry["entry_hash"]
        seq += 1
    return True, None
