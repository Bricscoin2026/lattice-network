"""
Lattice Network — /api/tenants/* read-only routes (Iter_34)
=============================================================

Read-only endpoints: public directory, list, get, employees, stats.

The mutating endpoint `POST /tenants/register` STAYS in server.py
because it has to call `register_lns` to bootstrap the founder LNS —
that helper is itself an unextracted FastAPI route. Once `routes/lns.py`
gains its mutating endpoints we'll move /tenants/register here too.
"""
from __future__ import annotations

from typing import Any, Callable, List

from fastapi import APIRouter, Depends, HTTPException

import core
from models import (
    LnsRecord, TenantRecord, TenantRegisterRequest, TenantRegisterResponse,
    RegisterRequest,
)

router = APIRouter(prefix="/tenants", tags=["tenants"])

# Module-level callable populated by `register()` so other modules (e.g.
# server.py::admin_chain_seed_demo) can invoke the tenant-onboarding flow
# as a plain coroutine without going through HTTP.
do_register_tenant: Callable | None = None


def register(
    api: APIRouter,
    *,
    db: Any,
    require_platform_sovereign_dep: Callable,
    require_tenant_member_dep: Callable,
    pqc_algorithm: str,
    require_sovereign_roles_dep: Callable | None = None,
    register_lns_fn: Callable | None = None,
    license_mod: Any | None = None,
    secrets_token_hex: Callable | None = None,
) -> None:
    async def _do_register_tenant(req: TenantRegisterRequest) -> TenantRegisterResponse:
        """Onboard a new enterprise: reserve its domain + create the founder LNS."""
        prefix = req.domain_prefix.strip().lower()
        domain = f"{prefix}.lns"
        existing = await db.tenants.find_one({"domain": domain})
        if existing:
            raise HTTPException(status_code=409, detail=f"domain already taken: {domain}")
        name = req.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="name required")
        # License quota enforcement.
        current_tenants = await db.tenants.count_documents({})
        if not license_mod.check_tenant_quota(current_tenants):
            edition = (license_mod.STATE.active or {}).get("edition", "community")
            max_t = license_mod.STATE.active.get("max_tenants")
            raise HTTPException(
                status_code=402,
                detail=(
                    f"License quota exceeded: edition='{edition}' allows max_tenants={max_t}, "
                    f"already {current_tenants} active. Upgrade the license to add more."
                ),
            )
        tenant_id = f"tnt-{secrets_token_hex(6)}"
        admin_full_lns = f"{req.admin_lns_prefix.strip().lower()}.{domain}"
        if await db.lns.find_one({"lns_name": admin_full_lns}):
            raise HTTPException(status_code=409,
                                detail=f"admin lns already exists: {admin_full_lns}")
        created_at = core.utc_iso()
        await db.tenants.insert_one({
            "tenant_id": tenant_id, "name": name, "domain": domain,
            "admin_lns": admin_full_lns, "created_at": created_at,
            "employees_count": 0,
        })
        sub_req = RegisterRequest(
            lns_name=admin_full_lns,
            department="Direzione",
            admin=req.admin_display_name,
            display_name=req.admin_display_name,
            tenant_id=tenant_id,
            role="admin",
        )
        sub_resp = await register_lns_fn(sub_req)
        keypair_json = None
        if sub_resp.public_key_hex and sub_resp.secret_key_hex:
            keypair_json = {
                "version": 1,
                "algorithm": pqc_algorithm,
                "lns_name": admin_full_lns,
                "tenant_id": tenant_id,
                "did": sub_resp.did,
                "public_key_hex": sub_resp.public_key_hex,
                "secret_key_hex": sub_resp.secret_key_hex,
                "created_at": created_at,
            }
        return TenantRegisterResponse(
            ok=True, tenant_id=tenant_id, name=name, domain=domain,
            admin_lns=admin_full_lns, admin_did=sub_resp.did,
            admin_tx_id=sub_resp.tx_id, block_index=sub_resp.block_index,
            created_at=created_at, admin_keypair_json=keypair_json,
        )

    # Expose to module-level so server.py (seed-demo) can call it directly.
    global do_register_tenant
    do_register_tenant = _do_register_tenant

    @router.post("/register", response_model=TenantRegisterResponse)
    async def register_tenant_endpoint(
        req: TenantRegisterRequest,
        _role: str = Depends(require_sovereign_roles_dep()),
    ) -> TenantRegisterResponse:
        return await _do_register_tenant(req)

    @router.get("/public")
    async def list_tenants_public() -> List[dict]:
        """Public directory of companies on the Lattice network."""
        cursor = db.tenants.find(
            {}, {"_id": 0, "tenant_id": 1, "name": 1, "domain": 1, "created_at": 1},
        ).sort("created_at", -1)
        return [doc async for doc in cursor]

    @router.get("", response_model=List[TenantRecord])
    async def list_tenants(_u: dict = Depends(require_platform_sovereign_dep())) -> List[TenantRecord]:
        cursor = db.tenants.find({}, {"_id": 0}).sort("created_at", -1)
        return [TenantRecord(**doc) async for doc in cursor]

    @router.get("/{tenant_id}", response_model=TenantRecord)
    async def get_tenant(
        tenant_id: str,
        user: dict = Depends(require_tenant_member_dep()),
    ) -> TenantRecord:
        doc = await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail=f"tenant not found: {tenant_id}")
        return TenantRecord(**doc)

    @router.get("/{tenant_id}/employees", response_model=List[LnsRecord])
    async def list_tenant_employees(
        tenant_id: str,
        user: dict = Depends(require_tenant_member_dep()),
    ) -> List[LnsRecord]:
        # Join db.lns with db.keystore so the response carries the X25519
        # `enc_pk_hex` used by the Key Recovery flow to seal Shamir shares
        # for each nominated guardian. Without this field the frontend cannot
        # mark a colleague as "ready" to act as guardian.
        rows = await db.lns.find({"tenant_id": tenant_id}, {"_id": 0}) \
            .sort("registered_at", 1).to_list(None)
        if not rows:
            return []
        names = [r["lns_name"] for r in rows]
        ks_cursor = db.keystore.find(
            {"entity": {"$in": names}},
            {"_id": 0, "entity": 1, "enc_pk_hex": 1},
        )
        enc_map = {d["entity"]: d.get("enc_pk_hex") async for d in ks_cursor}
        for r in rows:
            r["enc_pk_hex"] = enc_map.get(r["lns_name"])
        return [LnsRecord(**doc) for doc in rows]

    @router.get("/{tenant_id}/stats")
    async def tenant_stats(
        tenant_id: str,
        user: dict = Depends(require_tenant_member_dep()),
    ) -> dict:
        """KPI di una singola azienda (visibile solo ai membri + sovereign)."""
        tenant = await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
        if not tenant:
            raise HTTPException(status_code=404, detail="tenant not found")

        employees_total = await db.lns.count_documents({"tenant_id": tenant_id})
        employees_active = await db.lns.count_documents(
            {"tenant_id": tenant_id, "status": {"$ne": "REVOKED"}},
        )
        employees_revoked = await db.lns.count_documents(
            {"tenant_id": tenant_id, "status": "REVOKED"},
        )
        domain = tenant.get("domain", "")
        suffix = f".{domain}" if domain else None
        certify_q: dict = {}
        if suffix:
            certify_q = {"$or": [
                {"from_lns": {"$regex": f"{suffix}$"}},
                {"to_lns": {"$elemMatch": {"$regex": f"{suffix}$"}}},
            ]}
        certify_total = await db.certify_mails.count_documents(certify_q) if suffix else 0
        pulse_q: dict = {}
        if suffix:
            pulse_q = {"$or": [
                {"from_lns": {"$regex": f"{suffix}$"}},
                {"to_lns": {"$regex": f"{suffix}$"}},
            ]}
        pulse_total = await db.pulse_messages.count_documents(pulse_q) if suffix else 0
        roles_breakdown: dict[str, int] = {}
        async for doc in db.lns.aggregate([
            {"$match": {"tenant_id": tenant_id}},
            {"$group": {"_id": "$role", "n": {"$sum": 1}}},
        ]):
            roles_breakdown[doc["_id"] or "unknown"] = doc["n"]
        latest_tx_q: dict = {}
        if suffix:
            latest_tx_q = {"signer": {"$regex": f"{suffix}$"}}
        latest_tx_count = await db.transactions.count_documents(latest_tx_q) if suffix else 0
        return {
            "tenant_id": tenant_id,
            "tenant_name": tenant.get("name"),
            "domain": domain,
            "employees_total": employees_total,
            "employees_active": employees_active,
            "employees_revoked": employees_revoked,
            "certify_mails_total": certify_total,
            "pulse_messages_total": pulse_total,
            "on_chain_tx_total": latest_tx_count,
            "roles_breakdown": roles_breakdown,
            "computed_at": core.utc_iso(),
            "caller_role": user.get("role"),
        }

    api.include_router(router)
