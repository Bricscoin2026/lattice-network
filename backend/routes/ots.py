"""
Lattice Network — /api/admin/ots/* routes (Iter_29)
====================================================

Reference extraction module for the modular refactor of server.py.

Pattern demonstrated here:
    1. Each functional area gets its own `routes/<area>.py` file.
    2. The file defines an `APIRouter` plus a `register(deps)` factory
       so the host (server.py) can wire in `db`, `require_*` dependency
       and any constants without creating circular imports.
    3. server.py keeps the `api` umbrella router and calls
       `ots_routes.register(api, deps={...})` at module bottom — one
       line per area.

To extract another area (e.g. `routes/secrets.py`, `routes/license.py`):
    - Copy this file, change the prefix + tags.
    - Move the handlers verbatim, parameterising the imports.
    - Remove the originals from server.py and add the register() call.
    - Run `python -m pytest backend/tests/test_iteration_23_admin.py`.
"""
from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

import ots_anchor

router = APIRouter(prefix="/admin/ots", tags=["admin-ots"])


def register(api: APIRouter, *, db: Any, require_sovereign: Callable, chain_id: str) -> None:
    """Attach the OTS routes to the given umbrella `api` router."""

    @router.get("/status")
    async def ots_status() -> dict:
        """Public read-only summary of OTS configuration + recent anchors."""
        return {
            "enabled": ots_anchor.is_enabled(),
            "calendars": ots_anchor._calendars(),  # noqa: SLF001
            "anchors": await ots_anchor.list_anchors(db, limit=20),
        }

    @router.post("/anchor")
    async def ots_create_anchor(_sov: dict = Depends(require_sovereign())) -> dict:
        """Stamp the current ledger tip into the next Bitcoin block via OTS."""
        try:
            doc = await ots_anchor.create_anchor(db, chain_id=chain_id)
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))
        return {"ok": True, "anchor": doc}

    @router.post("/upgrade/{anchor_id}")
    async def ots_upgrade(anchor_id: str, _sov: dict = Depends(require_sovereign())) -> dict:
        """Ask the calendar to upgrade the proof with the Bitcoin attestation."""
        try:
            doc = await ots_anchor.upgrade_anchor(db, anchor_id)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))
        return {"ok": True, "anchor": doc}

    @router.post("/upgrade-all")
    async def ots_upgrade_all(_sov: dict = Depends(require_sovereign())) -> dict:
        """Sweep ALL pending anchors on demand. Same logic as the
        background loop but runs immediately and returns the per-anchor
        outcome. Heavy: makes one HTTP roundtrip to the calendar per
        pending anchor.
        """
        if not ots_anchor.is_enabled():
            raise HTTPException(status_code=503, detail="OpenTimestamps anchoring is disabled")
        pending_cursor = db.ots_anchors.find(
            {"btc_attested": False}, {"_id": 0, "anchor_id": 1}
        )
        pending = [d["anchor_id"] async for d in pending_cursor]
        results = []
        promoted = 0
        for anchor_id in pending:
            try:
                refreshed = await ots_anchor.upgrade_anchor(db, anchor_id)
                if refreshed.get("btc_attested"):
                    promoted += 1
                results.append({
                    "anchor_id": anchor_id,
                    "btc_attested": refreshed.get("btc_attested"),
                    "status": refreshed.get("last_upgrade_status"),
                })
            except Exception as e:
                results.append({"anchor_id": anchor_id, "error": str(e)})
        return {"ok": True, "pending": len(pending), "promoted": promoted, "results": results}

    @router.get("/anchors/{anchor_id}/proof")
    async def ots_proof_download(anchor_id: str, _sov: dict = Depends(require_sovereign())):
        """Download the binary `.ots` proof file."""
        blob = await ots_anchor.get_proof_bytes(db, anchor_id)
        if blob is None:
            raise HTTPException(status_code=404, detail=f"anchor not found: {anchor_id}")
        headers = {
            "Content-Disposition": f'attachment; filename="{anchor_id}.ots"',
            "Content-Type": "application/octet-stream",
        }
        return Response(content=blob, headers=headers, media_type="application/octet-stream")

    api.include_router(router)
