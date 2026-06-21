"""
Lattice Network — /api/leads/* routes (Iter_40)
================================================

Public lead capture (POST /leads) + sovereign-only mgmt:
    POST   /api/leads
    GET    /api/leads
    GET    /api/leads/unread-count
    POST   /api/leads/{lead_id}/read
    POST   /api/leads/read-all
    PATCH  /api/leads/{lead_id}

Extracted verbatim from server.py — Iter_40.
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
from datetime import datetime, timezone
from typing import Any, Callable, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

try:
    from mailer import send_lead_notification_email
except ImportError:  # pragma: no cover
    def send_lead_notification_email(_lead: dict) -> None:
        return None

log = logging.getLogger("lattice.leads")

router = APIRouter(tags=["leads"])


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class LeadRequest(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=100)
    contact_name: str = Field(..., min_length=2, max_length=80)
    email: str = Field(..., min_length=5, max_length=120,
                       pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: Optional[str] = Field(None, max_length=40)
    employees_range: Optional[str] = None
    industry: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=2000)


class LeadResponse(BaseModel):
    ok: bool
    lead_id: str
    received_at: str


class LeadStatusUpdate(BaseModel):
    status: Literal["new", "contacted", "qualified", "converted", "lost"]
    notes: Optional[str] = None


def register(
    api: APIRouter,
    *,
    db: Any,
    require_platform_sovereign_dep: Callable,
    pqc_sign_fn: Callable,
    finalise_block_fn: Callable,
    det_hex_fn: Callable,
    pqc_algorithm: str,
) -> None:

    async def _notarize_lead_onchain(lead: dict) -> dict:
        """LeadCapture TX — SHA3-512 + ML-DSA-65 + QBFT finalisation."""
        canonical = "|".join([
            lead["lead_id"],
            lead.get("company_name") or "",
            lead.get("contact_name") or "",
            lead.get("email") or "",
            lead.get("phone") or "",
            lead.get("industry") or "",
            lead.get("employees_range") or "",
            lead.get("received_at") or "",
        ]).encode("utf-8")
        lead_hash = hashlib.sha3_512(canonical).hexdigest()
        ts = lead.get("received_at") or _utc_iso()
        meta = await db.meta.find_one_and_update(
            {"_id": "seeded"},
            {"$inc": {"block_height": 1, "tx_total": 1, "qbft_round": 1}},
            return_document=True,
        )
        new_block_index = meta["block_height"]
        tx_id = f"tx-{det_hex_fn(f'lead-{lead_hash}-{ts}', 12)}"
        extrinsics_root = det_hex_fn(f"xroot-{tx_id}", 64)
        state_root = det_hex_fn(f"sroot-{new_block_index}", 64)
        summary = f"LeadCapture · {lead.get('company_name','?')} · {lead_hash[:16].upper()}"
        tx_msg = ("|".join([tx_id, str(new_block_index), ts, "LeadCapture", summary])).encode("utf-8")
        sig_hex, signer_fp = await pqc_sign_fn("platform.leads-bot", tx_msg, role="platform")
        block_doc = await finalise_block_fn(
            index=new_block_index, timestamp=ts, tx_id=tx_id,
            kind="LeadCapture", doc_hash=lead_hash, signer="platform.leads-bot",
        )
        await db.blocks.update_one({"index": block_doc["index"]}, {"$set": {
            "state_root": state_root,
            "extrinsics_root": extrinsics_root,
            "events_count": 1,
            "weight_used": 4_000,
            "digest": f"qbft:{new_block_index}",
        }})
        await db.transactions.insert_one({
            "tx_id": tx_id,
            "block_index": new_block_index,
            "timestamp": ts,
            "kind": "LeadCapture",
            "summary": summary,
            "sender_public_key": signer_fp,
            "signature": sig_hex,
            "signed_with": pqc_algorithm,
            "doc_hash": lead_hash,
        })
        return {
            "tx_id": tx_id,
            "block_index": new_block_index,
            "doc_hash": lead_hash,
            "signed_at": ts,
            "signed_by": signer_fp,
            "signature_hex": sig_hex,
        }

    @router.post("/leads", response_model=LeadResponse)
    async def submit_lead(req: LeadRequest) -> LeadResponse:
        daily_cap = int(os.environ.get("LATTICE_LEAD_DAILY_CAP", "500"))
        today_prefix = _utc_iso()[:10]
        todays_onchain = await db.leads.count_documents({
            "received_at": {"$regex": f"^{today_prefix}"},
            "tx_id": {"$ne": None},
        })
        lead_id = f"lead-{secrets.token_hex(6)}"
        ts = _utc_iso()
        lead = {
            "lead_id": lead_id,
            "company_name": req.company_name.strip(),
            "contact_name": req.contact_name.strip(),
            "email": req.email.strip().lower(),
            "phone": (req.phone or "").strip(),
            "employees_range": req.employees_range,
            "industry": req.industry,
            "notes": (req.notes or "").strip(),
            "received_at": ts,
            "status": "new",
            "read_at": None,
        }
        if todays_onchain < daily_cap:
            try:
                receipt = await _notarize_lead_onchain(lead)
                lead["tx_id"] = receipt["tx_id"]
                lead["block_index"] = receipt["block_index"]
                lead["doc_hash"] = receipt["doc_hash"]
                lead["signature_hex"] = receipt["signature_hex"]
            except Exception as e:
                log.warning("lead on-chain notarisation failed for %s: %s", lead_id, e)
        else:
            log.warning(
                "Daily LeadCapture cap (%d) hit for %s — storing lead WITHOUT on-chain proof",
                daily_cap, today_prefix,
            )
            lead["onchain_skipped_reason"] = "daily_cap_exceeded"
        await db.leads.insert_one(lead)
        # Notifica email al sovrano (best-effort, non bloccante)
        try:
            send_lead_notification_email(lead)
        except Exception as e:  # pragma: no cover
            log.warning("lead notification email error %s: %s", lead_id, e)
        return LeadResponse(ok=True, lead_id=lead_id, received_at=ts)

    @router.get("/leads/unread-count")
    async def leads_unread_count(
        _u: dict = Depends(require_platform_sovereign_dep()),
    ) -> dict:
        n = await db.leads.count_documents({"read_at": None})
        return {"unread": n}

    @router.post("/leads/{lead_id}/read")
    async def mark_lead_read(
        lead_id: str,
        _u: dict = Depends(require_platform_sovereign_dep()),
    ) -> dict:
        result = await db.leads.update_one(
            {"lead_id": lead_id, "read_at": None},
            {"$set": {"read_at": _utc_iso()}},
        )
        return {"ok": True, "lead_id": lead_id, "newly_read": result.modified_count > 0}

    @router.post("/leads/read-all")
    async def mark_all_leads_read(
        _u: dict = Depends(require_platform_sovereign_dep()),
    ) -> dict:
        ts = _utc_iso()
        result = await db.leads.update_many(
            {"read_at": None},
            {"$set": {"read_at": ts}},
        )
        return {"ok": True, "marked": result.modified_count}

    @router.get("/leads")
    async def list_leads(
        limit: int = Query(50, ge=1, le=500),
        status: Optional[str] = None,
        _u: dict = Depends(require_platform_sovereign_dep()),
    ) -> List[dict]:
        q: dict = {}
        if status:
            q["status"] = status
        cursor = db.leads.find(q, {"_id": 0}).sort("received_at", -1).limit(limit)
        return [doc async for doc in cursor]

    @router.patch("/leads/{lead_id}")
    async def update_lead_status(
        lead_id: str,
        req: LeadStatusUpdate,
        _u: dict = Depends(require_platform_sovereign_dep()),
    ) -> dict:
        update = {"status": req.status, "updated_at": _utc_iso()}
        if req.notes is not None:
            update["follow_up_notes"] = req.notes.strip()
        result = await db.leads.update_one({"lead_id": lead_id}, {"$set": update})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="lead not found")
        return {"ok": True, "lead_id": lead_id, "status": req.status}

    api.include_router(router)
