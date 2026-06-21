"""
Lattice Network — /api/admin/backup/* routes (Iter_30)
=======================================================

JSON snapshot + restore for the application collections. Extracted from
server.py following the OTS pattern.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse

_log = logging.getLogger("lattice.backup.routes")
router = APIRouter(prefix="/admin/backup", tags=["admin-backup"])


def register(
    api: APIRouter,
    *,
    db: Any,
    require_sovereign: Callable,
    utc_iso: Callable,
    backup_collections: List[str],
    backup_confirm_token: str,
    compliance_mode: bool,
) -> None:
    @router.get("/snapshot")
    async def backup_snapshot(_sov: dict = Depends(require_sovereign())):
        """Stream a JSON snapshot of all application collections."""
        snapshot: Dict[str, Any] = {
            "version": "1.0",
            "created_at": utc_iso(),
            "compliance_mode": compliance_mode,
            "collections": {},
        }
        for name in backup_collections:
            try:
                docs = await db[name].find({}, {"_id": 0}).to_list(length=None)
                snapshot["collections"][name] = docs
            except Exception as e:
                _log.warning("backup: %s failed (%s)", name, e)
                snapshot["collections"][name] = []
        snapshot["stats"] = {k: len(v) for k, v in snapshot["collections"].items()}
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        headers = {"Content-Disposition": f'attachment; filename="lattice-backup-{ts}.json"'}
        return JSONResponse(content=snapshot, headers=headers)

    @router.post("/restore")
    async def backup_restore(
        snapshot: Dict[str, Any],
        confirm: Optional[str] = Header(default=None, alias="X-Lattice-Backup-Confirm"),
        _sov: dict = Depends(require_sovereign()),
    ):
        """Restore an application state from a snapshot. DESTRUCTIVE."""
        if confirm != backup_confirm_token:
            raise HTTPException(
                status_code=400,
                detail=f"Missing/invalid confirmation header. Send 'X-Lattice-Backup-Confirm: {backup_confirm_token}'",
            )
        if "collections" not in snapshot:
            raise HTTPException(status_code=400, detail="Invalid snapshot format: missing 'collections' key")
        restored: Dict[str, int] = {}
        for name in backup_collections:
            docs = snapshot["collections"].get(name, [])
            try:
                await db[name].delete_many({})
                if docs:
                    await db[name].insert_many(docs)
                restored[name] = len(docs)
            except Exception as e:
                _log.error("restore: %s failed (%s)", name, e)
                restored[name] = -1
        _log.info("admin backup restore complete: %s", restored)
        return {
            "ok": True,
            "restored": restored,
            "snapshot_created_at": snapshot.get("created_at"),
            "message": f"Restore complete: {sum(v for v in restored.values() if v > 0)} documents imported.",
        }

    api.include_router(router)
