"""
Lattice Network — /api/auth/* + /api/me (Iter_38)
==================================================

Full auth surface extracted from server.py:
    GET  /api/me                       (Iter_36)
    POST /api/auth/challenge           (Iter_38)
    POST /api/auth/verify              (Iter_38)
    POST /api/auth/logout              (Iter_38)
    POST /api/auth/revoke-all          (Iter_38)
    POST /api/auth/2fa/enroll          (Iter_38)
    POST /api/auth/2fa/verify          (Iter_38)
    POST /api/auth/2fa/disable         (Iter_38)
    GET  /api/auth/2fa/status          (Iter_38)
    GET  /api/auth/sessions            (Iter_38)
    POST /api/auth/sessions/{jti}/revoke (Iter_38)

All endpoints preserve byte-identical behaviour vs server.py — the
TDD safety net is /app/backend/tests/test_iteration_38_auth_certify.py.
"""
from __future__ import annotations

import secrets
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import pyotp
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pqcrypto.sign import ml_dsa_65 as mldsa
from pydantic import BaseModel

import auth_state

router = APIRouter(tags=["auth"])


# ---------------------------------------------------------------------------
# Pydantic models — same wire shapes as server.py (do not rename fields).
# ---------------------------------------------------------------------------


class ChallengeRequest(BaseModel):
    lns_name: str


class ChallengeResponse(BaseModel):
    challenge_id: str
    lns_name: str
    nonce_hex: str
    issued_at: str
    expires_in_seconds: int = auth_state.CHALLENGE_TTL_SECONDS


class VerifyAuthRequest(BaseModel):
    challenge_id: str
    signature_hex: str


class AuthSession(BaseModel):
    ok: bool
    token: str
    lns: str
    tenant_id: Optional[str] = None
    role: str
    expires_in_seconds: int


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# register() — wires every handler with explicit deps (no server.py import)
# ---------------------------------------------------------------------------


