"""
Lattice Network — /api/admin/secrets/* routes (Iter_30)
========================================================

Extracted from server.py following the OTS pattern (routes/ots.py).
Wraps secret_manager.{status,init_passphrase,unlock} into a REST API
that the System Health UI consumes.
"""
from __future__ import annotations

from typing import Any, Callable, List, Tuple

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import secret_manager

router = APIRouter(prefix="/admin/secrets", tags=["admin-secrets"])


class SecretsPassphraseRequest(BaseModel):
    passphrase: str = Field(..., min_length=12, description="≥12 chars admin passphrase")


def register(
    api: APIRouter,
    *,
    db: Any,
    require_sovereign: Callable,
    get_or_create_keypair: Callable,
    node_labels: List[Tuple[str, str]],
) -> None:
    """Attach /admin/secrets/* routes to the umbrella api router."""

    async def _materialise_keypairs() -> None:
        # Re-materialise validator + admin console keypairs after a
        # successful unlock/init so subsequent signing calls don't crash.
        for (label, _role) in node_labels:
            await get_or_create_keypair(label, role="validator")
        await get_or_create_keypair("admin.console.admin", role="admin")

    @router.get("/status")
    async def secrets_status() -> dict:
        """Public-ish (sovereign-only) status of the at-rest key manager.

        Intentionally does NOT require_unlocked() so the operator can see
        *why* the keystore is locked without first authenticating with a
        keypair (whose sk_hex needs the very same master key).
        """
        return secret_manager.status()

    @router.post("/init")
    async def secrets_init(
        body: SecretsPassphraseRequest,
        _sov: dict = Depends(require_sovereign()),
    ):
        """First-time passphrase initialisation. Fails if already configured."""
        try:
            result = await secret_manager.init_passphrase(db, body.passphrase)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=409, detail=str(e))
        await _materialise_keypairs()
        return result

    @router.post("/unlock")
    async def secrets_unlock(body: SecretsPassphraseRequest):
        """Runtime unlock — passphrase IS the credential, no role gate."""
        try:
            result = await secret_manager.unlock(db, body.passphrase)
        except PermissionError:
            raise HTTPException(status_code=401, detail="passphrase does not match")
        except RuntimeError as e:
            raise HTTPException(status_code=404, detail=str(e))
        await _materialise_keypairs()
        return result

    api.include_router(router)
