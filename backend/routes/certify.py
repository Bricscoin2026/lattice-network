"""
Lattice Network — /api/certify/* read-only routes (Iter_33)
===========================================================

Read-only endpoints (stats, list). Mutating endpoints (send, read,
restore, delete, receipt.pdf) remain in server.py for now because they
depend on `_finalise_block_for_tx`, `_pqc_sign`, the E2E envelope
helpers, the PDF generator and the role-redaction layer — extracting
them cleanly requires first moving those helpers into `chain.py`.

See routes/README.md for the staged refactor roadmap.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, List, Literal, Optional

from fastapi import APIRouter, Depends, Query

from models import CertifyStats, CertifyMail

router = APIRouter(prefix="/certify", tags=["certify"])


def register(
    api: APIRouter,
    *,
    db: Any,
    current_user_dep: Callable,
    role_dep: Callable,
    redact_for_role: Callable,
) -> None:
    @router.get("/stats", response_model=CertifyStats)
    async def certify_stats() -> CertifyStats:
        now = datetime.now(timezone.utc)
        total = await db.certify_mails.count_documents({})
        cutoff_24 = (now - timedelta(hours=24)).isoformat()
        cutoff_7 = (now - timedelta(days=7)).isoformat()
        last_24 = await db.certify_mails.count_documents({"sealed_at": {"$gte": cutoff_24}})
        last_7 = await db.certify_mails.count_documents({"sealed_at": {"$gte": cutoff_7}})
        agg = await db.certify_mails.aggregate([
            {"$group": {"_id": None, "bytes": {"$sum": "$bytes"}}}
        ]).to_list(1)
        bytes_sealed = int(agg[0]["bytes"]) if agg else 0
        return CertifyStats(
            total_notarized=total,
            last_24h=last_24,
            last_7d=last_7,
            bytes_sealed=bytes_sealed,
            avg_seal_ms=round(random.uniform(38, 72), 1),
        )

    @router.get("/recent", response_model=List[CertifyMail])
    async def certify_recent(
        limit: int = Query(25, ge=1, le=200),
        box: Optional[Literal["inbox", "sent", "all", "trash"]] = "all",
        role: str = Depends(role_dep),
        user: dict = Depends(current_user_dep),
    ) -> List[CertifyMail]:
        """Personal mailbox (inbox/sent/all/trash)."""
        q: dict = {}
        me = user.get("lns")
        if me:
            if box == "trash":
                q = {
                    "$or": [{"sender_lns": me}, {"recipient_lns": me}],
                    "deleted_by": me,
                }
            else:
                if box == "inbox":
                    q = {"recipient_lns": me}
                elif box == "sent":
                    q = {"sender_lns": me}
                else:
                    q = {"$or": [{"sender_lns": me}, {"recipient_lns": me}]}
                q = {"$and": [q, {"deleted_by": {"$ne": me}}]}
        cursor = db.certify_mails.find(q, {"_id": 0}).sort("sealed_at", -1).limit(limit)
        raw = [m async for m in cursor]
        redacted = redact_for_role(role, "certify_mail", raw)
        return [CertifyMail(**m) for m in redacted]

    api.include_router(router)