def register(
    api: APIRouter,
    *,
    db: Any,
    current_user_dep: Callable,
    require_platform_sovereign_dep: Callable,
    envelope_mod: Any,
    audit_mod: Any,
    role_sovereign: str,
    role_auditor: str,
    role_vendor: str,
) -> None:
    # -----------------------------------------------------------------------
    # GET /me
    # -----------------------------------------------------------------------
    @router.get("/me")
    async def whoami(user: dict = Depends(current_user_dep)) -> dict:
        """Echo the resolved role + identity. Drives RBAC chrome in the UI."""
        role = user["role"]
        permissions = {
            role_sovereign: {
                "can_register_lns": True, "can_revoke_lns": True,
                "can_send_certify": True, "can_send_pulse": True,
                "can_read_plaintext": True, "can_read_lns_directory": True,
                "can_verify_signatures": True,
            },
            "admin": {
                "can_register_lns": True, "can_revoke_lns": True,
                "can_send_certify": True, "can_send_pulse": True,
                "can_read_plaintext": True, "can_read_lns_directory": True,
                "can_verify_signatures": True,
            },
            "operator": {
                "can_register_lns": False, "can_revoke_lns": False,
                "can_send_certify": True, "can_send_pulse": True,
                "can_read_plaintext": True, "can_read_lns_directory": True,
                "can_verify_signatures": True,
            },
            role_auditor: {
                "can_register_lns": False, "can_revoke_lns": False,
                "can_send_certify": False, "can_send_pulse": False,
                "can_read_plaintext": False, "can_read_lns_directory": True,
                "can_verify_signatures": True,
            },
            role_vendor: {
                "can_register_lns": False, "can_revoke_lns": False,
                "can_send_certify": False, "can_send_pulse": False,
                "can_read_plaintext": False, "can_read_lns_directory": False,
                "can_verify_signatures": True,
            },
        }.get(role, {})
        labels = {
            role_sovereign: "Sovereign Admin",
            "admin": "Tenant Admin",
            "operator": "Operator",
            role_auditor: "Auditor (Read-only)",
            role_vendor: "Vendor (Metadata-only)",
        }
        return {
            "role": role,
            "label": labels.get(role, role.title()),
            "permissions": permissions,
            "lns": user.get("lns"),
            "tenant_id": user.get("tenant_id"),
            "via": user.get("via"),
        }

    # -----------------------------------------------------------------------
    # POST /auth/challenge
    # -----------------------------------------------------------------------
    @router.post("/auth/challenge", response_model=ChallengeResponse)
    async def auth_challenge(req: ChallengeRequest) -> ChallengeResponse:
        """Issue a one-time PQC challenge for *lns_name*."""
        name = req.lns_name.strip().lower()
        record = await db.lns.find_one({"lns_name": name, "status": "ACTIVE"})
        if not record:
            # Don't leak existence — same 404 for unknown LNS and revoked.
            raise HTTPException(status_code=404, detail="lns not active")
        challenge_id = f"chal-{secrets.token_hex(8)}"
        nonce = secrets.token_bytes(32)
        ts = _utc_iso()
        await db.auth_challenges.insert_one({
            "challenge_id": challenge_id,
            "lns_name": name,
            "nonce_hex": nonce.hex(),
            "issued_at": ts,
            "expires_at_ts": time.time() + auth_state.CHALLENGE_TTL_SECONDS,
            "consumed": False,
        })
        return ChallengeResponse(
            challenge_id=challenge_id,
            lns_name=name,
            nonce_hex=nonce.hex(),
            issued_at=ts,
        )

    # -----------------------------------------------------------------------
    # POST /auth/verify
    # -----------------------------------------------------------------------
    @router.post("/auth/verify", response_model=AuthSession)
    async def auth_verify(req: VerifyAuthRequest, request: Request) -> AuthSession:
        """Verify the client's ML-DSA-65 signature on the challenge nonce, issue a JWT."""
        chal = await db.auth_challenges.find_one({"challenge_id": req.challenge_id})
        if not chal:
            raise HTTPException(status_code=404, detail="challenge not found")
        if chal.get("consumed"):
            raise HTTPException(status_code=409, detail="challenge already consumed")
        if time.time() > chal.get("expires_at_ts", 0):
            raise HTTPException(status_code=410, detail="challenge expired")
        name = chal["lns_name"]
        nonce = bytes.fromhex(chal["nonce_hex"])
        ks = await db.keystore.find_one({"entity": name}, {"_id": 0, "pk_hex": 1})
        if not ks:
            raise HTTPException(status_code=404, detail="no public key on file")
        pk = bytes.fromhex(ks["pk_hex"])
        try:
            sig = bytes.fromhex(req.signature_hex)
        except ValueError:
            raise HTTPException(status_code=400, detail="malformed signature_hex") from None
        try:
            ok = bool(mldsa.verify(pk, nonce, sig))
        except Exception:
            ok = False
        if not ok:
            raise HTTPException(status_code=401, detail="signature verification failed")
        # Mark challenge consumed so it can't be replayed.
        await db.auth_challenges.update_one(
            {"challenge_id": req.challenge_id},
            {"$set": {"consumed": True, "consumed_at": _utc_iso()}},
        )
        lns_doc = await db.lns.find_one({"lns_name": name}, {"_id": 0, "role": 1, "tenant_id": 1})
        role = (lns_doc or {}).get("role") or "operator"
        tenant_id = (lns_doc or {}).get("tenant_id")
        token = auth_state.issue_jwt(name, tenant_id, role)
        payload = auth_state.decode_jwt(token) or {}
        client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if not client_ip:
            client_ip = request.client.host if request.client else "unknown"
        await db.access_log.insert_one({
            "ts": _utc_iso(),
            "event": "login_success",
            "lns": name,
            "tenant_id": tenant_id,
            "role": role,
            "jti": payload.get("jti"),
            "ip": client_ip,
            "user_agent": request.headers.get("user-agent", "")[:200],
        })
        await audit_mod.append(db, "login_success", lns=name, ip=client_ip, jti=payload.get("jti"))
        return AuthSession(
            ok=True, token=token, lns=name, tenant_id=tenant_id,
            role=role, expires_in_seconds=auth_state.JWT_TTL_SECONDS,
        )

    # -----------------------------------------------------------------------
    # POST /auth/logout
    # -----------------------------------------------------------------------
    @router.post("/auth/logout")
    async def auth_logout(user: dict = Depends(current_user_dep)) -> dict:
        """Revoke the caller's current JWT."""
        jti = user.get("jti")
        if not jti:
            return {"ok": True, "noop": True, "detail": "no jwt to revoke"}
        await db.revoked_jwts.update_one(
            {"jti": jti},
            {"$set": {
                "jti": jti,
                "lns": user.get("lns"),
                "revoked_at": _utc_iso(),
                "expires_at": _utc_iso(),
            }},
            upsert=True,
        )
        return {"ok": True, "revoked": jti}

    # -----------------------------------------------------------------------
    # POST /auth/revoke-all
    # -----------------------------------------------------------------------
    @router.post("/auth/revoke-all")
    async def auth_revoke_all(user: dict = Depends(current_user_dep)) -> dict:
        """Self-service nuclear option: revoke EVERY active JWT for this LNS."""
        lns = user.get("lns")
        if not lns:
            raise HTTPException(status_code=401, detail="login required")
        ts = _utc_iso()
        await db.revoked_jwts.update_one(
            {"_id": f"nuke:{lns}"},
            {"$set": {"lns": lns, "nuked_at": ts, "nuked_iat": int(time.time())}},
            upsert=True,
        )
        return {"ok": True, "lns": lns, "nuked_at": ts}

    # -----------------------------------------------------------------------
    # 2FA TOTP (RFC 6238)
    # -----------------------------------------------------------------------
    @router.post("/auth/2fa/enroll")
    async def auth_2fa_enroll(user: dict = Depends(current_user_dep)) -> dict:
        lns = user.get("lns")
        if not lns:
            raise HTTPException(status_code=401, detail="login required")
        secret = pyotp.random_base32()
        sealed = envelope_mod.seal_text(secret, aad=f"totp:{lns}".encode())
        await db.totp_secrets.update_one(
            {"lns": lns},
            {"$set": {"lns": lns, "secret_sealed": sealed,
                      "enrolled_at": _utc_iso(), "verified": False}},
            upsert=True,
        )
        uri = pyotp.TOTP(secret).provisioning_uri(name=lns, issuer_name="Lattice Network")
        await audit_mod.append(db, "totp_enroll", lns=lns, by=lns)
        return {"ok": True, "secret_base32": secret, "otpauth_uri": uri}

    @router.post("/auth/2fa/verify")
    async def auth_2fa_verify(
        code: str = Query(..., min_length=6, max_length=6),
        user: dict = Depends(current_user_dep),
    ) -> dict:
        lns = user.get("lns")
        doc = await db.totp_secrets.find_one({"lns": lns})
        if not doc:
            raise HTTPException(
                status_code=404,
                detail="no TOTP secret enrolled — call /auth/2fa/enroll first",
            )
        secret = envelope_mod.open_text(doc["secret_sealed"], aad=f"totp:{lns}".encode())
        if not pyotp.TOTP(secret).verify(code, valid_window=1):
            raise HTTPException(status_code=401, detail="invalid TOTP code")
        await db.totp_secrets.update_one({"lns": lns}, {"$set": {"verified": True}})
        await audit_mod.append(db, "totp_verify_ok", lns=lns)
        return {"ok": True, "verified": True}

    @router.post("/auth/2fa/disable")
    async def auth_2fa_disable(
        code: str = Query(..., min_length=6, max_length=6),
        user: dict = Depends(current_user_dep),
    ) -> dict:
        lns = user.get("lns")
        doc = await db.totp_secrets.find_one({"lns": lns})
        if not doc:
            return {"ok": True, "noop": True}
        secret = envelope_mod.open_text(doc["secret_sealed"], aad=f"totp:{lns}".encode())
        if not pyotp.TOTP(secret).verify(code, valid_window=1):
            raise HTTPException(status_code=401, detail="invalid TOTP code")
        await db.totp_secrets.delete_one({"lns": lns})
        await audit_mod.append(db, "totp_disable", lns=lns)
        return {"ok": True, "disabled": True}

    @router.get("/auth/2fa/status")
    async def auth_2fa_status(user: dict = Depends(current_user_dep)) -> dict:
        lns = user.get("lns")
        doc = await db.totp_secrets.find_one(
            {"lns": lns}, {"_id": 0, "verified": 1, "enrolled_at": 1}
        )
        if not doc:
            return {"enabled": False}
        return {"enabled": bool(doc.get("verified")), "enrolled_at": doc.get("enrolled_at")}

    # -----------------------------------------------------------------------
    # Active sessions / access log (sovereign-only)
    # -----------------------------------------------------------------------
    @router.get("/auth/sessions")
    async def list_active_sessions(
        _u: dict = Depends(require_platform_sovereign_dep()),
    ) -> list:
        cursor = db.access_log.find({"event": "login_success"}, {"_id": 0}) \
            .sort("ts", -1).limit(200)
        return [doc async for doc in cursor]

    @router.post("/auth/sessions/{jti}/revoke")
    async def revoke_session(
        jti: str,
        _u: dict = Depends(require_platform_sovereign_dep()),
    ) -> dict:
        await db.revoked_jwts.update_one(
            {"jti": jti},
            {"$set": {"jti": jti, "revoked_at": _utc_iso(), "revoked_by": _u.get("lns")}},
            upsert=True,
        )
        await audit_mod.append(db, "session_revoke_by_admin", jti=jti, by=_u.get("lns"))
        return {"ok": True, "revoked_jti": jti}

    api.include_router(router)
