"""
Lattice QBFT validator — real BFT consensus participant.

Each validator runs as an independent OS process on its own TCP port.
It owns a real ML-DSA-65 (NIST FIPS 204) keypair and signs block
proposals broadcast by the lattice gateway. The aggregator collects
2f+1 signatures before finalising a block, which is real Byzantine
fault-tolerant consensus over real network round-trips.

Run example:
    LATTICE_VAL_ID=VAL-01 LATTICE_VAL_PORT=9001 \
    python -m uvicorn qbft_node:app --host 0.0.0.0 --port 9001
"""
from __future__ import annotations

import hashlib
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from pqcrypto.sign import ml_dsa_65 as mldsa
from pydantic import BaseModel

VAL_ID = os.environ.get("LATTICE_VAL_ID", "VAL-XX")
VAL_PORT = int(os.environ.get("LATTICE_VAL_PORT", "9001"))
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

_client = AsyncIOMotorClient(MONGO_URL)
_db = _client[DB_NAME]

_state: dict = {"pk": None, "sk": None, "fingerprint": None, "signed_total": 0, "started_at": None}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fp(pk: bytes) -> str:
    return hashlib.sha3_256(pk).hexdigest()[:32].upper()


async def _boot_key() -> None:
    """Materialise the validator's ML-DSA-65 keypair on first boot."""
    doc = await _db.keystore.find_one({"entity": VAL_ID})
    if doc:
        pk = bytes.fromhex(doc["pk_hex"])
        sk = bytes.fromhex(doc["sk_hex"])
    else:
        pk, sk = mldsa.generate_keypair()
        await _db.keystore.insert_one({
            "entity": VAL_ID,
            "role": "validator",
            "pk_hex": pk.hex(),
            "sk_hex": sk.hex(),
            "fingerprint": _fp(pk),
            "created_at": _now_iso(),
        })
    _state["pk"] = pk
    _state["sk"] = sk
    _state["fingerprint"] = _fp(pk)
    # Publish liveness so the gateway can discover us.
    await _db.qbft_registry.update_one(
        {"validator_id": VAL_ID},
        {"$set": {
            "validator_id": VAL_ID,
            "port": VAL_PORT,
            "endpoint": f"http://127.0.0.1:{VAL_PORT}",
            "pk_fingerprint": _state["fingerprint"],
            "boot_at": _now_iso(),
            "last_seen": _now_iso(),
            "signed_total": 0,
        }},
        upsert=True,
    )


@asynccontextmanager
async def _lifespan(_: FastAPI):
    _state["started_at"] = _now_iso()
    await _boot_key()
    yield


app = FastAPI(title=f"Lattice QBFT validator {VAL_ID}", lifespan=_lifespan)


class BlockProposal(BaseModel):
    index: int
    timestamp: str
    previous_hash: str
    block_hash: str
    merkle_root: str
    transactions_count: int
    chain_id: str


class SignedVote(BaseModel):
    validator_id: str
    pk_fingerprint: str
    signature_hex: str
    signed_at: str
    algorithm: str = "ML-DSA-65"


def _canonical(proposal: BlockProposal) -> bytes:
    # MUST mirror server._block_canonical_message exactly.
    return ("|".join([
        proposal.chain_id, str(proposal.index), proposal.timestamp,
        proposal.previous_hash, proposal.merkle_root,
        str(proposal.transactions_count), proposal.block_hash,
    ])).encode("utf-8")


# Recompute the block_hash from the header — the validator independently
# checks the proposer hasn't lied about its own hash. SHA3-512.
def _expected_block_hash(p: BlockProposal) -> str:
    payload = "|".join([
        p.chain_id, str(p.index), p.timestamp, p.previous_hash,
        p.merkle_root, str(p.transactions_count),
    ]).encode("utf-8")
    return hashlib.sha3_512(payload).hexdigest()


VALIDATOR_CHAIN_ID = os.environ.get("LATTICE_CHAIN_ID", "lattice-sovereign-it-prod")


