"""
Lattice Network — passphrase-based master-key manager
======================================================

This module derives the at-rest envelope key from an admin passphrase
using Argon2id (memory-hard KDF, OWASP recommended profile).

Why a separate module from `envelope.py`?
    `envelope.py` is the low-level seal/open API consumed everywhere.
    This module is the *operator-facing* control plane: init / unlock /
    rotate the master key without restarting the process.

Modes of operation (resolved at startup):

  1. STATIC KEY (legacy / dev):
     env `LATTICE_ENVELOPE_KEY` = 64 hex chars (32 bytes) → loaded by
     `envelope._load_master_key()`. No passphrase required, no unlock
     ceremony. Acceptable for single-tenant dev installs.

  2. PASSPHRASE FROM ENV (recommended for Docker self-host):
     env `LATTICE_ENVELOPE_PASSPHRASE` = arbitrary text. On first boot we
     generate a 16-byte salt + Argon2id verifier and persist them in
     `db.secret_config`. On subsequent boots we re-derive the key from
     the same passphrase + salt and verify against the stored hash.

  3. RUNTIME UNLOCK (high-security / banking):
     Neither env var set. The keystore boots in LOCKED state, signing
     keys cannot be read. Operator calls `POST /api/admin/secrets/unlock`
     with the passphrase to derive the key in-memory for that process
     lifetime. Sealed values cannot be opened until then.

Wire format of the verifier stored in Mongo (`db.secret_config._id="envelope_v1"`):
    {
        "_id": "envelope_v1",
        "salt_hex": "<32 hex>",
        "verifier": "<argon2id encoded hash>",   # safe to leak
        "created_at": "<iso>",
        "kdf": "argon2id",
        "time_cost": 3, "memory_cost": 65536, "parallelism": 4
    }

The verifier is the *argon2 PHC encoded hash*; it is NEVER used to
derive bytes, it only proves that a candidate passphrase matches.
The actual 32-byte master key is derived separately with
`PasswordHasher.hash` parameters using `argon2.low_level.hash_secret_raw`.
"""
from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from argon2.low_level import Type, hash_secret_raw

import envelope

_log = logging.getLogger("lattice.secrets")

# OWASP 2024 recommended Argon2id profile for password hashing.
_ARGON2_TIME_COST = 3
_ARGON2_MEMORY_COST = 65536   # 64 MiB
_ARGON2_PARALLELISM = 4
_ARGON2_HASH_LEN = 32         # derive a 32-byte AES-256-GCM key
_SALT_BYTES = 16
_CONFIG_ID = "envelope_v1"

_hasher = PasswordHasher(
    time_cost=_ARGON2_TIME_COST,
    memory_cost=_ARGON2_MEMORY_COST,
    parallelism=_ARGON2_PARALLELISM,
)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class _State:
    """Process-wide secret manager state."""

    def __init__(self) -> None:
        self.mode: str = "static"        # static | passphrase | locked
        self.unlocked: bool = False
        self.locked_reason: str = ""
        # When True, the static env-var key took precedence — passphrase
        # endpoints are disabled because the operator already opted into
        # the simpler model.
        self.static_key_loaded: bool = False


STATE = _State()


