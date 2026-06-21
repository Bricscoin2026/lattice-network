"""
Lattice Network — /api/admin/license/* routes (Iter_30)
========================================================

ML-DSA-65 signed license control plane. Extracted from server.py
following the OTS pattern.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import license as licmod

_log = logging.getLogger("lattice.license.routes")
router = APIRouter(prefix="/admin/license", tags=["admin-license"])


class LicenseInstallRequest(BaseModel):
    """Wraps the license document so the vendor can ship it as plain JSON."""
    license: Dict[str, Any] = Field(..., description="signed license dict (with signature_hex)")


def register(api: APIRouter, *, require_sovereign: Callable) -> None:
    @router.get("/status")
    async def license_status() -> dict:
        """Read-only license info — public so the UI can show edition badge."""
        return licmod.status()

    @router.post("/install")
    async def license_install(
        body: LicenseInstallRequest,
        _sov: dict = Depends(require_sovereign()),
    ) -> dict:
        """Install a vendor-signed license. Verifies ML-DSA-65 signature first."""
        try:
            active = licmod.install(body.license)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=f"license rejected: {e}")
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))
        _log.info("license installed · edition=%s", active.get("edition"))
        return {"ok": True, "status": licmod.status()}

    @router.post("/reload")
    async def license_reload(_sov: dict = Depends(require_sovereign())) -> dict:
        """Re-read the license file from disk (after manual replacement)."""
        licmod.load_from_disk()
        return {"ok": True, "status": licmod.status()}

    api.include_router(router)
