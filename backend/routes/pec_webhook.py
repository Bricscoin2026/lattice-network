"""
Lattice Network — /api/tenants/{id}/pec-webhook routes (Iter_40)
=================================================================

PUT  /api/tenants/{tenant_id}/pec-webhook
GET  /api/tenants/{tenant_id}/pec-webhook

Tenant-level PEC delivery-receipt webhook configuration.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["tenants"])


class TenantWebhookConfig(BaseModel):
    webhook_url: str = Field(..., min_length=8, max_length=512)
    webhook_secret: Optional[str] = Field(None, max_length=128)


def register(
    api: APIRouter,
    *,
    db: Any,
    require_tenant_member_dep: Callable,
) -> None:

    @router.put("/tenants/{tenant_id}/pec-webhook")
    async def configure_pec_webhook(
        tenant_id: str,
        req: TenantWebhookConfig,
        user: dict = Depends(require_tenant_member_dep()),
    ) -> dict:
        if user.get("role") not in ("admin", "sovereign"):
            raise HTTPException(status_code=403, detail="tenant admin role required")
        if not req.webhook_url.startswith(("http://", "https://")):
            raise HTTPException(status_code=422, detail="webhook URL must be http(s)://")
        set_doc = {"pec_webhook_url": req.webhook_url}
        if req.webhook_secret is not None:
            set_doc["pec_webhook_secret"] = req.webhook_secret
        await db.tenants.update_one({"tenant_id": tenant_id}, {"$set": set_doc})
        return {
            "ok": True,
            "tenant_id": tenant_id,
            "webhook_url": req.webhook_url,
            "secret_configured": bool(req.webhook_secret),
        }

    @router.get("/tenants/{tenant_id}/pec-webhook")
    async def get_pec_webhook(
        tenant_id: str,
        user: dict = Depends(require_tenant_member_dep()),
    ) -> dict:
        doc = await db.tenants.find_one(
            {"tenant_id": tenant_id},
            {"_id": 0, "pec_webhook_url": 1, "pec_webhook_secret": 1},
        )
        return {
            "tenant_id": tenant_id,
            "webhook_url": (doc or {}).get("pec_webhook_url") or "",
            "secret_configured": bool((doc or {}).get("pec_webhook_secret")),
        }

    api.include_router(router)
