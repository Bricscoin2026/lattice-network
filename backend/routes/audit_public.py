"""
Lattice Network — /api/audit/* public routes (Iter_37)
========================================================

Public unauthenticated audit page for tenants + chain integrity verifier.
"""
from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException

import audit
import core

router = APIRouter(prefix="/audit", tags=["audit"])


def register(
    api: APIRouter,
    *,
    db: Any,
    require_platform_sovereign_dep: Callable,
    pqc_algorithm: str,
    chain_id: str,
) -> None:
    @router.get("/public/{slug}")
    async def audit_public_endpoint(slug: str) -> dict:
        """Public audit page — works with tenant_id, domain or slug."""
        tenant = await db.tenants.find_one(
            {"$or": [{"domain": {"$regex": f"^{slug}\\.?", "$options": "i"}},
                     {"tenant_id": slug}]},
            {"_id": 0, "tenant_id": 1, "name": 1, "domain": 1, "created_at": 1},
        )
        if not tenant:
            cursor = db.tenants.find({}, {"_id": 0, "tenant_id": 1, "name": 1,
                                          "domain": 1, "created_at": 1})
            async for t in cursor:
                if t.get("domain", "").split(".")[0].lower() == slug.lower():
                    tenant = t
                    break
        if not tenant:
            valid = []
            async for t in db.tenants.find({}, {"_id": 0, "domain": 1, "name": 1}).limit(8):
                d = t.get("domain", "")
                if d:
                    valid.append({"slug": d.split(".")[0], "name": t.get("name"), "domain": d})
            raise HTTPException(
                status_code=404,
                detail=(f"no tenant matches slug '{slug}' · valid examples: "
                        + ", ".join([v["slug"] for v in valid[:3]])),
            )
        domain = tenant.get("domain", "")
        employees = await db.lns.count_documents({"tenant_id": tenant["tenant_id"]})
        tx_total = 0
        if domain:
            tx_total = await db.transactions.count_documents(
                {"signer_entity": {"$regex": f"\\.{domain}$"}},
            )
        recent = []
        if domain:
            cursor = db.transactions.find(
                {"signer_entity": {"$regex": f"\\.{domain}$"}},
                {"_id": 0, "tx_id": 1, "block_index": 1, "kind": 1,
                 "timestamp": 1, "doc_hash": 1, "signer_entity": 1, "signed_with": 1},
            ).sort("block_index", -1).limit(10)
            async for tx in cursor:
                recent.append({
                    "tx_id": tx.get("tx_id"),
                    "block_index": tx.get("block_index"),
                    "kind": tx.get("kind"),
                    "timestamp": tx.get("timestamp"),
                    "doc_hash_short": (tx.get("doc_hash") or "")[:16],
                    "signer_short": (tx.get("signer_entity") or "").split(".")[0],
                    "signed_with": tx.get("signed_with", "—"),
                })
        block_height = (await db.meta.find_one({"_id": "seeded"}, {"block_height": 1}) or {}).get("block_height", 0)
        return {
            "tenant": {
                "name": tenant.get("name"),
                "domain": domain,
                "registered_at": tenant.get("created_at"),
                "tenant_id_short": tenant.get("tenant_id", "")[:14] + "…",
            },
            "footprint": {
                "employees": employees,
                "transactions_total": tx_total,
                "recent_transactions": recent,
            },
            "network": {
                "chain_id": chain_id,
                "block_height": block_height,
                "pqc_algorithm": pqc_algorithm,
                "consensus": "QBFT · 2f+1 ML-DSA-65",
            },
            "checked_at": core.utc_iso(),
        }

    @router.get("/verify")
    async def audit_verify_chain(
        _u: dict = Depends(require_platform_sovereign_dep()),
    ) -> dict:
        """Verify the SHA3-512 audit-log hash chain integrity."""
        ok, broken_at = await audit.verify_chain(db)
        total = await db.audit_log.count_documents({})
        return {
            "ok": ok,
            "total_entries": total,
            "broken_at_seq": broken_at,
            "algorithm": "SHA3-512 hash chain",
            "verified_at": core.utc_iso(),
        }

    api.include_router(router)
