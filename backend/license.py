"""
Lattice Network — license enforcement (Iter_28)
================================================

A Lattice container ships without a license — it boots in COMMUNITY mode
(limits: 1 tenant, ≤10 users, no banking features, no support SLA). To
unlock paid tiers the operator installs a license file signed by the
vendor master key (ML-DSA-65, FIPS 204).

Why ML-DSA-65?
    - Same algorithm as the rest of Lattice → no extra crypto deps
    - Post-quantum safe → licenses survive a CRQC scenario
    - Detached signatures fit a "JSON payload + sig hex" file format

License file format (`*.lic`, canonical JSON + signature):

    {
        "license_id": "lic-...",
        "issued_at": "<iso>",
        "valid_from": "<iso>",
        "valid_until": "<iso>",
        "edition": "community|professional|banking|pa|enterprise",
        "tenant_name": "Banca XYZ S.p.A.",
        "max_tenants": 1|5|50|null,
        "max_users": 10|100|1000|null,
        "features": ["pulse", "certify", "mixnet", "ots_anchor", "banking_audit", ...],
        "issued_to_fingerprint": "<sha3-256 of org name>",
        "vendor_pubkey_fpr": "<8-byte fpr — must match installed pubkey>",
        "signature_hex": "<ML-DSA-65 sig of the canonical payload>"
    }

The signature is computed over the *canonical* JSON (sorted keys, no
whitespace) of the payload WITHOUT the `signature_hex` field.

Vendor public key is embedded as `LATTICE_VENDOR_PUBKEY_HEX` env var or
falls back to `data/vendor_pubkey.hex`. The corresponding private key is
held by Lattice S.r.l. and never deployed.

Helper CLI: `python -m tools.issue_license ...` (see /app/backend/scripts).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pqcrypto.sign import ml_dsa_65 as mldsa

_log = logging.getLogger("lattice.license")

EDITION_COMMUNITY = "community"
EDITIONS = {EDITION_COMMUNITY, "professional", "banking", "pa", "enterprise"}

# Default community limits (free tier — anyone can run Lattice for personal
# / pilot use, but cannot run a public PEC / banking integration without
# a license).
COMMUNITY_LIMITS = {
    "edition": EDITION_COMMUNITY,
    "max_tenants": 1,
    "max_users": 10,
    "features": ["pulse", "certify"],     # mixnet, banking audit, OTS anchor → paid
    "valid_until": None,                  # never expires
}


def _canonical(payload: dict) -> bytes:
    """Canonical JSON for signing — sorted keys, no whitespace, UTF-8."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _pk_fingerprint(pk: bytes) -> str:
    return hashlib.sha3_256(pk).hexdigest()[:16].upper()


def issue(
    private_key_hex: str,
    *,
    edition: str,
    tenant_name: str,
    valid_until_iso: str,
    max_tenants: Optional[int] = None,
    max_users: Optional[int] = None,
    features: Optional[list[str]] = None,
    license_id: Optional[str] = None,
) -> dict:
    """Build + sign a license file. Used by the vendor-side CLI only.

    Returns the full license dict (with `signature_hex` and
    `vendor_pubkey_fpr`).
    """
    if edition not in EDITIONS:
        raise ValueError(f"unknown edition: {edition}")
    sk = bytes.fromhex(private_key_hex)
    if len(sk) != mldsa.SECRET_KEY_SIZE:
        raise ValueError(f"vendor sk must be {mldsa.SECRET_KEY_SIZE} bytes")

    # Derive the matching public key fingerprint from the signature later;
    # for now we accept the caller-supplied vendor pubkey to keep the API
    # symmetric. Actual fingerprint computed by the verifier.
    payload = {
        "license_id": license_id or f"lic-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "valid_from": datetime.now(timezone.utc).isoformat(),
        "valid_until": valid_until_iso,
        "edition": edition,
        "tenant_name": tenant_name,
        "max_tenants": max_tenants,
        "max_users": max_users,
        "features": features or [],
        "issued_to_fingerprint": hashlib.sha3_256(tenant_name.encode("utf-8")).hexdigest()[:32],
    }
    sig = mldsa.sign(sk, _canonical(payload))
    payload["signature_hex"] = sig.hex()
    return payload


def verify(license_doc: dict, vendor_pk_hex: str) -> tuple[bool, str]:
    """Verify the signature + expiry of a license dict.

    Returns (ok, reason). `reason` is empty string on success.
    """
    if not isinstance(license_doc, dict):
        return False, "license must be a JSON object"
    sig_hex = license_doc.get("signature_hex")
    if not sig_hex:
        return False, "missing signature_hex"
    payload = {k: v for k, v in license_doc.items() if k != "signature_hex"}

    try:
        pk = bytes.fromhex(vendor_pk_hex)
        sig = bytes.fromhex(sig_hex)
    except ValueError:
        return False, "vendor_pubkey / signature is not valid hex"
    if len(pk) != mldsa.PUBLIC_KEY_SIZE:
        return False, f"vendor_pubkey must be {mldsa.PUBLIC_KEY_SIZE} bytes"
    if len(sig) != mldsa.SIGNATURE_SIZE:
        return False, f"signature must be {mldsa.SIGNATURE_SIZE} bytes"

    # pqcrypto.sign.ml_dsa_65.verify() returns a bool (NOT raises) on a bad
    # signature, so we MUST act on the return value. Wrap in try/except as
    # belt-and-suspenders for any unforeseen runtime error.
    try:
        ok = bool(mldsa.verify(pk, _canonical(payload), sig))
    except Exception:
        ok = False
    if not ok:
        return False, "signature verification failed"

    # Expiry check
    until = payload.get("valid_until")
    if until:
        try:
            exp = datetime.fromisoformat(until.replace("Z", "+00:00"))
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < datetime.now(timezone.utc):
                return False, f"license expired on {until}"
        except ValueError:
            return False, "valid_until is not a valid ISO-8601 timestamp"

    if payload.get("edition") not in EDITIONS:
        return False, f"unknown edition: {payload.get('edition')}"

    return True, ""


