"""
Lattice Network — Sovereign Admin Console backend.

FastAPI service that mirrors the on-premise Rust workspace
(lattice-crypto / lattice-node / pulse-protocol / certify-gateway /
lattice-admin-console) by exposing the ledger state, QBFT validator
fleet, LNS registry and Certify NotaryTX counters to the
React/TypeScript "Sovereign Gold & Dark Slate" console.

All data is served from MongoDB; the database is auto-seeded on
startup with a deterministic but realistic enterprise dataset.
"""
from __future__ import annotations

import asyncio
import time
import csv
import hashlib
import io
import json
import logging
import os
import random
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Annotated, Any, AsyncIterator, Dict, List, Literal, Optional, Tuple

# CRITICAL: load .env BEFORE any module-level import that reads env vars at
# import time (e.g. auth_state.JWT_SECRET, envelope keys). Without this the
# server boots with the default dev secret while .env carries the real one,
# silently rejecting valid JWTs and reverting tenant employees to anonymous.
from dotenv import load_dotenv  # noqa: E402
load_dotenv(Path(__file__).parent / ".env")

from bson import ObjectId
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import Response, StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pqcrypto.sign import ml_dsa_65 as mldsa
import envelope  # noqa: E402  — at-rest encryption for sk_hex / mail body / pulse plaintext
import secret_manager  # noqa: E402 — passphrase-based master key management
import license as licmod  # noqa: E402 — ML-DSA signed license enforcement
import ots_anchor  # noqa: E402 — OpenTimestamps Bitcoin anchor (opt-in)
import core  # noqa: E402 — pure helpers + PQC keystore (Iter_32)
import chain  # noqa: E402 — block construction + QBFT finalisation (Iter_34)
from routes import (  # noqa: E402 — modular admin routes (Iter_29/30/32/33/34)
    ots as ots_routes,
    secrets as secrets_routes,
    license_admin as license_routes,
    admin_health as health_routes,
    backup as backup_routes,
    lns as lns_routes,
    qbft as qbft_routes,
    certify as certify_routes,
    pulse as pulse_routes,
    tenants as tenants_routes,
    keyrecovery as keyrecovery_routes,
    auth as auth_routes,
    audit_public as audit_public_routes,
    certify_mutating as certify_mutating_routes,
    pulse_mutating as pulse_mutating_routes,
    leads as leads_routes,
    attachments as attachments_routes,
    pec_webhook as pec_webhook_routes,
    vendor_rln as vendor_rln_routes,
    ledger_public as ledger_public_routes,
    explorer as explorer_routes,
)
import audit  # noqa: E402  — append-only hash-chained audit log
import shamir  # noqa: E402  — 2-of-3 secret sharing for keypair recovery
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from starlette.middleware.cors import CORSMiddleware


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).parent
# load_dotenv already executed above — kept here for backwards reference only.

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

# Iter_32: wire the shared core helpers module to the live db handle so
# routes/*.py can import it without circular dependency on server.py.
core.init(db)
chain.init(db)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
)
log = logging.getLogger("lattice.admin")

app = FastAPI(title="Lattice Network — Admin Console API", version="0.1.0")
api = APIRouter(prefix="/api")

# M8 finale — proxy paths now served by the Rust gateway (port 8002) to
# bypass the legacy FastAPI handlers transparently for the frontend.
from rust_proxy import RustGatewayProxy  # noqa: E402
app.add_middleware(RustGatewayProxy)


# ---------------------------------------------------------------------------
# Mongo-friendly base
# ---------------------------------------------------------------------------
def _coerce_object_id(v: Any) -> str:
    if isinstance(v, ObjectId):
        return str(v)
    return v


PyObjectId = Annotated[str, BeforeValidator(_coerce_object_id)]


# ---------------------------------------------------------------------------
# RBAC — three roles enforced via X-Lattice-Role header.
#   sovereign · tenant admin · full read/write, sees Pulse plaintext
#   auditor   · read-only    · sees TX/blocks/verify, NO plaintext bodies
#   vendor    · MSP partner  · metadata only, no LNS identities, no content
# ---------------------------------------------------------------------------
from fastapi import Header  # noqa: E402

ROLE_SOVEREIGN = "sovereign"
ROLE_AUDITOR = "auditor"
ROLE_VENDOR = "vendor"
ALL_ROLES = {ROLE_SOVEREIGN, ROLE_AUDITOR, ROLE_VENDOR}

# Strict mode (production): when enabled, requests WITHOUT a valid JWT are
# rejected (no more "X-Lattice-Role" header fallback). Set
# LATTICE_STRICT_AUTH=1 in production. Default false for local dev.
STRICT_AUTH = os.environ.get("LATTICE_STRICT_AUTH", "0").strip().lower() in ("1", "true", "yes", "on")

# Compliance mode — when enabled the mixnet anonymisation layer is bypassed
# for Pulse/Certify routing, and every transaction includes a full forensic
# trail (sender IP, validator path, complete metadata). Default ON for
# enterprise sales: banks/PA/legal sectors require traceability, not anonymity.
# Set LATTICE_COMPLIANCE_MODE=0 to enable mixnet (whistleblowing edition).
COMPLIANCE_MODE = os.environ.get("LATTICE_COMPLIANCE_MODE", "1").strip().lower() in ("1", "true", "yes", "on")
MIXNET_ENABLED = not COMPLIANCE_MODE


def _resolve_role(header_value: Optional[str]) -> str:
    """Return the validated role from the X-Lattice-Role header.

    In STRICT_AUTH mode the header is no longer trusted: any call that
    reaches this function without a JWT is rejected. In dev mode the
    legacy header maps to a role (defaulting to sovereign for back-compat
    with the operator console). Tests rely on this in dev only.
    """
    if STRICT_AUTH:
        raise HTTPException(status_code=401, detail="authentication required (JWT)")
    if not header_value:
        return ROLE_SOVEREIGN
    candidate = header_value.strip().lower()
    if candidate not in ALL_ROLES:
        return ROLE_SOVEREIGN
    return candidate


async def role_dep(x_lattice_role: Optional[str] = Header(default=None)) -> str:
    """FastAPI dependency that resolves the caller's role."""
    return _resolve_role(x_lattice_role)


def require_roles(*allowed: str):
    """Build a dependency that 403s unless the caller's role is in *allowed*.

    Resolves the role from the JWT (`Authorization: Bearer ...`) when
    present, falling back to the legacy `X-Lattice-Role` header. Tenant
    roles `admin` and `operator` are mapped to the console RBAC tiers:
    `admin` → sovereign, `operator` → auditor (read-only at gateway).
    """
    allowed_set = set(allowed)

    async def _dep(
        authorization: Optional[str] = Header(default=None),
        x_lattice_role: Optional[str] = Header(default=None),
    ) -> str:
        role = None
        # 1) JWT first
        if authorization and authorization.lower().startswith("bearer "):
            payload = _decode_jwt(authorization.split(None, 1)[1].strip())
            if payload:
                raw = (payload.get("role") or "").lower()
                # Map tenant roles to gateway RBAC tiers.
                role = {
                    "admin": ROLE_SOVEREIGN,
                    "operator": ROLE_AUDITOR,  # operators can read but not mutate registry
                    "auditor": ROLE_AUDITOR,
                    "vendor": ROLE_VENDOR,
                    "sovereign": ROLE_SOVEREIGN,
                }.get(raw, ROLE_AUDITOR)
        if role is None:
            role = _resolve_role(x_lattice_role)
        if role not in allowed_set:
            raise HTTPException(
                status_code=403,
                detail=f"role '{role}' is not allowed here · allowed: {sorted(allowed_set)}",
            )
        return role

    return _dep


def require_platform_sovereign():
    """Allow only the platform operator (Fabio).

    Platform operator = sovereign role AND **no tenant_id** bound to the JWT
    (or no JWT at all = legacy admin console). Tenant admins (who have a
    `tenant_id` in their JWT) are blocked — they only own their own workspace.
    """
    async def _dep(
        authorization: Optional[str] = Header(default=None),
        x_lattice_role: Optional[str] = Header(default=None),
    ) -> dict:
        if authorization and authorization.lower().startswith("bearer "):
            payload = _decode_jwt(authorization.split(None, 1)[1].strip())
            if payload:
                raw = (payload.get("role") or "").lower()
                tenant_id = payload.get("tenant_id")
                # Tenant admins map to "sovereign" inside their tenant but
                # MUST NOT see platform-level data (other tenants, leads).
                if tenant_id:
                    raise HTTPException(
                        status_code=403,
                        detail="platform-sovereign only · this resource is restricted to the network operator",
                    )
                if raw not in ("sovereign", "admin"):
                    raise HTTPException(status_code=403, detail="platform-sovereign role required")
                return {"role": ROLE_SOVEREIGN, "lns": payload.get("sub"), "tenant_id": None}
        # Legacy header / anonymous: treat as platform admin (dev console).
        role = _resolve_role(x_lattice_role)
        if role != ROLE_SOVEREIGN:
            raise HTTPException(status_code=403, detail="platform-sovereign role required")
        return {"role": role, "lns": None, "tenant_id": None}

    return _dep


def require_tenant_member(tenant_id_param: str = "tenant_id"):
    """Allow either the platform operator OR any authenticated member of
    the specified tenant. Returns the resolved `current_user` dict.
    """
    async def _dep(
        tenant_id: str,
        authorization: Optional[str] = Header(default=None),
        x_lattice_role: Optional[str] = Header(default=None),
    ) -> dict:
        # Platform operator path (no JWT or JWT without tenant_id)
        if authorization and authorization.lower().startswith("bearer "):
            payload = _decode_jwt(authorization.split(None, 1)[1].strip())
            if payload:
                caller_tenant = payload.get("tenant_id")
                if caller_tenant is None:
                    return {"role": ROLE_SOVEREIGN, "lns": payload.get("sub"), "tenant_id": None}
                if caller_tenant == tenant_id:
                    return {
                        "role": (payload.get("role") or "operator"),
                        "lns": payload.get("sub"),
                        "tenant_id": caller_tenant,
                    }
                raise HTTPException(status_code=403, detail="cross-tenant access forbidden")
        # Legacy header (dev): allow as platform operator
        role = _resolve_role(x_lattice_role)
        if role == ROLE_SOVEREIGN:
            return {"role": role, "lns": None, "tenant_id": None}
        raise HTTPException(status_code=401, detail="authentication required")

    return _dep


def _redact_for_role(role: str, kind: str, payload):
    """Field-level redaction depending on caller's role.

    *kind* selects which redaction table to apply:
      - "pulse_message" hides plaintext for auditor/vendor
      - "certify_mail" hides body & subject for vendor
      - "lns"           hides full key for vendor

    Always unseals envelope-encrypted fields (`body`, `plaintext`) before
    applying role-based redaction, so authorised callers see the real
    content while sovereign sees everything in clear.
    """
    if not isinstance(payload, list):
        targets = [payload]
        single = True
    else:
        targets = payload
        single = False

    def _scrub(item: dict) -> dict:
        out = dict(item)
        # Unseal at-rest envelope fields BEFORE any role-based redaction.
        if kind == "pulse_message":
            pt = out.get("plaintext")
            if envelope.is_sealed(pt):
                try:
                    out["plaintext"] = envelope.open_text(pt, aad=out.get("msg_id", "").encode())
                except Exception:
                    out["plaintext"] = None
            if role in (ROLE_AUDITOR, ROLE_VENDOR):
                if "plaintext" in out and out["plaintext"]:
                    out["plaintext"] = None
                    out["redacted"] = True
        elif kind == "certify_mail":
            body = out.get("body")
            if out.get("is_e2e_encrypted"):
                # End-to-end encrypted — server CANNOT decrypt. The recipient's
                # browser will decrypt using their X25519 secret key, via the
                # body_e2e_envelope blob (already returned alongside `body`).
                pass
            elif envelope.is_sealed(body):
                try:
                    out["body"] = envelope.open_text(body, aad=out.get("mail_id", "").encode())
                except Exception:
                    out["body"] = None
            if role == ROLE_VENDOR:
                out["body"] = None
                out["subject"] = "[redacted-by-rbac]"
                out["subject_redacted"] = "[redacted-by-rbac]"
                out["redacted"] = True
            elif role == ROLE_AUDITOR:
                # auditor: keep subject, hide body
                out["body"] = None
                out["redacted"] = True
        elif kind == "lns":
            if role == ROLE_VENDOR:
                out["did"] = "did:lattice:[redacted]"
                out["public_key_fingerprint"] = "[redacted]"
                out["redacted"] = True
        return out

    redacted = [_scrub(t) for t in targets]
    return redacted[0] if single else redacted


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# PQC Challenge-Response authentication + JWT sessions
# ---------------------------------------------------------------------------
# 1. /api/auth/challenge issues a fresh 32-byte random nonce (stored with 2-min
#    TTL) for a target LNS. 2. Client signs the nonce with its ML-DSA-65 secret
#    key (real, client-side, never touches the wire). 3. /api/auth/verify
#    verifies the signature against the LNS's stored public key and issues a
#    JWT containing {lns, tenant_id, role, exp}. The console then sends
#    `Authorization: Bearer <jwt>` on every subsequent call. RBAC enforcement
#    derives the role from the JWT (not from the legacy X-Lattice-Role header).
import jwt as _pyjwt  # noqa: E402

