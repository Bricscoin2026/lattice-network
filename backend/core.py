"""
Lattice Network — core helper module
=====================================

Pure helper functions extracted from server.py (Iter_32) so that the
route modules (`routes/*.py`) can import them WITHOUT triggering a
circular import via `server.py`.

The module holds a single piece of mutable state: the Mongo `db` handle.
Set once at process startup via `init(db)`. After that, the async
helpers can be called from anywhere.

Why a module-level `_DB` instead of passing `db` to every helper?
    Identical signatures to the original server.py functions — drop-in
    compatibility for all 80+ existing call sites that just need to be
    rewired with `from core import get_or_create_keypair, ...`.

Functions intentionally kept here:
    pure (no I/O):
        utc_iso, det_hex, hex_token, pk_fingerprint,
        tx_canonical_message, block_canonical_message,
        merkle_root, tx_leaf_hash, compute_block_hash, build_signed_block
    DB-bound:
        get_or_create_keypair, pqc_sign, pqc_verify,
        qbft_known_validators

Constants:
    PQC_ALGORITHM, PQC_PK_SIZE, PQC_SK_SIZE, PQC_SIG_SIZE
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Optional, Tuple

from pqcrypto.sign import ml_dsa_65 as mldsa

import envelope

_log = logging.getLogger("lattice.core")

# PQC constants — referenced widely so we expose them here once.
PQC_ALGORITHM = "ML-DSA-65"
PQC_PK_SIZE = mldsa.PUBLIC_KEY_SIZE
PQC_SK_SIZE = mldsa.SECRET_KEY_SIZE
PQC_SIG_SIZE = mldsa.SIGNATURE_SIZE

# In-process keypair cache: entity -> (pk, sk). Same semantics as the
# legacy `_KEY_CACHE` in server.py.
_KEY_CACHE: dict[str, Tuple[bytes, bytes]] = {}

# Mongo handle, set by `init()`.
_DB: Any = None


def init(db_handle: Any) -> None:
    """Wire up the module's database dependency. Call once at startup."""
    global _DB
    _DB = db_handle


def _require_db() -> Any:
    if _DB is None:
        raise RuntimeError("core.init(db) was not called — wiring bug")
    return _DB


# ---------------------------------------------------------------------------
# Pure helpers (no I/O)
# ---------------------------------------------------------------------------


def utc_iso() -> str:
    """RFC-3339 timestamp with UTC offset."""
    return datetime.now(timezone.utc).isoformat()


def hex_token(n: int) -> str:
    """Cryptographically random hex string of length 2n."""
    return secrets.token_hex(n)


def det_hex(seed: str, n: int) -> str:
    """Deterministic hex digest derived from `seed`, truncated to 2n chars."""
    h = hashlib.sha3_512(seed.encode()).hexdigest()
    return h[: n * 2]


def pk_fingerprint(pk: bytes) -> str:
    """8-byte SHA3-256 fingerprint of a public key, uppercase hex."""
    return hashlib.sha3_256(pk).hexdigest()[:32].upper()


# ---------------------------------------------------------------------------
# PQC keystore
# ---------------------------------------------------------------------------


async def get_or_create_keypair(entity: str, role: str = "lns") -> Tuple[bytes, bytes]:
    """Return the (pk, sk) tuple for *entity*, materialising it on first use.

    Backwards compatible with legacy plaintext `sk_hex` documents
    (auto-upgraded to envelope on next write).
    """
    if entity in _KEY_CACHE:
        return _KEY_CACHE[entity]
    db = _require_db()
    doc = await db.keystore.find_one({"entity": entity})
    if doc:
        pk = bytes.fromhex(doc["pk_hex"])
        sk_field = doc.get("sk")
        if sk_field:
            sk = bytes.fromhex(envelope.open_hex(sk_field, aad=entity.encode()))
        else:
            sk = bytes.fromhex(doc["sk_hex"])
    else:
        pk, sk = mldsa.generate_keypair()
        await db.keystore.insert_one({
            "entity": entity,
            "role": role,
            "pk_hex": pk.hex(),
            "sk": envelope.seal_hex(sk.hex(), aad=entity.encode()),
            "fingerprint": pk_fingerprint(pk),
            "created_at": utc_iso(),
            "algorithm": PQC_ALGORITHM,
        })
    _KEY_CACHE[entity] = (pk, sk)
    return pk, sk


async def pqc_sign(entity: str, message: bytes, role: str = "lns") -> Tuple[str, str]:
    """Real ML-DSA-65 detached signature.

    Returns (signature_hex, public_key_fingerprint).
    """
    pk, sk = await get_or_create_keypair(entity, role)
    sig = mldsa.sign(sk, message)
    return sig.hex(), pk_fingerprint(pk)


async def pqc_verify(entity: str, message: bytes, signature_hex: str) -> bool:
    """Real ML-DSA-65 detached verification. False on missing pk / bad sig."""
    db = _require_db()
    doc = await db.keystore.find_one({"entity": entity}, {"_id": 0, "pk_hex": 1})
    if not doc:
        return False
    pk = bytes.fromhex(doc["pk_hex"])
    try:
        sig = bytes.fromhex(signature_hex)
    except ValueError:
        return False
    try:
        return bool(mldsa.verify(pk, message, sig))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# QBFT registry
# ---------------------------------------------------------------------------


def _db_qbft_registry():
    return _require_db().qbft_registry


async def qbft_known_validators() -> list[dict]:
    cursor = _db_qbft_registry().find({}, {"_id": 0}).sort("validator_id", 1)
    return [doc async for doc in cursor]


__all__ = [
    "PQC_ALGORITHM", "PQC_PK_SIZE", "PQC_SK_SIZE", "PQC_SIG_SIZE",
    "init",
    "utc_iso", "hex_token", "det_hex", "pk_fingerprint",
    "get_or_create_keypair", "pqc_sign", "pqc_verify",
    "qbft_known_validators",
]