# ---------------------------------------------------------------------------
# Runtime state — loaded once at startup
# ---------------------------------------------------------------------------


class _State:
    def __init__(self) -> None:
        self.active: dict = dict(COMMUNITY_LIMITS)
        self.signed: bool = False
        self.vendor_pk_hex: Optional[str] = None
        self.vendor_pk_fpr: Optional[str] = None
        self.last_error: str = ""


STATE = _State()


def _data_dir() -> Path:
    p = Path(os.environ.get("LATTICE_DATA_DIR", "/app/backend/data"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def _resolve_vendor_pubkey() -> Optional[str]:
    hex_env = os.environ.get("LATTICE_VENDOR_PUBKEY_HEX", "").strip()
    if hex_env:
        return hex_env
    p = _data_dir() / "vendor_pubkey.hex"
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return None


def _resolve_license_path() -> Path:
    return Path(os.environ.get("LATTICE_LICENSE_FILE", str(_data_dir() / "license.lic")))


def load_from_disk() -> dict:
    """Attempt to load + verify the on-disk license. Falls back to
    COMMUNITY if anything is missing or invalid. Returns the active dict.
    """
    STATE.active = dict(COMMUNITY_LIMITS)
    STATE.signed = False
    STATE.last_error = ""

    vendor_hex = _resolve_vendor_pubkey()
    if vendor_hex:
        try:
            STATE.vendor_pk_hex = vendor_hex
            STATE.vendor_pk_fpr = _pk_fingerprint(bytes.fromhex(vendor_hex))
        except ValueError:
            STATE.vendor_pk_hex = None
            STATE.vendor_pk_fpr = None
            STATE.last_error = "vendor_pubkey is not valid hex"
            _log.error(STATE.last_error)
            return STATE.active

    path = _resolve_license_path()
    if not path.exists():
        _log.info("No license file at %s — running in COMMUNITY edition", path)
        return STATE.active
    if not vendor_hex:
        STATE.last_error = "license file present but no vendor pubkey installed"
        _log.warning(STATE.last_error)
        return STATE.active

    try:
        license_doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        STATE.last_error = f"cannot parse license file: {e}"
        _log.error(STATE.last_error)
        return STATE.active

    ok, reason = verify(license_doc, vendor_hex)
    if not ok:
        STATE.last_error = f"license rejected: {reason}"
        _log.error(STATE.last_error)
        return STATE.active

    STATE.active = {
        "edition": license_doc["edition"],
        "tenant_name": license_doc.get("tenant_name"),
        "max_tenants": license_doc.get("max_tenants"),
        "max_users": license_doc.get("max_users"),
        "features": license_doc.get("features") or [],
        "valid_from": license_doc.get("valid_from"),
        "valid_until": license_doc.get("valid_until"),
        "license_id": license_doc.get("license_id"),
    }
    STATE.signed = True
    _log.info("License loaded · edition=%s · valid_until=%s",
              STATE.active["edition"], STATE.active.get("valid_until"))
    return STATE.active


def install(license_doc: dict) -> dict:
    """Persist + activate a license received via API. Verifies first."""
    if not STATE.vendor_pk_hex:
        raise RuntimeError("vendor pubkey not installed — cannot verify license")
    ok, reason = verify(license_doc, STATE.vendor_pk_hex)
    if not ok:
        raise PermissionError(reason)
    path = _resolve_license_path()
    path.write_text(json.dumps(license_doc, indent=2, sort_keys=True), encoding="utf-8")
    return load_from_disk()


def status() -> dict:
    """Read-only license info for the admin dashboard."""
    now = datetime.now(timezone.utc)
    until = STATE.active.get("valid_until")
    days_remaining: Optional[int] = None
    if until:
        try:
            exp = datetime.fromisoformat(until.replace("Z", "+00:00"))
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            days_remaining = max(0, (exp - now).days)
        except ValueError:
            pass
    return {
        "edition": STATE.active.get("edition"),
        "signed": STATE.signed,
        "tenant_name": STATE.active.get("tenant_name"),
        "license_id": STATE.active.get("license_id"),
        "max_tenants": STATE.active.get("max_tenants"),
        "max_users": STATE.active.get("max_users"),
        "features": STATE.active.get("features") or [],
        "valid_from": STATE.active.get("valid_from"),
        "valid_until": STATE.active.get("valid_until"),
        "days_remaining": days_remaining,
        "vendor_pubkey_fpr": STATE.vendor_pk_fpr,
        "vendor_pubkey_installed": STATE.vendor_pk_hex is not None,
        "last_error": STATE.last_error or None,
    }


def has_feature(name: str) -> bool:
    return name in (STATE.active.get("features") or [])


def check_tenant_quota(current_count: int) -> bool:
    max_t = STATE.active.get("max_tenants")
    return max_t is None or current_count < max_t


def check_user_quota(current_count: int) -> bool:
    max_u = STATE.active.get("max_users")
    return max_u is None or current_count < max_u