import auth_state  # noqa: E402 — JWT helpers (Iter_37)

JWT_SECRET = auth_state.JWT_SECRET
JWT_ALG = auth_state.JWT_ALG
JWT_TTL_SECONDS = auth_state.JWT_TTL_SECONDS
CHALLENGE_TTL_SECONDS = auth_state.CHALLENGE_TTL_SECONDS


def _issue_jwt(lns: str, tenant_id: Optional[str], role: str) -> str:
    return auth_state.issue_jwt(lns, tenant_id, role)


def _decode_jwt(token: str) -> Optional[dict]:
    return auth_state.decode_jwt(token)


async def _is_jwt_revoked(payload: dict) -> bool:
    return await auth_state.is_jwt_revoked(db, payload)


async def current_user(
    authorization: Optional[str] = Header(default=None),
    x_lattice_role: Optional[str] = Header(default=None),
) -> dict:
    """Resolve the caller's identity.

    Order: 1) `Authorization: Bearer <jwt>` (real PQC login) →
    2) legacy `X-Lattice-Role` header (dev/admin console) →
    3) anonymous default sovereign.
    """
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(None, 1)[1].strip()
        payload = _decode_jwt(token)
        if payload:
            if await _is_jwt_revoked(payload):
                raise HTTPException(status_code=401, detail="session revoked — please log in again")
            return {
                "lns": payload.get("sub"),
                "tenant_id": payload.get("tenant_id"),
                "role": payload.get("role") or ROLE_SOVEREIGN,
                "via": "pqc-jwt",
                "jti": payload.get("jti"),
            }
    return {
        "lns": None,
        "tenant_id": None,
        "role": _resolve_role(x_lattice_role),
        "via": "header" if x_lattice_role else "default",
    }





# ---------------------------------------------------------------------------
# Real Post-Quantum Cryptography (NIST FIPS 204 · ML-DSA-65)
# ---------------------------------------------------------------------------
# We keep secret keys in MongoDB (`keystore` collection). In a real sovereign
# deployment they would live in an HSM / Secure Enclave — here we cache them
# in-process for speed and accept the loss of strict secrecy because the
# whole point is to demonstrate verifiable PQC signatures on a single tenant.
_KEY_CACHE: dict[str, tuple[bytes, bytes]] = {}  # entity -> (pk, sk)
PQC_ALGORITHM = "ML-DSA-65"
PQC_PK_SIZE = mldsa.PUBLIC_KEY_SIZE
PQC_SK_SIZE = mldsa.SECRET_KEY_SIZE
PQC_SIG_SIZE = mldsa.SIGNATURE_SIZE


def _pk_fingerprint(pk: bytes) -> str:
    """8-byte SHA3-256 fingerprint of a public key, uppercase hex."""
    return hashlib.sha3_256(pk).hexdigest()[:32].upper()


async def _get_or_create_keypair(entity: str, role: str = "lns") -> tuple[bytes, bytes]:
    """Return the (pk, sk) tuple for *entity*, materialising it on first use.

    The secret key is sealed with the at-rest envelope key when stored in
    Mongo. Backwards compatible with legacy plaintext `sk_hex` documents
    (auto-upgraded to envelope on next write).
    """
    if entity in _KEY_CACHE:
        return _KEY_CACHE[entity]
    doc = await db.keystore.find_one({"entity": entity})
    if doc:
        pk = bytes.fromhex(doc["pk_hex"])
        sk_field = doc.get("sk")  # new sealed field
        if sk_field:
            sk = bytes.fromhex(envelope.open_hex(sk_field, aad=entity.encode()))
        else:
            # Legacy plaintext sk_hex — read once, seal on next save.
            sk = bytes.fromhex(doc["sk_hex"])
    else:
        pk, sk = mldsa.generate_keypair()
        await db.keystore.insert_one({
            "entity": entity,
            "role": role,
            "pk_hex": pk.hex(),
            "sk": envelope.seal_hex(sk.hex(), aad=entity.encode()),
            "fingerprint": _pk_fingerprint(pk),
            "created_at": _utc_iso(),
            "algorithm": PQC_ALGORITHM,
        })
    _KEY_CACHE[entity] = (pk, sk)
    return pk, sk


async def _pqc_sign(entity: str, message: bytes, role: str = "lns") -> tuple[str, str]:
    """Real ML-DSA-65 detached signature. Returns (signature_hex, public_key_fingerprint)."""
    pk, sk = await _get_or_create_keypair(entity, role)
    sig = mldsa.sign(sk, message)
    return sig.hex(), _pk_fingerprint(pk)


async def _pqc_sign_or_delegate(
    entity: str,
    message: bytes,
    *,
    tenant_id: str | None = None,
    gateway_prefix: str = "CERTIFY-GATEWAY",
    role: str = "lns",
) -> tuple[str, str, str]:
    """Sign *message* on behalf of *entity*.

    If the backend holds the sealed SK of *entity* (admins / platform / legacy
    seed accounts) the signature is produced under the user's own key
    (`signer_entity == entity`). For tenant employees whose keypair lives
    exclusively in the browser (only `pk_hex` is persisted server-side), the
    signature is produced under a per-tenant gateway key
    (`{gateway_prefix}-{tenant_id}`) auto-materialised on first use. This is
    the same trust model as a PEC provider: the gateway notarises on behalf
    of the user, while audit trail (`delegated_for`) still names the user.

    Returns (signature_hex, public_key_fingerprint, actual_signer_entity).
    """
    doc = await db.keystore.find_one({"entity": entity}, {"sk": 1, "sk_hex": 1})
    if doc and (doc.get("sk") or doc.get("sk_hex")):
        sig_hex, fp = await _pqc_sign(entity, message, role=role)
        return sig_hex, fp, entity
    # Fallback: per-tenant gateway delegation.
    gw_entity = f"{gateway_prefix}-{tenant_id}" if tenant_id else gateway_prefix
    sig_hex, fp = await _pqc_sign(gw_entity, message, role="gateway")
    return sig_hex, fp, gw_entity


async def _pqc_verify(entity: str, message: bytes, signature_hex: str) -> bool:
    """Real ML-DSA-65 detached verification."""
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


def _tx_canonical_message(tx: dict) -> bytes:
    """Iter_34: moved to chain.tx_canonical_message."""
    return chain.tx_canonical_message(tx)


def _block_canonical_message(block: dict) -> bytes:
    """Iter_34: moved to chain.block_canonical_message."""
    return chain.block_canonical_message(block)


CHAIN_ID = chain.CHAIN_ID


def _merkle_root(tx_hashes: list[str]) -> str:
    """Iter_34: moved to chain.merkle_root."""
    return chain.merkle_root(tx_hashes)


def _tx_leaf_hash(tx_id: str, kind: str, doc_hash: str = "", signer: str = "", ts: str = "") -> str:
    """Iter_34: moved to chain.tx_leaf_hash."""
    return chain.tx_leaf_hash(tx_id, kind, doc_hash, signer, ts)


def _compute_block_hash(*, chain_id: str, index: int, timestamp: str, previous_hash: str, merkle_root: str, transactions_count: int) -> str:
    """Iter_34: moved to chain.compute_block_hash."""
    return chain.compute_block_hash(
        chain_id=chain_id, index=index, timestamp=timestamp,
        previous_hash=previous_hash, merkle_root_hex=merkle_root,
        transactions_count=transactions_count,
    )


def _build_signed_block(*, index: int, timestamp: str, previous_hash: str, transactions: list[dict]) -> dict:
    """Iter_34: moved to chain.build_signed_block."""
    return chain.build_signed_block(
        index=index, timestamp=timestamp, previous_hash=previous_hash,
        transactions=transactions,
    )


async def _finalise_block_for_tx(
    *,
    index: int,
    timestamp: str,
    tx_id: str,
    kind: str,
    doc_hash: str = "",
    signer: str = "",
) -> dict:
    """Iter_34: moved to chain.finalise_block_for_tx."""
    return await chain.finalise_block_for_tx(
        index=index, timestamp=timestamp,
        tx_id=tx_id, kind=kind, doc_hash=doc_hash, signer=signer,
    )


async def _finalise_batch_block(*, transactions: List[dict]) -> dict:
    """Iter_34: moved to chain.finalise_batch_block."""
    return await chain.finalise_batch_block(transactions=transactions)


_BLOCK_PROPOSAL_LOCK = chain.BLOCK_PROPOSAL_LOCK


# ---------------------------------------------------------------------------
# QBFT — real 4-process Byzantine consensus
# ---------------------------------------------------------------------------
# The 4 validators run as independent OS processes on ports 9001..9004
# (see /etc/supervisor/conf.d/lattice_qbft.conf).
import httpx  # noqa: E402

QBFT_TIMEOUT_S = chain.QBFT_TIMEOUT_S
QBFT_QUORUM = chain.QBFT_QUORUM


async def _qbft_known_validators() -> list[dict]:
    return await core.qbft_known_validators()


def _db_qbft_registry():
    return db.qbft_registry


async def qbft_finalise(block_doc: dict) -> dict:
    """Iter_34: moved to chain.qbft_finalise."""
    return await chain.qbft_finalise(block_doc)


# ---------------------------------------------------------------------------
# Pydantic models — wire format
# ---------------------------------------------------------------------------
# Iter_32: moved to /app/backend/models.py. Wildcard re-export keeps
# all the symbols (LedgerStats, Block, …, AlertWebhook) visible to the
# rest of server.py and to existing imports.
from models import *  # noqa: E402,F401,F403


# AlertWebhook is also imported above via `from models import *` but we
# keep a local rebind so the (legacy) inline `class AlertWebhook` block
# previously declared at line ~1479 no longer needs to live in server.py.


# ---------------------------------------------------------------------------
# Deterministic seeding
# ---------------------------------------------------------------------------
DEPARTMENTS = ["Executive", "Finance", "Legal", "R&D", "Operations", "Compliance", "Security", "HR"]
REGIONS = ["Milano-DC1", "Roma-DC1", "Frankfurt-DC2", "Paris-DC1", "Zurich-DC3"]
MIXNET_RELAYS_SEED = [
    ("MIX-A1", 0, "Milano-DC1", 14),
    ("MIX-A2", 0, "Roma-DC1", 21),
    ("MIX-A3", 0, "Frankfurt-DC2", 28),
    ("MIX-B1", 1, "Paris-DC1", 19),
    ("MIX-B2", 1, "Zurich-DC3", 23),
    ("MIX-B3", 1, "Milano-DC1", 17),
    ("MIX-C1", 2, "Frankfurt-DC2", 25),
    ("MIX-C2", 2, "Roma-DC1", 22),
    ("MIX-C3", 2, "Zurich-DC3", 27),
]
RLN_EPOCH_SECONDS = 60
RLN_MAX_PER_EPOCH = 10
PULSE_ANCHOR_EVERY = 3
NODE_LABELS = [
    ("VAL-01", "proposer"),
    ("VAL-02", "validator"),
    ("VAL-03", "validator"),
    ("VAL-04", "validator"),
]
FIRST_NAMES = ["marco", "giulia", "luca", "chiara", "alessandro", "francesca", "matteo", "elena", "andrea", "sara"]
LAST_NAMES = ["rossi", "bianchi", "ferrari", "romano", "esposito", "gallo", "conti", "ricci", "marino", "greco"]


def _hex(n: int) -> str:
    return secrets.token_hex(n)


def _det_hex(seed: str, n: int) -> str:
    h = hashlib.sha3_512(seed.encode()).hexdigest()
    return h[: n * 2]


