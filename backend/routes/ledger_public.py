"""
Lattice Network — public ledger / PQC / Rust read-only routes (Iter_40)
=========================================================================

    GET /api/ledger/stats
    GET /api/ledger/blocks
    GET /api/ledger/verify/{tx_id}
    GET /api/transactions
    GET /api/transactions/export
    GET /api/keystore/{entity}
    GET /api/pqc/info
    GET /api/rust/info
    GET /api/rust/selftest

Extracted verbatim from server.py — Iter_40.
"""
from __future__ import annotations

import csv
import io
import json
import secrets
from datetime import datetime, timezone
from typing import Any, Callable, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from models import (
    Block,
    LedgerStats,
    Transaction,
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


router = APIRouter(tags=["ledger"])


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def register(
    api: APIRouter,
    *,
    db: Any,
    current_user_dep: Callable,
    pqc_verify_fn: Callable,
    tx_canonical_message_fn: Callable,
    pk_fingerprint_fn: Callable,
    pqc_algorithm: str,
    pqc_pk_size: int,
    pqc_sk_size: int,
    pqc_sig_size: int,
    rust_module: Any,
    rust_available: bool,
    rust_error: Optional[str],
) -> None:

    @router.get("/ledger/stats", response_model=LedgerStats)
    async def ledger_stats() -> LedgerStats:
        last_block = await db.blocks.find_one({}, {"_id": 0}, sort=[("index", -1)])
        tx_total = await db.transactions.count_documents({})
        block_height = (last_block["index"] if last_block else 0)
        return LedgerStats(
            block_height=block_height,
            total_transactions=tx_total,
            pending_transactions=0,
            finality_ms=420,
            chain_id="lattice-sovereign-it-prod",
            last_block_hash=last_block["block_hash"] if last_block else "0" * 128,
            last_block_at=last_block["timestamp"] if last_block else _utc_iso(),
            qbft_round=block_height,
        )

    @router.get("/ledger/blocks", response_model=List[Block])
    async def list_blocks(limit: int = Query(20, ge=1, le=200)) -> List[Block]:
        cursor = db.blocks.find({}, {"_id": 0}).sort("index", -1).limit(limit)
        return [Block(**b) async for b in cursor]

    TxKindLiteral = Literal[
        "IdentityRegister", "NotarySeal", "IdentityRevoke", "IdentityDelete",
        "DeliveryReceipt", "LeadCapture", "KeyShareEnroll", "KeyShareRecover",
    ]

    @router.get("/transactions", response_model=List[Transaction])
    async def list_transactions(
        limit: int = Query(40, ge=1, le=500),
        kind: Optional[TxKindLiteral] = None,
    ) -> List[Transaction]:
        q: dict = {}
        if kind:
            q["kind"] = kind
        cursor = db.transactions.find(q, {"_id": 0}).sort("block_index", -1).limit(limit)
        return [Transaction(**t) async for t in cursor]

    @router.get("/transactions/export")
    async def export_transactions(
        fmt: Literal["csv", "json"] = Query("csv"),
        kind: Optional[TxKindLiteral] = None,
        limit: int = Query(2000, ge=1, le=20000),
    ):
        q: dict = {}
        if kind:
            q["kind"] = kind
        rows = await db.transactions.find(q, {"_id": 0}).sort("block_index", -1).limit(limit).to_list(None)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        if fmt == "json":
            payload = json.dumps(rows, indent=2).encode()
            return Response(
                content=payload,
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename=lattice-tx-{stamp}.json"},
            )
        buf = io.StringIO()
        writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["tx_id", "block_index", "timestamp", "kind", "summary",
                         "sender_public_key", "signature"])
        for r in rows:
            writer.writerow([
                r.get("tx_id", ""),
                r.get("block_index", ""),
                r.get("timestamp", ""),
                r.get("kind", ""),
                r.get("summary", ""),
                r.get("sender_public_key", ""),
                r.get("signature", ""),
            ])
        return Response(
            content=buf.getvalue().encode(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=lattice-tx-{stamp}.csv"},
        )

    @router.get("/ledger/verify/{tx_id}", response_model=VerifyResponse)
    async def ledger_verify(tx_id: str) -> VerifyResponse:
        tx = await db.transactions.find_one({"tx_id": tx_id}, {"_id": 0})
        if not tx:
            raise HTTPException(status_code=404, detail=f"transaction not found: {tx_id}")
        msg = tx_canonical_message_fn(tx)
        signed_with = tx.get("signed_with", "legacy-seed")
        if signed_with != pqc_algorithm:
            return VerifyResponse(
                ok=False, tx_id=tx_id, algorithm=pqc_algorithm,
                signed_with=signed_with,
                public_key_size_bytes=pqc_pk_size,
                signature_size_bytes=pqc_sig_size,
                message_hex=msg.hex(),
                detail="Seeded transaction — signed with deterministic placeholder, not real PQC. New transactions emitted after upgrade are signed with NIST FIPS 204 ML-DSA-65 and verifiable.",
            )
        signer = tx.get("signer_entity") or ""
        ok = await pqc_verify_fn(signer, msg, tx.get("signature", ""))
        return VerifyResponse(
            ok=ok, tx_id=tx_id, algorithm=pqc_algorithm,
            signed_with=signed_with,
            signer_entity=signer,
            public_key_fingerprint=tx.get("sender_public_key"),
            public_key_size_bytes=pqc_pk_size,
            signature_size_bytes=pqc_sig_size,
            message_hex=msg.hex(),
            detail=("Signature verified against signer's persisted public key."
                    if ok else
                    "Signature DID NOT verify — bytes have been tampered or signer key rotated."),
        )

    @router.get("/keystore/{entity}", response_model=PublicKeyResponse)
    async def keystore_get(entity: str, user: dict = Depends(current_user_dep)) -> PublicKeyResponse:
        doc = await db.keystore.find_one({"entity": entity}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail=f"no key on file for entity: {entity}")
        caller_tenant = user.get("tenant_id")
        if caller_tenant:
            is_infra = entity.startswith(("VAL-", "OBS-", "MIX-", "GENESIS"))
            if not is_infra:
                lns_doc = await db.lns.find_one({"lns_name": entity}, {"tenant_id": 1})
                if not lns_doc or lns_doc.get("tenant_id") != caller_tenant:
                    raise HTTPException(
                        status_code=403,
                        detail="cross-company key lookup forbidden · puoi vedere solo le chiavi della tua azienda",
                    )
        pk_hex = doc["pk_hex"]
        return PublicKeyResponse(
            entity=entity,
            role=doc.get("role", "lns"),
            algorithm=pqc_algorithm,
            public_key_hex=pk_hex,
            public_key_size_bytes=len(pk_hex) // 2,
            fingerprint=doc.get("fingerprint", pk_fingerprint_fn(bytes.fromhex(pk_hex))),
            created_at=doc.get("created_at", _utc_iso()),
        )

    @router.get("/pqc/info")
    async def pqc_info() -> dict:
        return {
            "algorithm": pqc_algorithm,
            "standard": "NIST FIPS 204 (ML-DSA-65, formerly Dilithium3)",
            "public_key_size_bytes": pqc_pk_size,
            "secret_key_size_bytes": pqc_sk_size,
            "signature_size_bytes": pqc_sig_size,
            "kem_for_pulse": "ML-KEM-768 (NIST FIPS 203, formerly Kyber-768)",
            "implementation": "pqcrypto 0.4.0 · PQClean reference",
            "live": True,
        }

    @router.get("/rust/info")
    async def rust_info() -> dict:
        if not rust_available:
            return {
                "available": False,
                "error": rust_error,
                "hint": "Build with: cd /app/lattice/prod/lattice-py && maturin develop --release",
            }
        sample = b"lattice.rust.bridge.proof"
        sample_hash = rust_module.sha3_512_hex(sample)
        return {
            "available": True,
            "version": rust_module.version(),
            "binding": "PyO3 0.22 · maturin",
            "crate": "lattice-crypto (BSL 1.1) → lattice-py (Commercial)",
            "exposes": [
                "sha3_512_hex(bytes) -> str",
                "sha3_256_hex(bytes) -> str",
                "fingerprint_pubkey(bytes) -> str",
                "ml_dsa_65_keypair() -> (pk, sk)",
                "ml_dsa_65_sign(sk, msg) -> sig",
                "ml_dsa_65_verify(pk, msg, sig) -> bool",
            ],
            "proof": {
                "input_utf8": sample.decode(),
                "sha3_512_rust_hex": sample_hash,
                "computed_by": "Rust crate `lattice-crypto::compute_sha3_512` via PyO3",
            },
        }

    @router.get("/rust/selftest")
    async def rust_selftest() -> dict:
        if not rust_available:
            raise HTTPException(status_code=503, detail=f"rust bridge unavailable: {rust_error}")
        pk, sk = rust_module.ml_dsa_65_keypair()
        nonce = secrets.token_bytes(48)
        sig = rust_module.ml_dsa_65_sign(sk, nonce)
        ok = rust_module.ml_dsa_65_verify(pk, nonce, sig)
        return {
            "algorithm": "ML-DSA-65 · NIST FIPS 204",
            "computed_in": "Rust (lattice-crypto via PyO3)",
            "public_key_bytes": len(pk),
            "secret_key_bytes": len(sk),
            "signature_bytes": len(sig),
            "nonce_hex": nonce.hex(),
            "signature_first_32_hex": sig[:32].hex(),
            "fingerprint": rust_module.fingerprint_pubkey(pk),
            "verify_ok": ok,
        }

    api.include_router(router)