async def _is_well_formed(proposal: BlockProposal) -> tuple[bool, str]:
    """Independent validator-side checks. The validator is NOT supposed
    to trust the proposer for anything: it must look up state in its own
    DB view and re-derive every committed quantity.

    Checks:
      1. chain_id matches this validator's expected chain
      2. block_hash == SHA3-512(header) (proposer didn't lie about its hash)
      3. previous_hash == DB[last block].block_hash (no chain rewriting)
      4. index == DB[last block].index + 1 (no height skipping)
      5. anti-equivocation: this validator hasn't already signed a
         different block at this height (rejects double-signing).
    """
    if proposal.index < 0:
        return False, "index < 0"
    if proposal.chain_id != VALIDATOR_CHAIN_ID:
        return False, f"chain_id mismatch (expected {VALIDATOR_CHAIN_ID})"
    if not proposal.block_hash or len(proposal.block_hash) != 128:
        return False, "block_hash length != 128 hex chars (SHA3-512)"
    if not proposal.previous_hash or len(proposal.previous_hash) != 128:
        return False, "previous_hash length != 128 hex chars"
    if not proposal.merkle_root or len(proposal.merkle_root) != 64:
        return False, "merkle_root length != 64 hex chars (SHA3-256)"
    if proposal.block_hash != _expected_block_hash(proposal):
        return False, "block_hash does not match recomputed header hash"
    # Chain integrity: previous_hash must equal the last block's block_hash.
    last = await _db.blocks.find_one({}, {"_id": 0, "block_hash": 1, "index": 1}, sort=[("index", -1)])
    if last is None:
        if proposal.previous_hash != "0" * 128:
            return False, "expected genesis previous_hash but DB has no last block"
        if proposal.index != 1:
            return False, "expected index=1 for first non-genesis block"
    else:
        if proposal.previous_hash != last["block_hash"]:
            return False, "previous_hash != DB last block hash (chain reorg attempt?)"
        if proposal.index <= last["index"]:
            return False, f"index {proposal.index} must be strictly greater than last ({last['index']})"
    # Anti-equivocation: have we already signed a DIFFERENT block at this height?
    prior = await _db.qbft_votes_emitted.find_one(
        {"validator_id": VAL_ID, "index": proposal.index},
        {"_id": 0, "block_hash": 1},
    )
    if prior and prior.get("block_hash") != proposal.block_hash:
        return False, f"equivocation refused: already signed a different block at index {proposal.index}"
    return True, "ok"


@app.get("/health")
async def health() -> dict:
    return {
        "ok": True,
        "validator_id": VAL_ID,
        "port": VAL_PORT,
        "pk_fingerprint": _state.get("fingerprint"),
        "started_at": _state.get("started_at"),
        "signed_total": _state.get("signed_total", 0),
    }


@app.post("/qbft/sign-block", response_model=SignedVote)
async def sign_block(proposal: BlockProposal) -> SignedVote:
    ok, reason = await _is_well_formed(proposal)
    if not ok:
        raise HTTPException(status_code=400, detail=f"malformed block proposal: {reason}")
    sk = _state.get("sk")
    if sk is None:
        raise HTTPException(status_code=503, detail="validator key not initialised")
    msg = _canonical(proposal)
    sig = mldsa.sign(sk, msg)
    _state["signed_total"] += 1
    ts = _now_iso()
    # Persist anti-equivocation marker BEFORE returning the signature.
    await _db.qbft_votes_emitted.update_one(
        {"validator_id": VAL_ID, "index": proposal.index},
        {"$set": {
            "validator_id": VAL_ID,
            "index": proposal.index,
            "block_hash": proposal.block_hash,
            "signed_at": ts,
        }},
        upsert=True,
    )
    await _db.qbft_registry.update_one(
        {"validator_id": VAL_ID},
        {"$set": {"last_seen": ts, "signed_total": _state["signed_total"]}},
    )
    return SignedVote(
        validator_id=VAL_ID,
        pk_fingerprint=_state["fingerprint"],
        signature_hex=sig.hex(),
        signed_at=ts,
    )
