"""
Lattice Network — JWT session helpers (Iter_37)
=================================================

Extracted from server.py. Holds the small bag of stateless JWT
encode/decode helpers + the asynchronous revocation check that hits
`db.revoked_jwts`.

Mutable challenge / failed-login state was already in MongoDB so there's
nothing process-local to move here.

Configuration via env:
    LATTICE_JWT_SECRET     (default: dev-only — rotate in prod)
    LATTICE_JWT_TTL_HOURS  (default: 8)
"""
from __future__ import annotations

import os
import secrets
import time
from typing import Any, Optional

import jwt as _pyjwt

JWT_SECRET = os.environ.get("LATTICE_JWT_SECRET", "dev-only-please-rotate")
JWT_ALG = "HS256"
JWT_TTL_SECONDS = int(os.environ.get("LATTICE_JWT_TTL_HOURS", "8")) * 60 * 60
CHALLENGE_TTL_SECONDS = 120


def issue_jwt(lns: str, tenant_id: Optional[str], role: str) -> str:
    now = int(time.time())
    payload = {
        "sub": lns,
        "tenant_id": tenant_id,
        "role": role,
        "iat": now,
        "exp": now + JWT_TTL_SECONDS,
        "iss": "lattice-gateway",
        "jti": secrets.token_urlsafe(16),
    }
    return _pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_jwt(token: str) -> Optional[dict]:
    try:
        return _pyjwt.decode(
            token, JWT_SECRET, algorithms=[JWT_ALG],
            options={"require": ["exp", "sub"]},
        )
    except _pyjwt.PyJWTError:
        return None


async def is_jwt_revoked(db: Any, payload: dict) -> bool:
    """True if jti is explicitly revoked OR LNS was 'nuked' after iat."""
    jti = payload.get("jti") if isinstance(payload, dict) else None
    lns = payload.get("sub") if isinstance(payload, dict) else None
    iat = int(payload.get("iat", 0)) if isinstance(payload, dict) else 0
    if jti:
        doc = await db.revoked_jwts.find_one({"jti": jti}, {"_id": 0, "jti": 1})
        if doc is not None:
            return True
    if lns:
        nuke = await db.revoked_jwts.find_one({"_id": f"nuke:{lns}"}, {"_id": 0, "nuked_iat": 1})
        if nuke and int(nuke.get("nuked_iat", 0)) >= iat:
            return True
    return False