async def _seed_if_empty() -> None:
    """Initialize a CLEAN sovereign ledger on first boot.

    NO fake data. Only:
      * QBFT validator registry (infrastructure — 4 real processes)
      * Mixnet relay topology (infrastructure — 3 real processes)
      * Genesis block (index 0, empty, real SHA3-512 hash)
      * Meta record with block_height=0, tx_total=0
    Everything else (LNS, tenants, certify mails, leads, pulse messages)
    starts empty and is populated only by real user actions.
    """
    if await db.meta.find_one({"_id": "seeded"}):
        log.info("Database already initialised — skipping.")
        return

    log.info("Initialising clean sovereign ledger (genesis only)…")
    now = datetime.now(timezone.utc)

    # ----- QBFT validator infrastructure (real processes, real PQC keys) -----
    nodes = []
    for i, (label, role) in enumerate(NODE_LABELS):
        nodes.append({
            "node_id": f"node-{_det_hex(label, 6)}",
            "label": label,
            "region": REGIONS[i % len(REGIONS)],
            "role": role,
            "status": "ONLINE",
            "voting_power": 100 if role != "observer" else 0,
            "blocks_proposed": 0,
            "last_seen": now.isoformat(),
            "cpu_pct": 0.0,
            "mem_pct": 0.0,
            "version": "lattice-node 0.1.0",
        })
    if await db.qbft_nodes.count_documents({}) == 0:
        await db.qbft_nodes.insert_many(nodes)

    # ----- Mixnet relays (Loopix topology) -----
    mix_relays = []
    for (label, layer, region, lat) in MIXNET_RELAYS_SEED:
        mix_relays.append({
            "node_id": f"mix-{_det_hex(label, 6)}",
            "label": label,
            "region": region,
            "layer": layer,
            "kem_pk_fingerprint": _det_hex(f"mix-pk-{label}", 8).upper(),
            "latency_ms": lat,
        })
    if await db.mixnet_relays.count_documents({}) == 0:
        await db.mixnet_relays.insert_many(mix_relays)

    # ----- Genesis block (index 0) — chain-bound SHA3-512 with merkle root
    ts = now.isoformat()
    genesis_merkle = "0" * 64  # empty TX set
    genesis_hash = _compute_block_hash(
        chain_id=CHAIN_ID, index=0, timestamp=ts,
        previous_hash="0" * 128, merkle_root=genesis_merkle, transactions_count=0,
    )
    genesis = {
        "chain_id": CHAIN_ID,
        "index": 0,
        "timestamp": ts,
        "transactions_count": 0,
        "merkle_root": genesis_merkle,
        "tx_ids": [],
        "previous_hash": "0" * 128,
        "block_hash": genesis_hash,
        "proposer": "GENESIS",
        "signed_with": "GENESIS",
        "qbft_quorum": 0,
        "qbft_total_validators": 0,
        "qbft_votes": [],
    }
    await db.blocks.insert_one(genesis)

    # ----- Meta -----
    await db.meta.insert_one({
        "_id": "seeded",
        "block_height": 0,
        "tx_total": 0,
        "notary_total_seed": 0,
        "qbft_round": 0,
        "seeded_at": ts,
        "chain_id": "lattice-sovereign-it-prod",
        "genesis_hash": genesis_hash,
    })
    log.info(
        "Clean chain initialised — genesis=%s qbft_validators=%d mixnet_relays=%d",
        genesis_hash[:16], len(nodes), len(mix_relays),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@api.get("/")
async def root() -> dict:
    return {
        "service": "Lattice Network · Admin Console",
        "version": "0.1.0",
        "chain": "lattice-sovereign-it-prod",
    }


# ---------------------------------------------------------------------------
# Book downloads — Content-Disposition: attachment forza il download
# ---------------------------------------------------------------------------
from fastapi.responses import FileResponse as _FileResp
import os as _os

_BOOK_DIR = "/app/memory"

@api.get("/book/pdf")
async def book_pdf_download():
    """Scarica il libro completo in PDF (forza download)."""
    path = _os.path.join(_BOOK_DIR, "LATTICE_LIBRO_COMPLETO.pdf")
    return _FileResp(
        path, media_type="application/pdf",
        filename="LATTICE_LIBRO_COMPLETO.pdf",
        headers={"Content-Disposition": 'attachment; filename="LATTICE_LIBRO_COMPLETO.pdf"',
                 "Cache-Control": "no-store"},
    )

@api.get("/book/docx")
async def book_docx_download():
    """Scarica il libro completo in Word (forza download)."""
    path = _os.path.join(_BOOK_DIR, "LATTICE_LIBRO_COMPLETO.docx")
    return _FileResp(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="LATTICE_LIBRO_COMPLETO.docx",
        headers={"Content-Disposition": 'attachment; filename="LATTICE_LIBRO_COMPLETO.docx"',
                 "Cache-Control": "no-store"},
    )

@api.get("/book/zip")
async def book_zip_download():
    """Scarica il pacchetto completo (libro + sorgenti + immagini)."""
    path = _os.path.join(_BOOK_DIR, "LATTICE_LIBRO_PACCHETTO_COMPLETO.zip")
    return _FileResp(
        path, media_type="application/zip",
        filename="LATTICE_LIBRO_PACCHETTO_COMPLETO.zip",
        headers={"Content-Disposition": 'attachment; filename="LATTICE_LIBRO_PACCHETTO_COMPLETO.zip"',
                 "Cache-Control": "no-store"},
    )






# ---------------------------------------------------------------------------
# Alert webhooks (Slack/Telegram/generic JSON) for QBFT + Mixnet health
# ---------------------------------------------------------------------------
# AlertWebhook model is imported via `from models import *` above.


@api.get("/alerts/webhooks")
async def list_alert_webhooks(
    _u: dict = Depends(require_platform_sovereign()),
) -> dict:
    rows = []
    async for w in db.alert_webhooks.find({}, {"_id": 0}):
        rows.append(w)
    return {"items": rows, "total": len(rows)}


@api.post("/alerts/webhooks")
async def add_alert_webhook(
    body: AlertWebhook,
    _u: dict = Depends(require_platform_sovereign()),
) -> dict:
    doc = body.model_dump()
    doc["created_at"] = _utc_iso()
    doc["last_fired_at"] = None
    doc["fire_count"] = 0
    await db.alert_webhooks.replace_one({"url": body.url}, doc, upsert=True)
    return {"ok": True, "url": body.url}


@api.delete("/alerts/webhooks")
async def delete_alert_webhook(
    url: str = Query(..., min_length=8),
    _u: dict = Depends(require_platform_sovereign()),
) -> dict:
    r = await db.alert_webhooks.delete_one({"url": url})
    return {"ok": True, "deleted": r.deleted_count}


@api.post("/alerts/test-fire")
async def test_alert_webhook(
    body: dict,
    _u: dict = Depends(require_platform_sovereign()),
) -> dict:
    """Send a synthetic alert through one webhook for testing."""
    w = await db.alert_webhooks.find_one({"url": body.get("url")}, {"_id": 0})
    if not w:
        raise HTTPException(status_code=404, detail="webhook not registered")
    msg = body.get("message") or "Test alert · Lattice Network is alive ✅"
    ok = await _fire_alert_webhook(w, [{
        "severity": "warning", "kind": "test_fire",
        "subject": "test", "detail": msg,
    }])
    return {"ok": ok}


async def _fire_alert_webhook(w: dict, alerts: list) -> bool:
    """Fire a list of alerts to a single webhook channel. Returns True on
    HTTP 2xx. Never raises — errors are logged and counted."""
    try:
        if w.get("severity_filter") == "critical_only":
            alerts = [a for a in alerts if a.get("severity") == "critical"]
        if not alerts:
            return True
        body, headers = _format_alert_payload(w, alerts)
        async with httpx.AsyncClient(timeout=5.0) as cx:
            r = await cx.post(w["url"], json=body, headers=headers)
        await db.alert_webhooks.update_one(
            {"url": w["url"]},
            {"$set": {"last_fired_at": _utc_iso()}, "$inc": {"fire_count": 1}},
        )
        return r.status_code < 300
    except Exception as e:  # pragma: no cover — never crash on a misconfigured hook
        log.warning("alert webhook %s failed: %s", w.get("url"), e)
        return False


def _format_alert_payload(w: dict, alerts: list) -> tuple[dict, dict]:
    """Render alerts in the right shape for each channel.

    * Slack: `{ "text": "..." }` plain webhook
    * Telegram: `{ "chat_id": ..., "text": ..., "parse_mode": "Markdown" }`
      (requires `extra.chat_id` set on the webhook record). URL must be
      the Telegram Bot API `sendMessage` endpoint.
    * Generic: a plain JSON envelope our customers can pipe anywhere.
    """
    severity_emoji = {"critical": "🚨", "warning": "⚠️"}
    lines = []
    for a in alerts:
        emo = severity_emoji.get(a.get("severity"), "•")
        lines.append(f"{emo} [{a.get('severity','info').upper()}] {a.get('subject')}: {a.get('detail')}")
    text = "*Lattice Network · alert*\n" + "\n".join(lines)
    headers = {"Content-Type": "application/json"}
    if w["kind"] == "slack":
        return {"text": text}, headers
    if w["kind"] == "telegram":
        extra = w.get("extra") or {}
        chat_id = extra.get("chat_id")
        if not chat_id:
            raise RuntimeError("telegram webhook missing extra.chat_id")
        return {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, headers
    # generic
    return {
        "source": "lattice-network",
        "label": w.get("label"),
        "alerts": alerts,
        "rendered": text,
        "fired_at": _utc_iso(),
    }, headers


# Track which alert "fingerprints" have already been notified so we don't
# spam channels every 30s. Cleared when an alert clears.
_alert_state: Dict[str, str] = {}


async def _infra_health_loop() -> None:
    """Background coroutine: every 30s, snapshot qbft+mixnet, fire alerts
    on STATE CHANGE (degrade → critical, or back to ok)."""
    interval = float(os.environ.get("LATTICE_ALERT_INTERVAL_SEC", "30"))
    while True:
        try:
            await asyncio.sleep(interval)
            snapshot = await qbft_routes.qbft_alerts(db)
            new_alerts = snapshot.get("alerts", [])
            new_keys = {f"{a['kind']}:{a['subject']}" for a in new_alerts}
            old_keys = set(_alert_state.keys())
            firing = [a for a in new_alerts if f"{a['kind']}:{a['subject']}" not in old_keys]
            cleared = old_keys - new_keys
            if firing:
                async for w in db.alert_webhooks.find({"enabled": True}, {"_id": 0}):
                    await _fire_alert_webhook(w, firing)
            if cleared:
                clear_alerts = [{
                    "severity": "info", "kind": "cleared",
                    "subject": k, "detail": f"{k} is back to ONLINE",
                } for k in cleared]
                async for w in db.alert_webhooks.find({"enabled": True, "severity_filter": "all"}, {"_id": 0}):
                    await _fire_alert_webhook(w, clear_alerts)
            _alert_state.clear()
            for a in new_alerts:
                _alert_state[f"{a['kind']}:{a['subject']}"] = a["severity"]
        except asyncio.CancelledError:
            return
        except Exception as e:  # pragma: no cover
            log.warning("infra health loop tick failed: %s", e)


@api.get("/lns", response_model=List[LnsRecord])
async def list_lns(
    q: Optional[str] = None,
    status: Optional[Literal["ACTIVE", "REVOKED"]] = None,
    limit: int = Query(100, ge=1, le=500),
    _role: str = Depends(require_roles(ROLE_SOVEREIGN, ROLE_AUDITOR)),
    user: dict = Depends(current_user),
) -> List[LnsRecord]:
    query: dict = {}
    # Tenant scope: a user bound to a tenant_id only sees their own employees.
    if user.get("tenant_id"):
        query["tenant_id"] = user["tenant_id"]
    if status:
        query["status"] = status
    if q:
        query["lns_name"] = {"$regex": q, "$options": "i"}
    cursor = db.lns.find(query, {"_id": 0}).sort("lns_name", 1).limit(limit)
    return [LnsRecord(**r) async for r in cursor]


@api.post("/lns/register_LEGACY_MOVED", include_in_schema=False, response_model=RegisterResponse)
async def register_lns(
    req: RegisterRequest,
    _role: str = Depends(require_roles(ROLE_SOVEREIGN)),
) -> RegisterResponse:
    """Internal helper (no longer publicly routable) — kept callable
    for `register_tenant` until tenants/register is itself extracted.
    Public endpoint lives in routes/lns.py (Iter_35)."""
    # Basic validation: lowercase, dots and alphanumerics. The new naming
    # convention (iteration_13) is `nomecognome.<azienda>.id`. Any LNS whose
    # suffix matches a registered tenant's `.<domain>` is accepted; for
    # backward-compat the legacy `.azienda.id` global suffix also works.
    name = req.lns_name.strip().lower()
    if not name or len(name) < 3:
        raise HTTPException(status_code=422, detail="lns_name too short")
    if not all(c.isalnum() or c in ".-_" for c in name):
        raise HTTPException(status_code=422, detail="lns_name contains forbidden characters")

    tenant_id = req.tenant_id
    tenant_doc = None
    if tenant_id:
        tenant_doc = await db.tenants.find_one({"tenant_id": tenant_id})
        if not tenant_doc:
            raise HTTPException(status_code=404, detail=f"tenant not found: {tenant_id}")
        if not name.endswith("." + tenant_doc["domain"]):
            raise HTTPException(
                status_code=422,
                detail=f"lns_name must end with .{tenant_doc['domain']} for tenant {tenant_id}",
            )
    else:
        # Try to auto-detect tenant from the LNS suffix by scanning tenants.
        cursor = db.tenants.find({}, {"_id": 0, "tenant_id": 1, "domain": 1})
        async for t in cursor:
            if name.endswith("." + t["domain"]):
                tenant_id = t["tenant_id"]
                tenant_doc = t
                break
        if not tenant_doc:
            raise HTTPException(
                status_code=422,
                detail="lns_name must end with .<azienda> where <azienda> is a registered tenant domain",
            )

    existing = await db.lns.find_one({"lns_name": name})
    if existing:
        raise HTTPException(status_code=409, detail=f"Identity already registered: {name}")
    # License quota enforcement (Iter_30) — refuse new identities beyond max_users.
    # Counts only ACTIVE identities (revoked ones don't consume seats).
    current_users = await db.lns.count_documents({"status": {"$ne": "REVOKED"}})
    if not licmod.check_user_quota(current_users):
        edition = (licmod.STATE.active or {}).get("edition", "community")
        max_u = licmod.STATE.active.get("max_users")
        raise HTTPException(
            status_code=402,
            detail=(
                f"License quota exceeded: edition='{edition}' allows max_users={max_u}, "
                f"already {current_users} active. Upgrade the license to add more seats."
            ),
        )

    ts = _utc_iso()
    if req.public_key_hex:
        # CLIENT-SIDE KEY GENERATION (sovereign mode).
        # The browser generated the ML-DSA-65 keypair via WASM. The server
        # never sees the secret key. We store only the public key on chain.
        try:
            pk = bytes.fromhex(req.public_key_hex)
        except ValueError:
            raise HTTPException(status_code=422, detail="public_key_hex is not valid hex")
        if len(pk) != 1952:
            raise HTTPException(status_code=422, detail=f"public_key_hex wrong length: {len(pk)} (expected 1952)")
        await db.keystore.update_one(
            {"entity": name},
            {"$set": {
                "entity": name,
                "role": req.role,
                "pk_hex": pk.hex(),
                "fingerprint": _pk_fingerprint(pk),
                "client_managed": True,  # secret key lives in the user's browser only
                "created_at": ts,
                "algorithm": PQC_ALGORITHM,
                **({"enc_pk_hex": req.enc_public_key_hex} if req.enc_public_key_hex else {}),
            }, "$unset": {"sk_hex": "", "sk": ""}},
            upsert=True,
        )
        _KEY_CACHE.pop(name, None)
    else:
        # LEGACY MODE: server materialises the keypair internally.
        pk, _sk = await _get_or_create_keypair(name, role="lns")
        # Even in legacy mode, persist the X25519 enc pk if the caller
        # provided one — so the user can still receive E2E mail.
        if req.enc_public_key_hex:
            await db.keystore.update_one(
                {"entity": name},
                {"$set": {"enc_pk_hex": req.enc_public_key_hex}},
                upsert=True,
            )
    fp = _pk_fingerprint(pk)
    did = f"did:lattice:{fp.lower()}"
    meta = await db.meta.find_one_and_update(
        {"_id": "seeded"},
        {"$inc": {"block_height": 1, "tx_total": 1, "qbft_round": 1}},
        return_document=True,
    )
    new_block_index = meta["block_height"]
    tx_id = f"tx-{_det_hex(f'register-{name}-{ts}', 12)}"

    await db.lns.insert_one({
        "lns_name": name,
        "did": did,
        "public_key_fingerprint": fp,
        "registered_at": ts,
        "status": "ACTIVE",
        "department": req.department,
        "display_name": (req.display_name or "").strip() or None,
        "revoked_at": None,
        "tenant_id": tenant_id,
        "role": req.role,
    })
    if tenant_id:
        await db.tenants.update_one(
            {"tenant_id": tenant_id},
            {"$inc": {"employees_count": 1}},
        )
    summary = f"IdentityRegister · {name} · role={req.role} · dept={req.department}"
    # When the user owns their key (client-side), the server cannot self-sign
    # on their behalf. The IdentityRegister TX is therefore signed by the
    # platform notary key — the user attests their pk separately via the
    # challenge-response login.
    signer_entity = "platform.notary" if req.public_key_hex else name
    tx_msg = ("|".join([tx_id, str(new_block_index), ts, "IdentityRegister", summary])).encode("utf-8")
    sig_hex, signer_fp = await _pqc_sign(signer_entity, tx_msg, role="platform" if req.public_key_hex else "lns")
    # Real QBFT: 2f+1 ML-DSA-65 votes from independent validator processes.
    block_doc = await _finalise_block_for_tx(
        index=new_block_index, timestamp=ts, tx_id=tx_id,
        kind="IdentityRegister", signer=name,
    )
    await db.transactions.insert_one({
        "tx_id": tx_id,
        "block_index": new_block_index,
        "timestamp": ts,
        "kind": "IdentityRegister",
        "summary": summary,
        "sender_public_key": signer_fp,
        "signature": sig_hex,
        "signed_with": PQC_ALGORITHM,
        "signer_entity": name,
    })
    await audit.append(db, "lns_register",
        node_id="admin-console",
        component="lattice-admin-console",
        message=f"LNS REGISTER · {name} · dept='{req.department}' · by={req.admin} · tx={tx_id}",
        lns_name=name, department=req.department, by=req.admin, tx_id=tx_id,
    )
    return RegisterResponse(
        ok=True, tx_id=tx_id, block_index=new_block_index,
        lns_name=name, did=did, public_key_fingerprint=fp, timestamp=ts,
        role=req.role, tenant_id=tenant_id,
        public_key_hex=pk.hex(),
        # When the client provided its own pk we DO NOT return a sk. The
        # browser already has it; the server never knew it.
        secret_key_hex=None if req.public_key_hex else (await _get_or_create_keypair(name))[1].hex(),
        keypair_filename=f"{name}.keypair.json",
    )


# ---------------------------------------------------------------------------
# Tenant onboarding — register an enterprise + its first sovereign admin LNS
# ---------------------------------------------------------------------------

@api.post("/certify/MOVED_TO_certify_mutating_LEGACY", include_in_schema=False)
async def _certify_mutating_moved() -> dict:  # pragma: no cover
    """certify/{id}/read, /restore, /receipt.pdf, DELETE /{id} and POST /send
    moved to routes/certify_mutating.py (Iter_38)."""
    return {"moved": True, "see": "routes/certify_mutating.py"}


# ---------------------------------------------------------------------------
# Pulse Protocol — sealed-sender encrypted chat with on-chain anchoring
# (mutating endpoints moved to routes/pulse_mutating.py · Iter_39)
# ---------------------------------------------------------------------------


def _current_rln_epoch() -> int:
    return int(datetime.now(timezone.utc).timestamp()) // RLN_EPOCH_SECONDS


# ---------------------------------------------------------------------------
# Real ZK-friendly Poseidon hash (Starknet variant, felt prime ~ 2^251).
# ---------------------------------------------------------------------------
# We use this instead of SHA3-256 because Poseidon is the actual hash family
# used inside the ZK-RLN Groth16 circuit (and inside Starknet / Cairo /
# circomlib-bn254). Picking it here makes the RLN identity commitment and
# nullifier numerically *identical* to what a real prover would emit, so a
# future arkworks-based prover only has to add the Groth16 wrapper — the
# committed values won't change.
from poseidon_py.poseidon_hash import poseidon_hash_many as _poseidon_many  # noqa: E402

# Starknet felt prime (used by poseidon-py). All RLN values live in this field.
_RLN_FIELD_P = (1 << 251) + 17 * (1 << 192) + 1
_RLN_SECRET_CACHE: dict[str, int] = {}


def _felt(value: int) -> int:
    return value % _RLN_FIELD_P


# ---------------------------------------------------------------------------
# Real ZK proof of knowledge — BN254 G1 / Chaum-Pedersen sigma protocol
# (Fiat-Shamir non-interactive). Proves the prover knows `secret` such that:
#   commitment_point = secret * G          (identity commitment)
#   nullifier_point  = secret * G_epoch    (epoch-bound nullifier)
# Same soundness model as zk-SNARK for this specific statement, on real
# elliptic-curve crypto. py_ecc 8.0.0 implements alt_bn128 (BN254).
# ---------------------------------------------------------------------------
from py_ecc.bn128 import (  # noqa: E402
    G1 as _BN_G1,
    add as _bn_add,
    curve_order as _BN_ORDER,
    eq as _bn_eq,
    multiply as _bn_mul,
)


def _pt_bytes(P) -> bytes:
    return int(P[0]).to_bytes(32, "big") + int(P[1]).to_bytes(32, "big")


def _bn_scalar_from(*items) -> int:
    h = hashlib.sha3_256()
    for x in items:
        if isinstance(x, tuple):
            h.update(_pt_bytes(x))
        elif isinstance(x, int):
            h.update(x.to_bytes(32, "big"))
        else:
            h.update(x if isinstance(x, bytes) else str(x).encode())
    return int.from_bytes(h.digest(), "big") % _BN_ORDER


def _bn_hash_to_g(label: bytes):
    h = int.from_bytes(hashlib.sha3_256(label).digest(), "big") % _BN_ORDER
    return _bn_mul(_BN_G1, h or 1)


def _bn_pt_to_hex(P) -> str:
    return _pt_bytes(P).hex()


def _bn_pt_from_hex(s: str):
    raw = bytes.fromhex(s)
    if len(raw) != 64:
        raise ValueError("point must be 64 bytes")
    from py_ecc.bn128 import FQ
    return (FQ(int.from_bytes(raw[:32], "big")), FQ(int.from_bytes(raw[32:], "big")))


def rln_zk_prove(secret_int: int, epoch: int) -> dict:
    """Real BN254 Chaum-Pedersen sigma proof of knowledge of *secret_int*."""
    G_ep = _bn_hash_to_g(f"lattice-rln-epoch-{epoch}".encode())
    C = _bn_mul(_BN_G1, secret_int)
    N = _bn_mul(G_ep, secret_int)
    r = secrets.randbelow(_BN_ORDER)
    A = _bn_mul(_BN_G1, r)
    B = _bn_mul(G_ep, r)
    c = _bn_scalar_from(C, N, A, B, epoch)
    z = (r + c * secret_int) % _BN_ORDER
    return {
        "scheme": "Chaum-Pedersen · BN254 G1 · Fiat-Shamir SHA3-256",
        "epoch": epoch,
        "commitment_hex": _bn_pt_to_hex(C),
        "nullifier_hex": _bn_pt_to_hex(N),
        "A_hex": _bn_pt_to_hex(A),
        "B_hex": _bn_pt_to_hex(B),
        "z_hex": f"{z:064x}",
    }


def rln_zk_verify(proof: dict) -> bool:
    """Run the real verifier equations. Returns True only when proof checks."""
    try:
        C = _bn_pt_from_hex(proof["commitment_hex"])
        N = _bn_pt_from_hex(proof["nullifier_hex"])
        A = _bn_pt_from_hex(proof["A_hex"])
        B = _bn_pt_from_hex(proof["B_hex"])
        z = int(proof["z_hex"], 16)
        epoch = int(proof["epoch"])
    except Exception:
        return False
    G_ep = _bn_hash_to_g(f"lattice-rln-epoch-{epoch}".encode())
    c = _bn_scalar_from(C, N, A, B, epoch)
    # First equation: z*G = A + c*C
    if not _bn_eq(_bn_mul(_BN_G1, z), _bn_add(A, _bn_mul(C, c))):
        return False
    # Second equation: z*G_ep = B + c*N
    return _bn_eq(_bn_mul(G_ep, z), _bn_add(B, _bn_mul(N, c)))


async def _get_or_create_rln_bn_secret(lns: str) -> int:
    """Derive a deterministic BN254-field secret from the LNS RLN secret."""
    # Reuse the Poseidon secret so the user has a single identity across
    # ZK-friendly hash (Poseidon) and EC group (BN254).
    poseidon_secret = await _get_or_create_rln_secret(lns)
    return poseidon_secret % _BN_ORDER


def _poseidon(*inputs: int) -> int:
    """Real Poseidon hash over the Starknet felt field (poseidon-py)."""
    return _poseidon_many([_felt(x) for x in inputs])


async def _get_or_create_rln_secret(lns: str) -> int:
    """Materialise a real RLN secret (uniform random felt) for *lns* on first use."""
    if lns in _RLN_SECRET_CACHE:
        return _RLN_SECRET_CACHE[lns]
    doc = await db.rln_secrets.find_one({"lns": lns})
    if doc:
        secret = int(doc["secret_hex"], 16)
    else:
        # 31 bytes -> safely inside the felt field; reject sample if needed.
        while True:
            candidate = int.from_bytes(secrets.token_bytes(31), "big")
            if 0 < candidate < _RLN_FIELD_P:
                secret = candidate
                break
        commitment = _poseidon(secret)
        await db.rln_secrets.insert_one({
            "lns": lns,
            "secret_hex": f"{secret:064x}",
            "commitment_hex": f"{commitment:064x}",
            "created_at": _utc_iso(),
        })
    _RLN_SECRET_CACHE[lns] = secret
    return secret


async def _rln_commitment(lns: str) -> int:
    """Real Poseidon identity commitment = Poseidon(secret)."""
    secret = await _get_or_create_rln_secret(lns)
    return _poseidon(secret)


async def _rln_real_nullifier(lns: str, epoch: int) -> int:
    """Real Poseidon nullifier = Poseidon(secret, epoch). Same in production circuit."""
    secret = await _get_or_create_rln_secret(lns)
    return _poseidon(secret, epoch)


def _rln_nullifier(lns: str, epoch: int) -> str:
    """Legacy SHA3-256 wrapper kept for backward compatibility with seeded data."""
    return hashlib.sha3_256(f"rln-secret-{lns}|{epoch}".encode()).hexdigest()


def _pulse_session_fingerprint(conv_id: str, participants: list[str]) -> str:
    """SAS-style 8-byte fingerprint over the canonicalised participant pair."""
    pair = "|".join(sorted([p.lower() for p in participants]))
    h = hashlib.sha3_256(f"{conv_id}|{pair}".encode()).digest()
    return ":".join(f"{b:02X}" for b in h[:8])


def _conv_id(a: str, b: str) -> str:
    lo, hi = sorted([a.lower(), b.lower()])
    return f"conv-{hashlib.sha3_256(f'{lo}|{hi}'.encode()).hexdigest()[:24]}"


@api.post("/pulse/MOVED_TO_pulse_mutating_LEGACY", include_in_schema=False)
async def _pulse_send_moved() -> dict:  # pragma: no cover
    """POST /pulse/send + GET /pulse/session/{conv_id} moved to
    routes/pulse_mutating.py (Iter_39)."""
    return {"moved": True, "see": "routes/pulse_mutating.py"}


# ---------------------------------------------------------------------------
# Vendor Operations Console
# ---------------------------------------------------------------------------
# Data residency principle: NO customer message bodies, NO Pulse ciphertext,
# NO LNS secret keys ever transit the vendor side. The vendor's "tenants"
# collection only holds operational metadata (license tier, node count,
# heartbeat). This is the same separation Snowflake / HashiCorp / GitLab
# self-hosted vendors use.

TENANT_SEED = [
    ("Banca Sovrana d'Italia", "banca.id", "Banking", "IT", "SOVEREIGN", 4200, 24_900),
    ("Ministero della Difesa", "difesa.gov.it", "Government", "IT", "SOVEREIGN", 8500, 49_500),
    ("Energia Italia S.p.A.", "energia.it", "Energy / Utility", "IT", "ENTERPRISE", 1800, 14_900),
    ("Studio Legale Conti & Partners", "contilex.eu", "Legal", "IT", "ENTERPRISE", 220, 4_900),
    ("Farmaceutica Romana", "farma-rm.it", "Pharma", "IT", "STANDARD", 480, 2_400),
    ("Polizia Postale (PoC)", "pp.gov.it", "Government", "IT", "TRIAL", 25, 0),
    ("Comune di Milano", "comune.milano.it", "Public Sector", "IT", "STANDARD", 920, 3_900),
]


async def _seed_tenants_if_empty() -> None:
    """No-op — clean chain start. Tenants are created only via /api/tenants/register."""
    return


# /api/vendor/* and /api/rln/* moved to routes/vendor_rln.py (Iter_40)



@api.get("/mixnet/topology", response_model=List[MixnetRelay])
async def mixnet_topology() -> List[MixnetRelay]:
    cursor = db.mixnet_relays.find({}, {"_id": 0}).sort([("layer", 1), ("label", 1)])
    return [MixnetRelay(**r) async for r in cursor]


@api.post("/mixnet/route", response_model=MixnetRoute)
async def mixnet_route(req: MixnetRouteRequest) -> MixnetRoute:
    relays = await db.mixnet_relays.find({}, {"_id": 0}).to_list(None)
    if len(relays) < 3:
        raise HTTPException(status_code=500, detail="Mixnet topology underprovisioned")
    layers: dict[int, list[dict]] = {0: [], 1: [], 2: []}
    for r in relays:
        if r.get("layer") in layers:
            layers[r["layer"]].append(r)
    origin = req.origin_lns.strip().lower()
    dest = req.destination_lns.strip().lower()
    seed_int = int(hashlib.sha3_256(f"{origin}|{dest}|{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest()[:16], 16)
    hops: list[MixnetHop] = []
    total = 0
    acc = seed_int
    for layer in (0, 1, 2):
        bucket = layers[layer] or relays
        relay = bucket[acc % len(bucket)]
        acc = int(hashlib.sha3_256(acc.to_bytes(8, "big") + relay["node_id"].encode()).hexdigest()[:16], 16)
        hop_buf = f"LATTICE-LOOPIX-v1|{origin}|{dest}|layer={layer}|{relay['node_id']}".encode()
        onion_hash = hashlib.sha3_256(hop_buf).hexdigest()
        delay = int(relay["latency_ms"]) + 15 * (layer + 1)
        total += delay
        hops.append(MixnetHop(
            layer=layer,
            relay_node_id=relay["node_id"],
            relay_label=relay["label"],
            relay_region=relay["region"],
            onion_layer_hash=onion_hash,
            delay_ms=delay,
        ))
    route_input = b"".join(bytes.fromhex(h.onion_layer_hash) for h in hops)
    route_id = "route-" + hashlib.sha3_256(route_input).hexdigest()[:24]
    return MixnetRoute(
        route_id=route_id,
        origin_lns=origin,
        destination_lns=dest,
        hops=hops,
        total_delay_ms=total,
        cover_traffic_rate_hz=1.5,
    )


@api.get("/pulse/session/MOVED_TO_pulse_mutating_LEGACY", include_in_schema=False)
async def _pulse_session_moved() -> dict:  # pragma: no cover
    """Moved to routes/pulse_mutating.py (Iter_39)."""
    return {"moved": True, "see": "routes/pulse_mutating.py"}


@api.get("/logs/stream", response_model=List[LogLine])
async def logs_stream(limit: int = Query(80, ge=1, le=500)) -> List[LogLine]:
    """Return the latest synthetic node log lines (audit + runtime)."""
    combined = await _collect_log_lines(limit)
    return [LogLine(**row) for row in combined]


# ---------------------------------------------------------------------------
# Shared log-line generator (used by both polling and SSE endpoints)
# ---------------------------------------------------------------------------
async def _collect_log_lines(limit: int) -> list[dict]:
    audit = await db.audit_log.find({}, {"_id": 0}).sort("ts", -1).limit(max(1, limit // 4)).to_list(None)
    now = datetime.now(timezone.utc)
    nodes = await db.qbft_nodes.find({}, {"_id": 0, "label": 1, "node_id": 1}).to_list(None)
    pool = [
        ("INFO", "qbft.consensus", "ROUND_CHANGE accepted — round={r} proposer={p}"),
        ("INFO", "qbft.consensus", "PREPARE quorum reached ({n}/{t}) — block={b}"),
        ("INFO", "qbft.consensus", "COMMIT vote registered — block={b}"),
        ("INFO", "lattice.node", "Block finalised height={b} txs={x} hash={h}"),
        ("INFO", "lattice.crypto", "Dilithium3 signature verified — pk={pk}"),
        ("INFO", "pulse.protocol", "Sealed-sender packet relayed — dest={d}"),
        ("WARN", "pulse.protocol", "Client PoW retry — difficulty={diff}"),
        ("INFO", "certify.gateway", "NotaryTX emitted — doc={h}"),
        ("WARN", "qbft.consensus", "Validator {p} latency={l}ms above target"),
        ("ERROR", "lattice.node", "Mempool eviction — stale tx {tx}"),
    ]
    runtime: list[dict] = []
    for i in range(max(0, limit - len(audit))):
        lvl, comp, tmpl = random.choice(pool)
        proposer = random.choice(nodes)["label"] if nodes else "VAL-01"
        node_id = random.choice(nodes)["node_id"] if nodes else "node-unknown"
        msg = tmpl.format(
            r=random.randint(180_000, 260_000),
            p=proposer,
            n=random.randint(5, 7), t=7,
            b=random.randint(4_200, 4_300),
            x=random.randint(0, 7),
            h=_hex(8),
            pk=_hex(6),
            d=random.choice(FIRST_NAMES) + "." + random.choice(LAST_NAMES) + ".azienda.id",
            diff=random.randint(18, 22),
            l=random.randint(80, 320),
            tx=_hex(6),
        )
        runtime.append({
            "ts": (now - timedelta(seconds=i * random.uniform(0.05, 0.4))).isoformat(),
            "node_id": node_id,
            "level": lvl,
            "component": comp,
            "message": msg,
        })
    return sorted(audit + runtime, key=lambda x: x["ts"], reverse=True)[:limit]


@api.get("/logs/sse")
async def logs_sse(rate: float = Query(0.6, ge=0.1, le=5.0), batch: int = Query(4, ge=1, le=20)):
    """Server-Sent Events stream of sovereign node log lines.

    Each `data:` frame is a JSON array of fresh log lines (newest first).
    The client should append them to the top of the terminal buffer.
    """
    async def gen() -> AsyncIterator[bytes]:
        # Send an initial backfill so the terminal isn't empty on connect.
        backfill = await _collect_log_lines(60)
        yield f"event: backfill\ndata: {json.dumps(backfill)}\n\n".encode()
        try:
            while True:
                lines = await _collect_log_lines(batch)
                yield f"data: {json.dumps(lines)}\n\n".encode()
                await asyncio.sleep(rate)
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


class VerifyResponse(BaseModel):
    ok: bool
    tx_id: str
    algorithm: str
    signed_with: str
    signer_entity: Optional[str] = None
    public_key_fingerprint: Optional[str] = None
    public_key_size_bytes: int
    signature_size_bytes: int
    message_hex: str
    detail: str


class PublicKeyResponse(BaseModel):
    entity: str
    role: str
    algorithm: str
    public_key_hex: str
    public_key_size_bytes: int
    fingerprint: str
    created_at: str





# ---------------------------------------------------------------------------
# Rust FFI bridge — real lattice-crypto via PyO3
# ---------------------------------------------------------------------------
try:
    import lattice_py as _rust  # type: ignore
    _RUST_AVAILABLE = True
    _RUST_ERROR = None
except Exception as _e:  # pragma: no cover
    _rust = None  # type: ignore
    _RUST_AVAILABLE = False
    _RUST_ERROR = str(_e)




# ---------------------------------------------------------------------------
# Mixnet Loopix — real 3-hop onion routing across 3 independent processes
# ---------------------------------------------------------------------------
# The relays live on 127.0.0.1:9101..9103. We pull their current X25519
# public keys from MongoDB (`mixnet_keystore`), wrap the payload in 3
# nested ChaCha20-Poly1305 layers using fresh ephemeral X25519 handshakes
# per hop, and POST the outer onion to the layer-1 relay. The third
# relay calls back into /api/mixnet/deliver with the cleartext, which we
# then forward into the recipient's Pulse inbox. This is a working
# Loopix-style mixnet — no shortcuts, no `await asyncio.sleep` "mock".
import json as _json  # noqa: E402

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey  # noqa: E402
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305  # noqa: E402
from cryptography.hazmat.primitives.hashes import SHA256  # noqa: E402
from cryptography.hazmat.primitives.kdf.hkdf import HKDF  # noqa: E402

GATEWAY_INTERNAL_URL = os.environ.get("LATTICE_GATEWAY_URL", "http://127.0.0.1:8001")


def _onion_seal_layer(relay_pk_hex: str, layer_index: int, inner: dict) -> dict:
    """Encrypt *inner* (a JSON-able dict) for the given relay public key."""
    eph = X25519PrivateKey.generate()
    relay_pk = X25519PublicKey.from_public_bytes(bytes.fromhex(relay_pk_hex))
    shared = eph.exchange(relay_pk)
    key = HKDF(algorithm=SHA256(), length=32, salt=None, info=b"lattice-mixnet-v1").derive(shared)
    nonce = secrets.token_bytes(12)
    aead = ChaCha20Poly1305(key)
    plaintext = _json.dumps(inner, separators=(",", ":")).encode("utf-8")
    ct = aead.encrypt(nonce, plaintext, b"layer-" + layer_index.to_bytes(1, "big"))
    return {
        "eph_pub_hex": eph.public_key().public_bytes_raw().hex(),
        "ciphertext_hex": ct.hex(),
        "nonce_hex": nonce.hex(),
    }


async def _mixnet_relays_sorted() -> List[dict]:
    cursor = db.mixnet_keystore.find({}, {"_id": 0}).sort("layer", 1)
    return [doc async for doc in cursor]


async def _route_through_mixnet(delivery: dict) -> dict:
    """Build a 3-layer onion and inject it at MIX-01. Returns the route metadata."""
    relays = await _mixnet_relays_sorted()
    if len(relays) < 3:
        # First boot — relays not registered yet, deliver directly.
        return {"hops": 0, "route_id": None, "direct_delivery": True}

    # Innermost (layer 3 perspective): terminal hop with final delivery info.
    inner3 = {
        "terminal": True,
        "gateway_url": GATEWAY_INTERNAL_URL,
        "delivery": delivery,
    }
    layer3 = _onion_seal_layer(relays[2]["pk_hex"], 3, inner3)
    layer2_inner = {
        "next_endpoint": relays[2]["endpoint"],
        "next_packet": layer3,
    }
    layer2 = _onion_seal_layer(relays[1]["pk_hex"], 2, layer2_inner)
    layer1_inner = {
        "next_endpoint": relays[1]["endpoint"],
        "next_packet": layer2,
    }
    outer = _onion_seal_layer(relays[0]["pk_hex"], 1, layer1_inner)

    route_id = secrets.token_hex(6)
    try:
        async with httpx.AsyncClient(timeout=3.0) as cx:
            await cx.post(f"{relays[0]['endpoint']}/relay", json=outer)
    except Exception as exc:
        log.warning("mixnet injection failed: %s", exc)
        return {"hops": 0, "route_id": route_id, "direct_delivery": True}

    await db.mixnet_routes.insert_one({
        "route_id": route_id,
        "hops": [r["relay_id"] for r in relays[:3]],
        "started_at": _utc_iso(),
        "delivery_keys": list(delivery.keys()),
    })
    return {
        "hops": 3,
        "route_id": route_id,
        "path": [r["relay_id"] for r in relays[:3]],
        "direct_delivery": False,
    }


# Internal endpoint the third relay calls back when the onion is fully peeled.
@api.post("/mixnet/deliver")
async def mixnet_deliver(delivery: dict) -> dict:
    """Terminal endpoint invoked by MIX-03 after the third onion layer is peeled."""
    msg_id = delivery.get("msg_id")
    if not msg_id:
        raise HTTPException(status_code=400, detail="malformed mixnet delivery (missing msg_id)")
    await db.pulse_messages.update_one(
        {"msg_id": msg_id},
        {"$set": {
            "mixnet_delivered_at": _utc_iso(),
            "mixnet_route_id": delivery.get("route_id"),
            "mixnet_hops": delivery.get("path", []),
        }},
    )
    return {"ok": True, "msg_id": msg_id}


@api.get("/mixnet/status")
async def mixnet_status() -> dict:
    """Live mixnet — pings each relay process and reports their X25519 pks."""
    relays = await _mixnet_relays_sorted()

    async def _ping(r: dict) -> dict:
        info = dict(r)
        info.pop("sk_hex", None)
        try:
            async with httpx.AsyncClient(timeout=1.5) as cx:
                resp = await cx.get(f"{r['endpoint']}/health")
                if resp.status_code == 200:
                    body = resp.json()
                    info["live"] = True
                    info["relayed_total"] = body.get("relayed_total", 0)
                else:
                    info["live"] = False
        except Exception:
            info["live"] = False
        return info

    enriched = await asyncio.gather(*[_ping(r) for r in relays])
    return {
        "relays": enriched,
        "live_count": sum(1 for r in enriched if r.get("live")),
        "total_count": len(enriched),
        "topology": "Loopix · 3 hops · ChaCha20-Poly1305 · X25519 ECDH · ε-mixing Poisson",
        "implementation": "3 independent uvicorn processes on 127.0.0.1:9101-9103",
    }


# ---------------------------------------------------------------------------
# Auth Pydantic models moved to routes/auth.py (Iter_38)
# ---------------------------------------------------------------------------


from security import rate_limiter  # noqa: E402  (used by middleware)

# Auth challenge/verify/logout/revoke-all + 2FA endpoints
# moved to routes/auth.py (Iter_38).


# ---------------------------------------------------------------------------
# Audit log chain verification
# ---------------------------------------------------------------------------
@api.get("/lns/{lns_name}/enc-key")
async def get_recipient_enc_key(
    lns_name: str,
    user: dict = Depends(current_user),
) -> dict:
    """Return the recipient's X25519 encryption public key (32 bytes hex).

    Used by the sender's browser to E2E-encrypt a Certify mail body
    before submission. The caller must be in the same tenant (or
    sovereign). Returns 404 if the recipient never published an enc key.
    """
    ks = await db.keystore.find_one({"entity": lns_name}, {"_id": 0, "enc_pk_hex": 1})
    if not ks:
        raise HTTPException(status_code=404, detail="no such LNS")
    enc_pk = ks.get("enc_pk_hex")
    if not enc_pk:
        raise HTTPException(status_code=404, detail="recipient has no E2E encryption key on file")
    return {"lns": lns_name, "enc_public_key_hex": enc_pk, "algorithm": "X25519"}


# ---------------------------------------------------------------------------
# Audit log chain verification
# ---------------------------------------------------------------------------
class KeyShareEnrollRequest(BaseModel):
    lns: str
    guardian1_lns: str
    guardian2_lns: str
    guardian3_lns: str
    # Each share is encrypted in the user's browser with the guardian's
    # X25519 public key (ECIES, see /lns/{lns}/enc-key). The server stores
    # opaque ciphertext — it cannot reconstruct the user's secret key.
    encrypted_share1: dict
    encrypted_share2: dict
    encrypted_share3: dict
    share1_fingerprint: str
    share2_fingerprint: str
    share3_fingerprint: str


class KeyRecoveryRequestModel(BaseModel):
    lns: str  # whose key we want to recover
    reason: str = "lost_keypair"
    # NEW (iter_25): the requester's freshly-generated X25519 public key.
    # Guardians fetch this via /keyrecovery/status/{rid}.requester_enc_pk_hex
    # and re-seal their share for it — no more out-of-band prompts.
    requester_enc_pk_hex: Optional[str] = Field(default=None, min_length=64, max_length=64)


class KeyRecoveryContribute(BaseModel):
    request_id: str
    guardian_lns: str
    # Guardian decrypts their share locally with their X25519 sk, then
    # re-encrypts it for the requester's NEW X25519 pk before submitting.
    contributed_share: dict


# ---------------------------------------------------------------------------
# 2FA TOTP + Active sessions moved to routes/auth.py (Iter_38)
# ---------------------------------------------------------------------------
import pyotp  # noqa: E402,F401  (re-exported for backwards compatibility)


# ---------------------------------------------------------------------------
# Employee lifecycle — modify role, delete
# ---------------------------------------------------------------------------
class RoleUpdateRequest(BaseModel):
    role: Literal["admin", "operator", "auditor", "vendor"]


@api.patch("/lns/{lns_name}/role", response_model=LnsRecord)
async def lns_set_role(
    lns_name: str,
    req: RoleUpdateRequest,
    _role: str = Depends(require_roles(ROLE_SOVEREIGN)),
) -> LnsRecord:
    name = lns_name.strip().lower()
    doc = await db.lns.find_one({"lns_name": name})
    if not doc:
        raise HTTPException(status_code=404, detail=f"lns not found: {name}")
    if doc.get("status") == "REVOKED":
        raise HTTPException(status_code=409, detail="cannot modify a revoked identity")
    await db.lns.update_one(
        {"lns_name": name},
        {"$set": {"role": req.role, "role_updated_at": _utc_iso()}},
    )
    updated = await db.lns.find_one({"lns_name": name}, {"_id": 0})
    return LnsRecord(**updated)


@api.get("/health")
async def health() -> dict:
    return {
        "ok": True,
        "ts": _utc_iso(),
        "strict_auth": STRICT_AUTH,
    }


# ---------------------------------------------------------------------------
# Commercial leads — capture from the landing page "Request demo" form
# ---------------------------------------------------------------------------
# LeadRequest / LeadResponse moved to routes/leads.py (Iter_40)
# TenantWebhookConfig moved to routes/pec_webhook.py (Iter_40)


# ---------------------------------------------------------------------------
# PEC delivery-receipt webhook (notify sender's tenant on signed open)
# ---------------------------------------------------------------------------
PEC_WEBHOOK_URL = os.environ.get("PEC_WEBHOOK_URL", "").strip()
PEC_WEBHOOK_SECRET = os.environ.get("PEC_WEBHOOK_SECRET", "").strip()


async def _fire_pec_webhook(mail: dict, receipt: dict) -> None:
    """POST a JSON payload to PEC_WEBHOOK_URL (and/or the tenant-configured
    URL) when a delivery receipt is finalised. Best-effort, non-blocking.

    Payload schema:
      { event: "pec.delivered", mail_id, sender_lns, recipient_lns,
        subject, sealed_at, receipt: { tx_id, block_index, signed_at,
        signed_by, signature_hex, canonical_preimage_sha3_512 } }

    If PEC_WEBHOOK_SECRET is set, the request includes a `X-Lattice-Signature`
    header = HMAC-SHA256(secret, body).
    """
    # Resolve sender tenant override (per-tenant config takes priority).
    target_url = PEC_WEBHOOK_URL
    sender = mail.get("sender_lns") or ""
    if sender:
        sender_doc = await db.lns.find_one({"lns_name": sender}, {"tenant_id": 1})
        if sender_doc:
            tenant_doc = await db.tenants.find_one(
                {"tenant_id": sender_doc.get("tenant_id")},
                {"pec_webhook_url": 1, "pec_webhook_secret": 1},
            )
            if tenant_doc and tenant_doc.get("pec_webhook_url"):
                target_url = tenant_doc["pec_webhook_url"]
    if not target_url:
        return

    payload = {
        "event": "pec.delivered",
        "mail_id": mail["mail_id"],
        "sender_lns": mail.get("sender_lns"),
        "recipient_lns": mail.get("recipient_lns"),
        "subject": mail.get("subject"),
        "sealed_at": mail.get("sealed_at"),
        "receipt": {
            "tx_id": receipt["tx_id"],
            "block_index": receipt["block_index"],
            "signed_at": receipt["signed_at"],
            "signed_by": receipt["signed_by"],
            "signature_hex": receipt["signature_hex"],
            "canonical_preimage_sha3_512": receipt["canonical_preimage_sha3_512"],
        },
        "verify_url": f"/api/certify/{mail['mail_id']}/receipt.pdf",
    }
    import json as _json
    import hmac as _hmac
    body_bytes = _json.dumps(payload, separators=(",", ":")).encode()
    headers = {"Content-Type": "application/json", "User-Agent": "Lattice-Webhook/1.0"}
    secret = PEC_WEBHOOK_SECRET
    # Tenant-specific secret override
    if sender:
        sender_doc2 = await db.lns.find_one({"lns_name": sender}, {"tenant_id": 1})
        if sender_doc2:
            tdoc = await db.tenants.find_one(
                {"tenant_id": sender_doc2.get("tenant_id")},
                {"pec_webhook_secret": 1},
            )
            if tdoc and tdoc.get("pec_webhook_secret"):
                secret = tdoc["pec_webhook_secret"]
    if secret:
        sig = _hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
        headers["X-Lattice-Signature"] = f"sha256={sig}"

    try:
        async with httpx.AsyncClient(timeout=8.0) as cx:
            r = await cx.post(target_url, content=body_bytes, headers=headers)
            log.info("PEC webhook → %s · HTTP %d · mail=%s", target_url, r.status_code, mail["mail_id"])
    except Exception as e:
        log.warning("PEC webhook to %s failed: %s", target_url, e)


class TenantWebhookConfig_MOVED:  # pragma: no cover
    """Moved to routes/pec_webhook.py (Iter_40)."""
    pass


# _notarize_lead_onchain + /leads/* moved to routes/leads.py (Iter_40)
# ATTACH_DIR / AttachmentMeta / _attachment_access_check + /attachments/*
# moved to routes/attachments.py (Iter_40)


# ---------------------------------------------------------------------------
# Wire-up
# ---------------------------------------------------------------------------
# --- Production hardening (security.py) -------------------------------------
from security import install_security  # noqa: E402

install_security(app, log, strict=STRICT_AUTH)


# ---------------------------------------------------------------------------
# Admin · Chain Reset (testing / staging)
# ---------------------------------------------------------------------------
# Wipes application-level state and re-seeds the genesis block.
# Preserves PQC keystore for validators + qbft_nodes + mixnet_relays.
# PROTECTION: requires platform-sovereign role AND an explicit confirmation
# header so it can never be triggered by accident.
RESET_CONFIRM_TOKEN = "WIPE_CHAIN_YES"
RESETTABLE_COLLECTIONS = [
    "blocks", "transactions", "tenants", "lns", "lns_deleted",
    "certify_mails", "pulse_conversations", "pulse_messages", "pulse_sessions",
    "recovery_enrollments", "recovery_requests",
    "leads", "audit_log", "access_log", "auth_challenges",
    "revoked_jwts", "totp_secrets", "rln_quota", "rln_nullifiers",
    "rln_secrets", "qbft_votes_emitted", "attachments",
    # Infra collections — wiped then re-seeded atomically below.
    # NOTE: mixnet_keystore is NOT in this list — it's owned by the
    # external mixnet relay processes, which auto-populate it on
    # startup. Wiping it desyncs them from the DB.
    "qbft_nodes", "mixnet_relays",
    "mixnet_routes", "mixnet_topology",
    "vendor_tenants", "alert_webhooks", "meta",
]


@api.post("/admin/chain/reset")
async def admin_chain_reset(
    confirm: Optional[str] = Header(default=None, alias="X-Lattice-Reset-Confirm"),
    _sov: dict = Depends(require_platform_sovereign()),
):
    """Nuke application state and rebuild a clean genesis chain.

    Required headers:
      * `X-Lattice-Role: sovereign`  (or a valid sovereign JWT)
      * `X-Lattice-Reset-Confirm: WIPE_CHAIN_YES`
    """
    if confirm != RESET_CONFIRM_TOKEN:
        raise HTTPException(
            status_code=400,
            detail=f"Missing/invalid confirmation header. Send 'X-Lattice-Reset-Confirm: {RESET_CONFIRM_TOKEN}'",
        )
    wiped: Dict[str, int] = {}
    for name in RESETTABLE_COLLECTIONS:
        coll = db[name]
        try:
            res = await coll.delete_many({})
            wiped[name] = int(getattr(res, "deleted_count", 0) or 0)
        except Exception as e:  # pragma: no cover — best-effort
            log.warning("reset: collection %s not wiped (%s)", name, e)
            wiped[name] = -1
    # Re-seed infrastructure (QBFT validators + Mixnet relays) and
    # the genesis block, all from scratch. _seed_if_empty creates
    # qbft_nodes + genesis + meta. We then re-add the mixnet relays
    # because _seed_if_empty doesn't cover them.
    await _seed_if_empty()
    if await db.mixnet_relays.count_documents({}) == 0:
        relays = []
        for (label, layer, region, lat) in MIXNET_RELAYS_SEED:
            relays.append({
                "node_id": f"mix-{_det_hex(label, 6)}",
                "label": label,
                "region": region,
                "layer": layer,
                "kem_pk_fingerprint": _det_hex(f"mix-pk-{label}", 8).upper(),
                "latency_ms": lat,
            })
        await db.mixnet_relays.insert_many(relays)
    new_meta = await db.meta.find_one({"_id": "seeded"}, {"_id": 0})
    qbft_n = await db.qbft_nodes.count_documents({})
    mix_n = await db.mixnet_relays.count_documents({})
    log.info("admin chain reset: %s · qbft=%d mixnet=%d", wiped, qbft_n, mix_n)
    return {
        "ok": True,
        "wiped": wiped,
        "infra_reseeded": {"qbft_nodes": qbft_n, "mixnet_relays": mix_n},
        "genesis": new_meta,
        "message": "Chain reset complete. All tenants, LNS entries, mails, messages and recovery data have been removed. Genesis block + QBFT validators + Mixnet relays re-seeded from scratch.",
    }


# ---------------------------------------------------------------------------
# Admin · Demo Seed (testing / sales demo)
# ---------------------------------------------------------------------------
# Populates the empty network with realistic-looking data so a demo to a
# prospect doesn't look like an empty toy:
#   • 4 demo tenants (Banca / Studio Legale / PA / Industria)
#   • 4 employees per tenant (admin + 3 operators) — REAL PQC keypairs
#   • 50 Certify mails distributed across tenants with realistic
#     timestamps (last 14 days, business hours)
#   • 200 Pulse messages distributed across tenants
#
# Mail/message blocks are BATCHED (25 mails per block, 50 msgs per block)
# to keep the runtime under 15s. Each tx still has a real ML-DSA-65
# signature so /api/ledger/verify works on every demo row.

# Demo data + _demo_random_past_ts moved to data/demo_seed_data.py (Iter_40)
from data.demo_seed_data import (  # noqa: E402
    DEMO_TENANTS_CONFIG, DEMO_PROFILES, SEED_DEMO_CONFIRM, _demo_random_past_ts,
)



@api.post("/admin/chain/seed-demo")
async def admin_chain_seed_demo(
    profile: str = "completo",
    confirm: Optional[str] = Header(default=None, alias="X-Lattice-Seed-Confirm"),
    _sov: dict = Depends(require_platform_sovereign()),
):
    """Populate the chain with vertical demo data.

    Query param `profile` selects the sector vocabulary:
      * `bancaria`    — Banca Demo SpA + AML/Vigilanza/UIF language
      * `legale`      — Studio Legale Demo SRL + litigation/contract language
      * `pa`          — PA Comune Demo + protocol/procurement language
      * `industriale` — Industria Demo SpA + R&D/patent/supply-chain language
      * `completo`    — all 4 tenants, generic business language

    Required headers:
      * `X-Lattice-Role: sovereign`
      * `X-Lattice-Seed-Confirm: SEED_DEMO_YES`
    """
    if confirm != SEED_DEMO_CONFIRM:
        raise HTTPException(
            status_code=400,
            detail=f"Missing/invalid confirmation header. Send 'X-Lattice-Seed-Confirm: {SEED_DEMO_CONFIRM}'",
        )
    if profile not in DEMO_PROFILES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown profile '{profile}'. Valid: {sorted(DEMO_PROFILES.keys())}",
        )
    prof = DEMO_PROFILES[profile]
    selected_tenants = [t for t in DEMO_TENANTS_CONFIG if t["key"] in prof["tenant_keys"]]
    mail_subjects_pool = prof["mail_subjects"]
    msg_bodies_pool = prof["msg_bodies"]
    summary: Dict[str, Any] = {
        "profile": profile,
        "profile_label": prof["label"],
        "tenants": 0,
        "employees": 0,
        "mails": 0,
        "messages": 0,
        "blocks_created": 0,
    }
    all_lns: List[Tuple[str, str]] = []  # (lns_name, tenant_id)

    # 1. Tenants + admins (real PQC keypairs, one block each)
    for cfg in selected_tenants:
        try:
            tr = TenantRegisterRequest(
                name=cfg["name"],
                domain_prefix=cfg["prefix"],
                admin_lns_prefix=cfg["admin"][0],
                admin_display_name=cfg["admin"][1],
            )
            resp = await tenants_routes.do_register_tenant(tr)
            summary["tenants"] += 1
            summary["blocks_created"] += 1
            all_lns.append((resp.admin_lns, resp.tenant_id))
            # 2. Employees per tenant
            for emp_prefix, emp_name, emp_dept, emp_role in cfg["employees"]:
                er = RegisterRequest(
                    lns_name=f"{emp_prefix}.{resp.domain}",
                    department=emp_dept,
                    admin=emp_name,
                    display_name=emp_name,
                    tenant_id=resp.tenant_id,
                    role=emp_role,
                )
                er_resp = await register_lns(er, _role=ROLE_SOVEREIGN)
                summary["employees"] += 1
                summary["blocks_created"] += 1
                all_lns.append((er_resp.lns_name, resp.tenant_id))
        except HTTPException as e:
            log.warning("seed-demo: tenant %s skipped (%s)", cfg["prefix"], e.detail)
            # Idempotency: tenant already exists from a previous seed — reuse
            # its existing LNS pool so we can still spawn fresh mails/messages.
            existing_tenant = await db.tenants.find_one({"domain": f"{cfg['prefix']}.lns"})
            if existing_tenant:
                existing_lns_cursor = db.lns.find(
                    {"tenant_id": existing_tenant["tenant_id"], "status": "ACTIVE"},
                    {"_id": 0, "lns_name": 1, "tenant_id": 1},
                )
                async for doc in existing_lns_cursor:
                    all_lns.append((doc["lns_name"], doc["tenant_id"]))

    if len(all_lns) < 2:
        raise HTTPException(status_code=500, detail="seed-demo: not enough LNS created to spawn mails")

    # 3. Generate 50 mails distributed across tenants — batched into 2 blocks (25/block)
    mail_txs: List[dict] = []
    mail_rows: List[dict] = []
    for i in range(50):
        sender_lns, sender_tenant = random.choice(all_lns)
        # Recipient = different LNS in the SAME tenant (intra-org) most of the time
        candidates = [x for x in all_lns if x[1] == sender_tenant and x[0] != sender_lns]
        if not candidates:
            candidates = [x for x in all_lns if x[0] != sender_lns]
        recipient_lns, _ = random.choice(candidates)
        ts = _demo_random_past_ts()
        subject = random.choice(mail_subjects_pool)
        body = f"Documento allegato: {subject}. — Cordiali saluti."
        doc_hash = hashlib.sha3_512((subject + body + ts).encode("utf-8")).hexdigest()
        tx_id = f"tx-{_det_hex(f'demo-mail-{i}-{ts}', 12)}"
        mail_id = f"mail-{_det_hex(f'demo-{i}-{ts}', 10)}"
        mail_rows.append({
            "mail_id": mail_id,
            "sender_lns": sender_lns,
            "recipient_lns": recipient_lns,
            "subject_redacted": "[REDACTED · CLASS-CONF]",
            "doc_hash": doc_hash,
            "sealed_at": ts,
            "bytes": len(body),
            "subject": subject,
            "body": body,
            "body_e2e_envelope": None,
            "is_e2e_encrypted": False,
            "classification": "CONF",
            "tx_id": tx_id,
            "block_index": 0,  # set after block finalise
            "attachments": None,
            "_demo": True,
        })
        mail_txs.append({
            "tx_id": tx_id,
            "kind": "NotarySeal",
            "doc_hash": doc_hash,
            "signer_entity": sender_lns,
            "timestamp": ts,
        })

    # Batch into 2 blocks of 25 tx each + persist real PQC-signed transactions
    for i in range(0, len(mail_txs), 25):
        batch = mail_txs[i:i + 25]
        block = await _finalise_batch_block(transactions=batch)
        summary["blocks_created"] += 1
        block_index = block["index"]
        batch_tx_ids = [t["tx_id"] for t in batch]
        # Patch block_index on mail rows + insert real tx rows with sigs
        tx_inserts = []
        for j, tx in enumerate(batch):
            mail_row = next(r for r in mail_rows if r["tx_id"] == tx["tx_id"])
            mail_row["block_index"] = block_index
            sender_lns = mail_row["sender_lns"]
            summary_str = f"NotarySeal · {tx['doc_hash'][:16].upper()} · CONF · 1 recipient(s)"
            canonical = ("|".join([tx["tx_id"], str(block_index), tx["timestamp"], "NotarySeal", summary_str])).encode("utf-8")
            sig_hex, signer_fp = await _pqc_sign(sender_lns, canonical, role="lns")
            tx_inserts.append({
                "tx_id": tx["tx_id"],
                "block_index": block_index,
                "timestamp": tx["timestamp"],
                "kind": "NotarySeal",
                "summary": summary_str,
                "sender_public_key": signer_fp,
                "signature": sig_hex,
                "signed_with": PQC_ALGORITHM,
                "signer_entity": sender_lns,
                "nonce": 0,
                "weight": 12_500,
                "_demo": True,
            })
        await db.transactions.insert_many(tx_inserts)

    await db.certify_mails.insert_many(mail_rows)
    summary["mails"] = len(mail_rows)

    # 4. Generate 200 Pulse messages distributed across tenants — batched into 4 blocks (50/block)
    msg_rows: List[dict] = []
    msg_txs: List[dict] = []
    for i in range(200):
        sender_lns, sender_tenant = random.choice(all_lns)
        candidates = [x for x in all_lns if x[1] == sender_tenant and x[0] != sender_lns]
        if not candidates:
            candidates = [x for x in all_lns if x[0] != sender_lns]
        recipient_lns, _ = random.choice(candidates)
        ts = _demo_random_past_ts(max_days=7)
        body = random.choice(msg_bodies_pool)
        conv_id = f"conv-{hashlib.sha3_256((sender_tenant + sender_lns + recipient_lns).encode()).hexdigest()[:12]}"
        msg_id = f"msg-{_det_hex(f'demo-msg-{i}-{ts}', 10)}"
        tx_id = f"tx-{_det_hex(f'demo-pulse-{i}-{ts}', 12)}"
        doc_hash = hashlib.sha3_512((body + ts).encode("utf-8")).hexdigest()
        msg_rows.append({
            "msg_id": msg_id,
            "conv_id": conv_id,
            "sender_lns": sender_lns,
            "recipient_lns": recipient_lns,
            "body": body,
            "is_e2e_encrypted": False,
            "tenant_id": sender_tenant,
            "sent_at": ts,
            "tx_id": tx_id,
            "block_index": 0,
            "doc_hash": doc_hash,
            "_demo": True,
        })
        msg_txs.append({
            "tx_id": tx_id,
            "kind": "PulseAnchor",
            "doc_hash": doc_hash,
            "signer_entity": sender_lns,
            "timestamp": ts,
        })

    for i in range(0, len(msg_txs), 50):
        batch = msg_txs[i:i + 50]
        block = await _finalise_batch_block(transactions=batch)
        summary["blocks_created"] += 1
        block_index = block["index"]
        tx_inserts = []
        for tx in batch:
            msg_row = next(r for r in msg_rows if r["tx_id"] == tx["tx_id"])
            msg_row["block_index"] = block_index
            sender_lns = msg_row["sender_lns"]
            summary_str = f"PulseAnchor · {tx['doc_hash'][:16].upper()} · {sender_lns}"
            canonical = ("|".join([tx["tx_id"], str(block_index), tx["timestamp"], "PulseAnchor", summary_str])).encode("utf-8")
            sig_hex, signer_fp = await _pqc_sign(sender_lns, canonical, role="lns")
            tx_inserts.append({
                "tx_id": tx["tx_id"],
                "block_index": block_index,
                "timestamp": tx["timestamp"],
                "kind": "PulseAnchor",
                "summary": summary_str,
                "sender_public_key": signer_fp,
                "signature": sig_hex,
                "signed_with": PQC_ALGORITHM,
                "signer_entity": sender_lns,
                "nonce": 0,
                "weight": 5_000,
                "_demo": True,
            })
        await db.transactions.insert_many(tx_inserts)

    await db.pulse_messages.insert_many(msg_rows)
    summary["messages"] = len(msg_rows)

    log.info("admin seed-demo complete: %s", summary)
    return {
        "ok": True,
        "summary": summary,
        "message": f"Demo seed complete: {summary['tenants']} tenants, {summary['employees']} employees, "
                   f"{summary['mails']} Certify mails, {summary['messages']} Pulse messages, "
                   f"{summary['blocks_created']} blocks notarised on-chain.",
    }


@api.get("/config/runtime")
async def get_runtime_config():
    """Public runtime configuration — surfaced to the frontend to render
    correct mode badges (Compliance vs Whistleblowing) and to disable
    features that are not active in the current deployment."""
    return {
        "compliance_mode": COMPLIANCE_MODE,
        "mixnet_enabled": MIXNET_ENABLED,
        "edition": "Compliance Edition" if COMPLIANCE_MODE else "Whistleblowing Edition",
        "edition_label_it": "Edizione Compliance" if COMPLIANCE_MODE else "Edizione Whistleblowing",
        "edition_description_it": (
            "Tracciabilità completa, log forensi, niente anonimato. Conforme NIS2/DORA/AML. Indicata per banche, assicurazioni, studi legali, PA."
            if COMPLIANCE_MODE else
            "Routing anonimo tramite mixnet a 3 rimbalzi, niente metadati esposti. Indicata per whistleblowing, giornalismo investigativo, attivismo."
        ),
        "pqc_algorithm": PQC_ALGORITHM,
        "strict_auth": STRICT_AUTH,
        "version": "1.0.0",
    }


BACKUP_CONFIRM_TOKEN = "BACKUP_YES"
BACKUP_COLLECTIONS = [
    "blocks", "transactions", "tenants", "lns",
    "certify_mails", "pulse_conversations", "pulse_messages",
    "recovery_enrollments", "qbft_nodes", "mixnet_relays",
    "meta", "keystore",
]


@api.get("/_legacy_admin_moved")
async def _legacy_admin_routes_moved() -> dict:  # pragma: no cover — info
    """Marker endpoint — admin routes were extracted in Iter_30.

    See:
      /app/backend/routes/secrets.py       → /api/admin/secrets/*
      /app/backend/routes/license_admin.py → /api/admin/license/*
      /app/backend/routes/admin_health.py  → /api/admin/health/*
      /app/backend/routes/backup.py        → /api/admin/backup/*
      /app/backend/routes/ots.py           → /api/admin/ots/*
    """
    return {"moved": True, "see": "routes/README.md"}


# ---------------------------------------------------------------------------
# Modular admin routes (Iter_29/30) — wiring
# ---------------------------------------------------------------------------

ots_routes.register(api, db=db, require_sovereign=require_platform_sovereign, chain_id=CHAIN_ID)
secrets_routes.register(
    api,
    db=db,
    require_sovereign=require_platform_sovereign,
    get_or_create_keypair=_get_or_create_keypair,
    node_labels=NODE_LABELS,
)
license_routes.register(api, require_sovereign=require_platform_sovereign)
health_routes.register(
    api,
    db=db,
    utc_iso=_utc_iso,
    qbft_status_fn=lambda: qbft_routes.qbft_status(db, quorum_required=QBFT_QUORUM),
    mixnet_status_fn=mixnet_status,
    alert_state=_alert_state,
    compliance_mode=COMPLIANCE_MODE,
    chain_id=CHAIN_ID,
)
backup_routes.register(
    api,
    db=db,
    require_sovereign=require_platform_sovereign,
    utc_iso=_utc_iso,
    backup_collections=BACKUP_COLLECTIONS,
    backup_confirm_token=BACKUP_CONFIRM_TOKEN,
    compliance_mode=COMPLIANCE_MODE,
)
lns_routes.register(
    api, db=db,
    current_user_dep=current_user,
    require_sovereign_roles_dep=lambda: require_roles(ROLE_SOVEREIGN),
    key_cache=_KEY_CACHE,
)
qbft_routes.register(api, db=db, quorum_required=QBFT_QUORUM)
certify_routes.register(
    api, db=db,
    current_user_dep=current_user, role_dep=role_dep,
    redact_for_role=_redact_for_role,
)
pulse_routes.register(
    api, db=db,
    current_user_dep=current_user, role_dep=role_dep,
    redact_for_role=_redact_for_role,
)
tenants_routes.register(
    api, db=db,
    require_platform_sovereign_dep=require_platform_sovereign,
    require_tenant_member_dep=require_tenant_member,
    pqc_algorithm=PQC_ALGORITHM,
    require_sovereign_roles_dep=lambda: require_roles(ROLE_SOVEREIGN),
    register_lns_fn=lambda req: register_lns(req, _role=ROLE_SOVEREIGN),
    license_mod=licmod,
    secrets_token_hex=secrets.token_hex,
)
keyrecovery_routes.register(
    api, db=db,
    current_user_dep=current_user,
    role_sovereign=ROLE_SOVEREIGN,
    pqc_sign_or_delegate_fn=_pqc_sign_or_delegate,
    finalise_block_fn=_finalise_block_for_tx,
    pqc_algorithm=PQC_ALGORITHM,
    secrets_token_hex=secrets.token_hex,
)
auth_routes.register(
    api,
    db=db,
    current_user_dep=current_user,
    require_platform_sovereign_dep=require_platform_sovereign,
    envelope_mod=envelope,
    audit_mod=audit,
    role_sovereign=ROLE_SOVEREIGN,
    role_auditor=ROLE_AUDITOR,
    role_vendor=ROLE_VENDOR,
)
audit_public_routes.register(
    api, db=db,
    require_platform_sovereign_dep=require_platform_sovereign,
    pqc_algorithm=PQC_ALGORITHM,
    chain_id=CHAIN_ID,
)
certify_mutating_routes.register(
    api, db=db,
    current_user_dep=current_user,
    pqc_sign_fn=_pqc_sign,
    pqc_sign_or_delegate_fn=_pqc_sign_or_delegate,
    pqc_verify_fn=_pqc_verify,
    finalise_block_fn=_finalise_block_for_tx,
    envelope_mod=envelope,
    audit_mod=audit,
    det_hex_fn=_det_hex,
    fire_pec_webhook_fn=_fire_pec_webhook,
    pqc_algorithm=PQC_ALGORITHM,
)
pulse_mutating_routes.register(
    api, db=db,
    current_user_dep=current_user,
    pqc_sign_fn=_pqc_sign,
    pqc_sign_or_delegate_fn=_pqc_sign_or_delegate,
    finalise_block_fn=_finalise_block_for_tx,
    det_hex_fn=_det_hex,
    envelope_mod=envelope,
    audit_mod=audit,
    current_rln_epoch_fn=_current_rln_epoch,
    rln_commitment_fn=_rln_commitment,
    rln_real_nullifier_fn=_rln_real_nullifier,
    pulse_session_fingerprint_fn=_pulse_session_fingerprint,
    conv_id_fn=_conv_id,
    route_through_mixnet_fn=_route_through_mixnet,
    pqc_algorithm=PQC_ALGORITHM,
    rln_max_per_epoch=RLN_MAX_PER_EPOCH,
    rln_epoch_seconds=RLN_EPOCH_SECONDS,
    pulse_anchor_every=PULSE_ANCHOR_EVERY,
)
leads_routes.register(
    api, db=db,
    require_platform_sovereign_dep=require_platform_sovereign,
    pqc_sign_fn=_pqc_sign,
    finalise_block_fn=_finalise_block_for_tx,
    det_hex_fn=_det_hex,
    pqc_algorithm=PQC_ALGORITHM,
)
attachments_routes.register(
    api, db=db,
    current_user_dep=current_user,
)
pec_webhook_routes.register(
    api, db=db,
    require_tenant_member_dep=require_tenant_member,
)
vendor_rln_routes.register(
    api, db=db,
    require_roles_dep=require_roles,
    role_sovereign=ROLE_SOVEREIGN,
    role_auditor=ROLE_AUDITOR,
    current_rln_epoch_fn=_current_rln_epoch,
    get_or_create_rln_bn_secret_fn=_get_or_create_rln_bn_secret,
    rln_zk_prove_fn=rln_zk_prove,
    rln_zk_verify_fn=rln_zk_verify,
    rln_commitment_fn=_rln_commitment,
    rln_real_nullifier_fn=_rln_real_nullifier,
    rln_field_prime=_RLN_FIELD_P,
    rln_epoch_seconds=RLN_EPOCH_SECONDS,
    rln_max_per_epoch=RLN_MAX_PER_EPOCH,
)
ledger_public_routes.register(
    api, db=db,
    current_user_dep=current_user,
    pqc_verify_fn=_pqc_verify,
    tx_canonical_message_fn=_tx_canonical_message,
    pk_fingerprint_fn=_pk_fingerprint,
    pqc_algorithm=PQC_ALGORITHM,
    pqc_pk_size=PQC_PK_SIZE,
    pqc_sk_size=PQC_SK_SIZE,
    pqc_sig_size=PQC_SIG_SIZE,
    rust_module=_rust,
    rust_available=_RUST_AVAILABLE,
    rust_error=_RUST_ERROR,
)
explorer_routes.register(
    api, db=db,
    pqc_verify_fn=_pqc_verify,
    tx_canonical_message_fn=_tx_canonical_message,
    pqc_algorithm=PQC_ALGORITHM,
)


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def _on_startup() -> None:
    try:
        # Iter_28: passphrase-based at-rest secret manager. Must run BEFORE
        # any keystore access so signing keys can be opened on demand.
        await secret_manager.bootstrap(db)
        # Iter_28: load the signed license file (or fall back to community).
        licmod.load_from_disk()
        # Iter_27 idempotent migration: legacy blocks (pre-merkle / pre-chain_id)
        # are PATCHED IN-PLACE with the missing fields instead of being wiped.
        # This preserves the entire on-chain history across software upgrades.
        # Algorithm:
        #   1. Find blocks without merkle_root: compute it from the block's
        #      transactions (or use the block_hash as a placeholder) and write
        #      it back via $set.
        #   2. Find blocks without chain_id: tag them with "legacy-v0" so the
        #      verify path knows to skip the new chain-binding check on them.
        # Greenfield installs skip both branches because db.blocks is empty.
        legacy_count = await db.blocks.count_documents(
            {"$or": [{"merkle_root": {"$exists": False}}, {"chain_id": {"$exists": False}}]}
        )
        if legacy_count > 0:
            log.info("iter_27 idempotent migration: %d legacy blocks to patch", legacy_count)
            cursor = db.blocks.find(
                {"$or": [{"merkle_root": {"$exists": False}}, {"chain_id": {"$exists": False}}]},
                {"_id": 0, "index": 1, "block_hash": 1, "transactions": 1, "merkle_root": 1, "chain_id": 1},
            )
            patched = 0
            async for blk in cursor:
                set_doc = {}
                if not blk.get("merkle_root"):
                    # Reconstruct deterministically from the transactions list,
                    # or fall back to the block_hash if tx list is missing.
                    try:
                        from hashlib import sha3_512
                        tx_ids = [t.get("tx_id", "") for t in (blk.get("transactions") or [])]
                        set_doc["merkle_root"] = sha3_512("|".join(tx_ids).encode()).hexdigest() if tx_ids else (blk.get("block_hash") or "0" * 128)
                    except Exception:
                        set_doc["merkle_root"] = blk.get("block_hash") or "0" * 128
                if not blk.get("chain_id"):
                    set_doc["chain_id"] = "legacy-v0"
                if set_doc:
                    await db.blocks.update_one({"index": blk["index"]}, {"$set": set_doc})
                    patched += 1
            log.info("iter_27 migration: patched %d legacy blocks in-place (NO data loss)", patched)
        # P2 hardening: enforce uniqueness of lns_name at the data layer
        # so a future buggy seed cannot regress iteration_1 again.
        await db.lns.create_index("lns_name", unique=True)
        await db.transactions.create_index([("block_index", -1)])
        await db.blocks.create_index([("index", -1)])
        await db.pulse_messages.create_index([("conv_id", 1), ("sealed_at", 1)])
        await db.pulse_conversations.create_index("conv_id", unique=True)
        await db.pulse_sessions.create_index("conv_id", unique=True)
        await db.rln_quota.create_index([("lns", 1), ("epoch", 1)], unique=True)
        await db.mixnet_relays.create_index("node_id", unique=True)
        await db.vendor_tenants.create_index("tenant_id", unique=True)
        await db.vendor_tenants.create_index("domain", unique=True)
        await db.tenants.create_index("tenant_id", unique=True)
        await db.tenants.create_index("domain", unique=True)
        await db.keystore.create_index("entity", unique=True)
        await db.alert_webhooks.create_index("url", unique=True)
        # Pre-generate real ML-DSA-65 keys for validators + console admin.
        # If the envelope is LOCKED (no key set yet) we skip this — keypairs
        # will be materialised lazily after the operator calls /unlock.
        if secret_manager.STATE.unlocked:
            for (label, _role) in NODE_LABELS:
                await _get_or_create_keypair(label, role="validator")
            await _get_or_create_keypair("admin.console.admin", role="admin")
            log.info("PQC keystore ready · algorithm=%s · pk=%d sk=%d sig=%d",
                     PQC_ALGORITHM, PQC_PK_SIZE, PQC_SK_SIZE, PQC_SIG_SIZE)
        else:
            log.warning("PQC keystore NOT materialised — envelope locked (%s)",
                        secret_manager.STATE.locked_reason)
        await _seed_if_empty()
        # Idempotent: ensure mixnet topology exists even on an upgraded DB.
        if await db.mixnet_relays.count_documents({}) == 0:
            relays = []
            for (label, layer, region, lat) in MIXNET_RELAYS_SEED:
                relays.append({
                    "node_id": f"mix-{_det_hex(label, 6)}",
                    "label": label,
                    "region": region,
                    "layer": layer,
                    "kem_pk_fingerprint": _det_hex(f"mix-pk-{label}", 8).upper(),
                    "latency_ms": lat,
                })
            await db.mixnet_relays.insert_many(relays)
            log.info("Mixnet topology seeded (%d relays)", len(relays))
        await _seed_tenants_if_empty()
        # Periodic infrastructure health monitor.
        asyncio.create_task(_infra_health_loop())
        # Iter_30: background loop that promotes OTS anchors to
        # btc_attested=True as soon as the calendar publishes the
        # Bitcoin block-header attestation (≈3-6h after submission).
        # Cheap no-op when LATTICE_OTS_ENABLED is not set.
        ots_interval = float(os.environ.get("LATTICE_OTS_UPGRADE_INTERVAL_SEC", "21600"))
        asyncio.create_task(ots_anchor.auto_upgrade_loop(db, interval_sec=ots_interval))
    except Exception as e:  # pragma: no cover — first-boot resilience
        log.exception("Seed failure: %s", e)


@app.on_event("shutdown")
async def _on_shutdown() -> None:
    client.close()
