"""
Lattice Network — ledger / block finalisation primitives (Iter_34)
===================================================================

Extracted from server.py to unblock the mutating-route refactors
(`routes/lns.py`, `routes/certify.py`, `routes/pulse.py`). All the
functions that craft a block, run QBFT consensus and INSERT into
`db.blocks` now live here.

Like `core.py`, this module exposes an `init(db)` call to receive the
Mongo handle once at process startup. After that the async helpers can
be `await`-ed from anywhere.

Public surface:
    * canonical messages: `tx_canonical_message`, `block_canonical_message`
    * hashing: `merkle_root`, `tx_leaf_hash`, `compute_block_hash`
    * block construction: `build_signed_block`
    * end-to-end finalisation: `finalise_block_for_tx`,
      `finalise_batch_block`, `qbft_finalise`

Constants kept here:
    `CHAIN_ID`, `QBFT_TIMEOUT_S`, `QBFT_QUORUM`
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from typing import Any, List, Optional

import httpx
from fastapi import HTTPException

import core

_log = logging.getLogger("lattice.chain")

CHAIN_ID = os.environ.get("LATTICE_CHAIN_ID", "lattice-sovereign-it-prod")
QBFT_TIMEOUT_S = 2.5
QBFT_QUORUM = 3  # 2f+1 with f=1, n=4

# Set by init(db) at startup.
_DB: Any = None
# Single-writer lock for block proposal — prevents two simultaneous
# `_finalise_block_for_tx` racing for the same `next_index`.
BLOCK_PROPOSAL_LOCK: asyncio.Lock = asyncio.Lock()


def init(db_handle: Any) -> None:
    global _DB
    _DB = db_handle


def _require_db() -> Any:
    if _DB is None:
        raise RuntimeError("chain.init(db) was not called — wiring bug")
    return _DB


# ---------------------------------------------------------------------------
# Canonical message formats (used by signers and verifiers)
# ---------------------------------------------------------------------------


def tx_canonical_message(tx: dict) -> bytes:
    """Deterministic byte sequence signed by every transaction.

    DeliveryReceipt transactions use a different canonical (the PEC
    receipt envelope) because the signer is the recipient and the
    payload binds the mail metadata, not the TX metadata.
    """
    kind = tx.get("kind", "")
    if kind == "DeliveryReceipt":
        return ("|".join([
            tx.get("mail_id", ""),
            tx.get("sealed_at", "") or tx.get("signed_at", ""),
            tx.get("sender", ""),
            tx.get("recipient", ""),
            tx.get("doc_hash", ""),
        ])).encode("utf-8")
    parts = [
        tx.get("tx_id", ""),
        str(tx.get("block_index", "")),
        tx.get("timestamp", ""),
        tx.get("kind", ""),
        tx.get("summary", ""),
    ]
    return ("|".join(parts)).encode("utf-8")


def block_canonical_message(block: dict) -> bytes:
    """Deterministic byte sequence signed by every validator.

    Binds the block to: chain_id, merkle_root, previous_hash, block_hash.
    """
    parts = [
        block.get("chain_id", ""),
        str(block.get("index", "")),
        block.get("timestamp", ""),
        block.get("previous_hash", ""),
        block.get("merkle_root", ""),
        str(block.get("transactions_count", "")),
        block.get("block_hash", ""),
    ]
    return ("|".join(parts)).encode("utf-8")


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def merkle_root(tx_hashes: List[str]) -> str:
    """SHA3-256 Merkle root over the leaf TX hashes. Empty → 64 zeros."""
    if not tx_hashes:
        return "0" * 64
    level = [bytes.fromhex(h) for h in tx_hashes]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        nxt = []
        for i in range(0, len(level), 2):
            nxt.append(hashlib.sha3_256(level[i] + level[i + 1]).digest())
        level = nxt
    return level[0].hex()


def tx_leaf_hash(
    tx_id: str, kind: str, doc_hash: str = "", signer: str = "", ts: str = "",
) -> str:
    """Stable leaf hash for a transaction (SHA3-256)."""
    payload = "|".join([tx_id, kind, doc_hash, signer, ts]).encode("utf-8")
    return hashlib.sha3_256(payload).hexdigest()


def compute_block_hash(
    *,
    chain_id: str,
    index: int,
    timestamp: str,
    previous_hash: str,
    merkle_root_hex: str,
    transactions_count: int,
) -> str:
    """SHA3-512 hash of the block header."""
    payload = "|".join([
        chain_id, str(index), timestamp, previous_hash,
        merkle_root_hex, str(transactions_count),
    ]).encode("utf-8")
    return hashlib.sha3_512(payload).hexdigest()


# ---------------------------------------------------------------------------
# Block construction
# ---------------------------------------------------------------------------


def build_signed_block(
    *,
    index: int,
    timestamp: str,
    previous_hash: str,
    transactions: List[dict],
) -> dict:
    """Produce a fully-bound block header from a list of TX dicts.

    Each TX must already have `tx_id`, `kind`, optionally `doc_hash`,
    `signer_entity`, `timestamp`. Returns the block dict ready for
    `qbft_finalise()`.
    """
    leaves = [
        tx_leaf_hash(
            t.get("tx_id", ""),
            t.get("kind", ""),
            t.get("doc_hash", ""),
            t.get("signer_entity", ""),
            t.get("timestamp", ""),
        )
        for t in transactions
    ]
    merkle = merkle_root(leaves)
    block_hash = compute_block_hash(
        chain_id=CHAIN_ID, index=index, timestamp=timestamp,
        previous_hash=previous_hash, merkle_root_hex=merkle,
        transactions_count=len(transactions),
    )
    return {
        "chain_id": CHAIN_ID,
        "index": index,
        "timestamp": timestamp,
        "previous_hash": previous_hash,
        "merkle_root": merkle,
        "transactions_count": len(transactions),
        "tx_ids": [t.get("tx_id") for t in transactions],
        "block_hash": block_hash,
    }


# ---------------------------------------------------------------------------
# QBFT finalisation
# ---------------------------------------------------------------------------


async def qbft_finalise(block_doc: dict) -> dict:
    """Broadcast a block proposal to all live validators and collect
    2f+1 ML-DSA-65 signatures. Refuses to publish a block if the
    validator registry is empty (no single-signer fallback).
    """
    for k in ("chain_id", "merkle_root", "previous_hash", "block_hash"):
        if not block_doc.get(k):
            raise HTTPException(status_code=500, detail=f"qbft_finalise refused: missing {k}")
    proposal = {
        "index": block_doc["index"],
        "timestamp": block_doc["timestamp"],
        "previous_hash": block_doc["previous_hash"],
        "block_hash": block_doc["block_hash"],
        "merkle_root": block_doc["merkle_root"],
        "transactions_count": block_doc.get("transactions_count", 1),
        "chain_id": block_doc["chain_id"],
    }
    validators = await core.qbft_known_validators()
    if not validators:
        raise HTTPException(
            status_code=503,
            detail=(
                "QBFT validator registry empty · refuse to publish block "
                "(security: no single-signer fallback)."
            ),
        )

    async def _ask(v: dict) -> Optional[dict]:
        url = f"{v['endpoint']}/qbft/sign-block"
        try:
            async with httpx.AsyncClient(timeout=QBFT_TIMEOUT_S) as cx:
                r = await cx.post(url, json=proposal)
                if r.status_code != 200:
                    return None
                return r.json()
        except Exception:
            return None

    results = await asyncio.gather(*[_ask(v) for v in validators])
    votes: List[dict] = []
    seen_signers: set[str] = set()
    msg = block_canonical_message(block_doc)
    for vote in results:
        if not vote:
            continue
        signer = vote.get("validator_id")
        if not signer or signer in seen_signers:
            continue
        ok = await core.pqc_verify(signer, msg, vote.get("signature_hex", ""))
        if ok:
            votes.append(vote)
            seen_signers.add(signer)

    if len(votes) < QBFT_QUORUM:
        raise HTTPException(
            status_code=503,
            detail=(
                f"QBFT quorum not reached · need {QBFT_QUORUM}, got "
                f"{len(votes)} signatures from {len(validators)} validators"
            ),
        )

    primary = votes[0]
    block_doc["proposer"] = primary["validator_id"]
    block_doc["proposer_signature"] = primary["signature_hex"]
    block_doc["proposer_pk_fingerprint"] = primary["pk_fingerprint"]
    block_doc["signed_with"] = core.PQC_ALGORITHM
    block_doc["qbft_votes"] = votes
    block_doc["qbft_quorum"] = QBFT_QUORUM
    block_doc["qbft_total_validators"] = len(validators)
    return block_doc


# ---------------------------------------------------------------------------
# End-to-end finalisers (caller does NOT insert into db.blocks again)
# ---------------------------------------------------------------------------


async def finalise_block_for_tx(
    *,
    index: int,
    timestamp: str,
    tx_id: str,
    kind: str,
    doc_hash: str = "",
    signer: str = "",
) -> dict:
    """Build a single-TX block, run QBFT, INSERT into db.blocks, return result."""
    db = _require_db()
    async with BLOCK_PROPOSAL_LOCK:
        prev = await db.blocks.find_one(
            {}, {"_id": 0, "block_hash": 1, "index": 1}, sort=[("index", -1)],
        )
        prev_hash = prev["block_hash"] if prev else "0" * 128
        effective_index = (prev["index"] + 1) if prev else 1
        block = build_signed_block(
            index=effective_index, timestamp=timestamp, previous_hash=prev_hash,
            transactions=[{
                "tx_id": tx_id, "kind": kind,
                "doc_hash": doc_hash, "signer_entity": signer,
                "timestamp": timestamp,
            }],
        )
        result = await qbft_finalise(block)
        await db.blocks.insert_one(result)
        return result


async def finalise_batch_block(*, transactions: List[dict]) -> dict:
    """Same as finalise_block_for_tx but writes a single block with N TXs."""
    if not transactions:
        raise ValueError("transactions list cannot be empty")
    db = _require_db()
    async with BLOCK_PROPOSAL_LOCK:
        prev = await db.blocks.find_one(
            {}, {"_id": 0, "block_hash": 1, "index": 1}, sort=[("index", -1)],
        )
        prev_hash = prev["block_hash"] if prev else "0" * 128
        effective_index = (prev["index"] + 1) if prev else 1
        ts = transactions[0].get("timestamp") or core.utc_iso()
        block = build_signed_block(
            index=effective_index, timestamp=ts, previous_hash=prev_hash,
            transactions=transactions,
        )
        result = await qbft_finalise(block)
        await db.blocks.insert_one(result)
        return result
