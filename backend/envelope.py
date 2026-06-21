"""
Lattice Network — envelope encryption for at-rest secrets
==========================================================

Single API for AES-256-GCM encryption of:
    1. PQC secret keys in `db.keystore.sk_hex`
    2. Pulse plaintext bodies in `db.pulse_messages.plaintext`
    3. Certify mail bodies in `db.certify_mails.body`
    4. Recovery codes, future password-protected fields

The master key is derived from the env var `LATTICE_ENVELOPE_KEY` (32 hex
bytes = 64 hex chars). Lose the master key → cannot decrypt anything,
including the operator's own signing keys. Back it up offline in 2
separate places (same regime as the recovery code).

If `LATTICE_ENVELOPE_KEY` is NOT set the module operates in passthrough
mode (no encryption) — this keeps dev environments working but logs a
loud warning. Production MUST set the env var.

Wire format (each sealed value):
    "v1:<base64(nonce ‖ ciphertext ‖ tag)>"
The version prefix allows future key-rotation without re-encrypting the
whole database (write v2, read v1 + v2).
"""
from __future__ import annotations

import base64
import logging
import os
import secrets
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_log = logging.getLogger("lattice.envelope")
_VERSION = "v1"
_NONCE_SIZE = 12  # GCM standard


def _load_master_key() -> Optional[bytes]:
    raw = os.environ.get("LATTICE_ENVELOPE_KEY", "").strip()
    if not raw:
        return None
    try:
        key = bytes.fromhex(raw)
    except ValueError:
        raise SystemExit(
            "FATAL: LATTICE_ENVELOPE_KEY must be 64 hex characters (32 bytes). "
            "Generate one with: python -c 'import secrets; print(secrets.token_hex(32))'"
        )
    if len(key) != 32:
        raise SystemExit(
            f"FATAL: LATTICE_ENVELOPE_KEY must be 32 bytes (64 hex chars), got {len(key)}"
        )
    return key


_MASTER_KEY: Optional[bytes] = None
_AEAD: Optional[AESGCM] = None


def _ensure_loaded() -> None:
    """Lazy init — called on first seal/open. We delay so that the caller
    can `load_dotenv()` before the module reads the env var."""
    global _MASTER_KEY, _AEAD
    if _MASTER_KEY is not None or _AEAD is not None:
        return
    _MASTER_KEY = _load_master_key()
    if _MASTER_KEY is not None:
        _AEAD = AESGCM(_MASTER_KEY)
        _log.info("Envelope encryption ENABLED · algorithm=AES-256-GCM")
    else:
        _log.warning(
            "LATTICE_ENVELOPE_KEY is not set — at-rest encryption DISABLED. "
            "Secrets, mail bodies and chat plaintext will be stored in clear. "
            "This is acceptable only for local development."
        )


def enabled() -> bool:
    _ensure_loaded()
    return _AEAD is not None


def set_master_key(key: bytes) -> None:
    """Install a master key derived at runtime (e.g. Argon2id from a
    passphrase). Overrides any env-loaded key. Used by `secret_manager`."""
    global _MASTER_KEY, _AEAD
    if not isinstance(key, (bytes, bytearray)) or len(key) != 32:
        raise ValueError("master key must be exactly 32 bytes")
    _MASTER_KEY = bytes(key)
    _AEAD = AESGCM(_MASTER_KEY)
    _log.info("Envelope master key installed at runtime (32 bytes)")


def seal(plaintext: bytes, aad: bytes = b"") -> str:
    """Encrypt + base64-encode. Returns `"v1:<b64>"` or the plaintext
    hex prefix `"v0:<hex>"` when encryption is disabled (dev mode)."""
    if not isinstance(plaintext, (bytes, bytearray)):
        raise TypeError("seal() requires bytes")
    _ensure_loaded()
    if _AEAD is None:
        return "v0:" + plaintext.hex()
    nonce = secrets.token_bytes(_NONCE_SIZE)
    ct = _AEAD.encrypt(nonce, bytes(plaintext), aad or None)
    return _VERSION + ":" + base64.b64encode(nonce + ct).decode("ascii")


def open_(token: str, aad: bytes = b"") -> bytes:
    """Decode + decrypt. Accepts both v0 (dev clear) and v1 (AES-GCM) tokens."""
    if not isinstance(token, str) or ":" not in token:
        raise ValueError("envelope token must be 'vN:...' string")
    version, payload = token.split(":", 1)
    if version == "v0":
        return bytes.fromhex(payload)
    if version != _VERSION:
        raise ValueError(f"unknown envelope version: {version}")
    _ensure_loaded()
    if _AEAD is None:
        raise ValueError(
            "cannot open v1 envelope without LATTICE_ENVELOPE_KEY (dev mode "
            "cannot read prod-encrypted data)"
        )
    raw = base64.b64decode(payload)
    nonce, ct = raw[:_NONCE_SIZE], raw[_NONCE_SIZE:]
    return _AEAD.decrypt(nonce, ct, aad or None)


def seal_text(plaintext: str, aad: bytes = b"") -> str:
    return seal(plaintext.encode("utf-8"), aad)


def open_text(token: str, aad: bytes = b"") -> str:
    return open_(token, aad).decode("utf-8")


def seal_hex(hex_value: str, aad: bytes = b"") -> str:
    """Convenience: take a hex string, store as sealed envelope."""
    return seal(bytes.fromhex(hex_value), aad)


def open_hex(token: str, aad: bytes = b"") -> str:
    """Inverse of `seal_hex` — sealed envelope → hex string."""
    return open_(token, aad).hex()


def is_sealed(value: Optional[str]) -> bool:
    """True iff the value looks like an envelope token."""
    return isinstance(value, str) and (value.startswith("v0:") or value.startswith("v1:"))