# ---------------------------------------------------------------------------
# KDF
# ---------------------------------------------------------------------------


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Argon2id → 32-byte AES-256-GCM key."""
    if not passphrase:
        raise ValueError("passphrase must be non-empty")
    if len(salt) < _SALT_BYTES:
        raise ValueError(f"salt must be >= {_SALT_BYTES} bytes")
    return hash_secret_raw(
        secret=passphrase.encode("utf-8"),
        salt=salt,
        time_cost=_ARGON2_TIME_COST,
        memory_cost=_ARGON2_MEMORY_COST,
        parallelism=_ARGON2_PARALLELISM,
        hash_len=_ARGON2_HASH_LEN,
        type=Type.ID,
    )


# ---------------------------------------------------------------------------
# Bootstrapping (called from server startup)
# ---------------------------------------------------------------------------


async def bootstrap(db: Any) -> None:
    """Resolve the operating mode at process boot.

    Precedence:
        1. LATTICE_ENVELOPE_KEY (static)
        2. LATTICE_ENVELOPE_PASSPHRASE (auto-derive)
        3. locked — wait for runtime unlock
    """
    if os.environ.get("LATTICE_ENVELOPE_KEY", "").strip():
        # Already loaded by envelope module on first seal/open.
        envelope._ensure_loaded()  # noqa: SLF001 — intentional
        if envelope._AEAD is not None:  # noqa: SLF001
            STATE.mode = "static"
            STATE.unlocked = True
            STATE.static_key_loaded = True
            _log.info("Secret manager: STATIC mode (LATTICE_ENVELOPE_KEY)")
            return

    passphrase = os.environ.get("LATTICE_ENVELOPE_PASSPHRASE", "").strip()
    cfg = await db.secret_config.find_one({"_id": _CONFIG_ID})

    if passphrase:
        if cfg is None:
            # First boot with a passphrase → create salt + verifier
            salt = secrets.token_bytes(_SALT_BYTES)
            verifier = _hasher.hash(passphrase)
            await db.secret_config.insert_one({
                "_id": _CONFIG_ID,
                "salt_hex": salt.hex(),
                "verifier": verifier,
                "kdf": "argon2id",
                "time_cost": _ARGON2_TIME_COST,
                "memory_cost": _ARGON2_MEMORY_COST,
                "parallelism": _ARGON2_PARALLELISM,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            _log.info("Secret manager: initialised passphrase verifier (first boot)")
        else:
            salt = bytes.fromhex(cfg["salt_hex"])
            try:
                _hasher.verify(cfg["verifier"], passphrase)
            except VerifyMismatchError:
                STATE.mode = "locked"
                STATE.locked_reason = (
                    "LATTICE_ENVELOPE_PASSPHRASE does NOT match the stored verifier. "
                    "Refusing to derive a wrong master key (would corrupt at-rest data)."
                )
                _log.error(STATE.locked_reason)
                return

        key = _derive_key(passphrase, salt)
        envelope.set_master_key(key)
        STATE.mode = "passphrase"
        STATE.unlocked = True
        _log.info("Secret manager: PASSPHRASE mode (env-supplied, auto-unlock)")
        return

    # No env var set — wait for runtime unlock
    STATE.mode = "locked"
    if cfg is None:
        STATE.locked_reason = "Keystore not initialised. Call POST /api/admin/secrets/init."
    else:
        STATE.locked_reason = "Keystore locked. Call POST /api/admin/secrets/unlock."
    _log.warning("Secret manager: LOCKED — %s", STATE.locked_reason)


# ---------------------------------------------------------------------------
# Runtime control plane (called from /api routes)
# ---------------------------------------------------------------------------


async def init_passphrase(db: Any, passphrase: str) -> dict:
    """First-time initialisation when neither env var was set.

    Idempotency: if a verifier already exists this fails — the operator
    must use `unlock` (or rotate).
    """
    if STATE.static_key_loaded:
        raise RuntimeError("static LATTICE_ENVELOPE_KEY in use — passphrase init disabled")
    if len(passphrase) < 12:
        raise ValueError("passphrase must be at least 12 characters")

    cfg = await db.secret_config.find_one({"_id": _CONFIG_ID})
    if cfg is not None:
        raise RuntimeError("passphrase already initialised — use /unlock or /rotate")

    salt = secrets.token_bytes(_SALT_BYTES)
    verifier = _hasher.hash(passphrase)
    await db.secret_config.insert_one({
        "_id": _CONFIG_ID,
        "salt_hex": salt.hex(),
        "verifier": verifier,
        "kdf": "argon2id",
        "time_cost": _ARGON2_TIME_COST,
        "memory_cost": _ARGON2_MEMORY_COST,
        "parallelism": _ARGON2_PARALLELISM,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    key = _derive_key(passphrase, salt)
    envelope.set_master_key(key)
    STATE.mode = "passphrase"
    STATE.unlocked = True
    STATE.locked_reason = ""
    _log.info("Secret manager: passphrase initialised via API")
    return {"ok": True, "mode": "passphrase", "unlocked": True}


async def unlock(db: Any, passphrase: str) -> dict:
    """Derive the master key from an existing passphrase + verifier."""
    if STATE.static_key_loaded:
        return {"ok": True, "mode": "static", "unlocked": True, "note": "static key, unlock is no-op"}
    cfg = await db.secret_config.find_one({"_id": _CONFIG_ID})
    if cfg is None:
        raise RuntimeError("keystore not initialised — call /init first")
    try:
        _hasher.verify(cfg["verifier"], passphrase)
    except VerifyMismatchError:
        raise PermissionError("passphrase does not match stored verifier")

    salt = bytes.fromhex(cfg["salt_hex"])
    key = _derive_key(passphrase, salt)
    envelope.set_master_key(key)
    STATE.mode = "passphrase"
    STATE.unlocked = True
    STATE.locked_reason = ""
    _log.info("Secret manager: unlocked via API")
    return {"ok": True, "mode": "passphrase", "unlocked": True}


def status() -> dict:
    """Read-only state for the admin dashboard."""
    return {
        "mode": STATE.mode,
        "unlocked": STATE.unlocked,
        "locked_reason": STATE.locked_reason or None,
        "static_key_loaded": STATE.static_key_loaded,
        "kdf": "argon2id",
        "kdf_params": {
            "time_cost": _ARGON2_TIME_COST,
            "memory_cost_kb": _ARGON2_MEMORY_COST,
            "parallelism": _ARGON2_PARALLELISM,
        },
    }


def require_unlocked() -> None:
    """Raise if envelope is locked — call before any sk_hex access."""
    if not STATE.unlocked:
        raise RuntimeError(f"keystore is locked: {STATE.locked_reason}")
