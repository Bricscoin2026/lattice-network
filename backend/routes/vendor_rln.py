"""
Lattice Network — /api/vendor/* + /api/rln/* routes (Iter_40)
==============================================================

Read-only endpoints (vendor portfolio + ZK-RLN public introspection).
Extracted verbatim from server.py — Iter_40.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, List, Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from models import RlnQuota, VendorStats, VendorTenant


router = APIRouter(tags=["vendor"])


class RlnZkVerifyRequest(BaseModel):
    epoch: int
    commitment_hex: str
    nullifier_hex: str
    A_hex: str
    B_hex: str
    z_hex: str


def register(
    api: APIRouter,
    *,
    db: Any,
    require_roles_dep: Callable,
    role_sovereign: str,
    role_auditor: str,
    current_rln_epoch_fn: Callable,
    get_or_create_rln_bn_secret_fn: Callable,
    rln_zk_prove_fn: Callable,
    rln_zk_verify_fn: Callable,
    rln_commitment_fn: Callable,
    rln_real_nullifier_fn: Callable,
    rln_field_prime: int,
    rln_epoch_seconds: int,
    rln_max_per_epoch: int,
) -> None:
    # /vendor/*
    @router.get("/vendor/tenants", response_model=List[VendorTenant])
    async def vendor_tenants(
        health: Optional[Literal["HEALTHY", "DEGRADED", "OFFLINE"]] = None,
        tier: Optional[Literal["TRIAL", "STANDARD", "ENTERPRISE", "SOVEREIGN"]] = None,
    ):
        q: dict = {}
        if health:
            q["health"] = health
        if tier:
            q["license_tier"] = tier
        rows = await db.vendor_tenants.find(q, {"_id": 0}).sort("mrr_eur", -1).to_list(None)
        now = datetime.now(timezone.utc)
        for r in rows:
            if r["health"] != "OFFLINE":
                r["last_heartbeat_at"] = (now - timedelta(seconds=random.randint(1, 90))).isoformat()
        return [VendorTenant(**r) for r in rows]

    @router.get("/vendor/stats", response_model=VendorStats)
    async def vendor_stats() -> VendorStats:
        rows = await db.vendor_tenants.find({}, {"_id": 0}).to_list(None)
        total = len(rows)
        healthy = sum(1 for r in rows if r["health"] == "HEALTHY")
        degraded = sum(1 for r in rows if r["health"] == "DEGRADED")
        offline = sum(1 for r in rows if r["health"] == "OFFLINE")
        nodes_total = sum(r["nodes_total"] for r in rows)
        nodes_active = sum(r["nodes_active"] for r in rows)
        seats = sum(r["license_seats"] for r in rows)
        mrr = sum(r["mrr_eur"] for r in rows)
        return VendorStats(
            tenants_total=total,
            tenants_healthy=healthy,
            tenants_degraded=degraded,
            tenants_offline=offline,
            nodes_total=nodes_total,
            nodes_active=nodes_active,
            seats_sold=seats,
            mrr_eur=mrr,
            arr_eur=mrr * 12,
        )

    # /rln/*
    @router.get("/rln/zk/prove/{lns}")
    async def rln_zk_prove_endpoint(
        lns: str,
        _role: str = Depends(require_roles_dep(role_sovereign, role_auditor)),
    ) -> dict:
        lns_n = lns.strip().lower()
        epoch = current_rln_epoch_fn()
        secret = await get_or_create_rln_bn_secret_fn(lns_n)
        proof = rln_zk_prove_fn(secret, epoch)
        proof["lns"] = lns_n
        return proof

    @router.post("/rln/zk/verify")
    async def rln_zk_verify_endpoint(req: RlnZkVerifyRequest) -> dict:
        proof_dict = req.model_dump()
        ok = rln_zk_verify_fn(proof_dict)
        return {
            "ok": ok,
            "scheme": "Chaum-Pedersen · BN254 G1 · Fiat-Shamir SHA3-256",
            "epoch": req.epoch,
            "detail": (
                "Sigma proof verified: prover knows secret x s.t. commitment=x·G and nullifier=x·G_epoch."
                if ok else
                "Sigma proof failed verification — either the proof was tampered with or the prover does not know the secret."
            ),
        }

    @router.get("/rln/quota", response_model=RlnQuota)
    async def rln_quota(lns: str) -> RlnQuota:
        lns_n = lns.strip().lower()
        epoch = current_rln_epoch_fn()
        doc = await db.rln_quota.find_one({"lns": lns_n, "epoch": epoch}, {"_id": 0})
        used = int(doc.get("used", 0)) if doc else 0
        nullifier_int = await rln_real_nullifier_fn(lns_n, epoch)
        return RlnQuota(
            lns=lns_n,
            epoch=epoch,
            epoch_seconds=rln_epoch_seconds,
            used=used,
            max_per_epoch=rln_max_per_epoch,
            nullifier_seed=f"{nullifier_int:064x}".upper(),
        )

    @router.get("/rln/commitment/{lns}")
    async def rln_commitment(lns: str) -> dict:
        lns_n = lns.strip().lower()
        commitment = await rln_commitment_fn(lns_n)
        return {
            "lns": lns_n,
            "hash_function": "Poseidon (Starknet, felt prime)",
            "field_prime_hex": f"{rln_field_prime:064x}",
            "commitment_hex": f"{commitment:064x}",
            "commitment_decimal": str(commitment),
            "epoch_seconds": rln_epoch_seconds,
            "implementation": "poseidon-py 0.2.0",
        }

    @router.get("/rln/nullifiers")
    async def rln_recent_nullifiers(limit: int = 20) -> List[dict]:
        cursor = db.rln_nullifiers.find({}, {"_id": 0}).sort([("observed_at", -1)]).limit(limit)
        return [doc async for doc in cursor]

    api.include_router(router)
