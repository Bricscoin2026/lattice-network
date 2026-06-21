"""
Lattice Network — /api/lns/* routes (Iter_32 + 35)
====================================================

Both read-only and mutating endpoints. The mutating side was extracted
in Iter_35 with `chain.finalise_block_for_tx` as the only ledger
helper — every other dependency (_pqc_sign, _KEY_CACHE, audit.append,
license quota, role redaction) is injected via the `register(deps)`
factory so this module stays free of any circular import on server.py.
"""
from __future__ import annotations

from typing import Any, Callable, List

from fastapi import APIRouter, Depends, HTTPException

from pydantic import BaseModel

import audit
import chain
import core
import license as licmod
from models import (
    LnsRecord, LnsCheckResponse,
    RegisterRequest, RegisterResponse,
    RevokeRequest, RevokeResponse,
)

router = APIRouter(prefix="/lns", tags=["lns"])


class RotateEncPkRequest(BaseModel):
    lns_name: str
    new_enc_public_key_hex: str
    nonce: str
    signature_hex: str
    reason: str = "post_recovery"


def register(
    api: APIRouter,
    *,
    db: Any,
    current_user_dep: Callable,
    require_sovereign_roles_dep: Callable,
    key_cache: dict,
) -> None:
    """Attach the LNS routes to the umbrella api router."""

    # ------------------------------------------------------------------
    # Read-only (already moved in Iter_32)
    # ------------------------------------------------------------------

    @router.get("/active", response_model=List[LnsRecord])
    async def lns_active(user: dict = Depends(current_user_dep)) -> List[LnsRecord]:
        """Active LNS directory — tenant-scoped for tenant users."""
        q: dict = {"status": "ACTIVE"}
        if user.get("tenant_id"):
            q["tenant_id"] = user["tenant_id"]
        cursor = db.lns.find(q, {"_id": 0}).sort("lns_name", 1).limit(500)
        return [LnsRecord(**r) async for r in cursor]

    @router.get("/check", response_model=LnsCheckResponse)
    async def lns_check(lns_name: str) -> LnsCheckResponse:
        """Live uniqueness check for the registration dialog."""
        raw = lns_name
        name = (lns_name or "").strip().lower()
        if not name or len(name) <= 3:
            return LnsCheckResponse(lns_name=raw, normalized=name, available=False, reason="too_short")
        if not all(c.isalnum() or c in ".-_" for c in name):
            return LnsCheckResponse(lns_name=raw, normalized=name, available=False, reason="forbidden_chars")
        suffix_ok = False
        cursor = db.tenants.find({}, {"_id": 0, "domain": 1})
        async for t in cursor:
            if name.endswith("." + t["domain"]):
                suffix_ok = True
                break
        if not suffix_ok:
            return LnsCheckResponse(lns_name=raw, normalized=name, available=False, reason="bad_suffix")
        existing = await db.lns.find_one({"lns_name": name})
        if existing:
            return LnsCheckResponse(lns_name=raw, normalized=name, available=False, reason="already_taken")
        return LnsCheckResponse(lns_name=raw, normalized=name, available=True)

    # ------------------------------------------------------------------
    # Mutating (extracted in Iter_35)
    # ------------------------------------------------------------------

    @router.post("/register", response_model=RegisterResponse)
    async def register_lns_endpoint(
        req: RegisterRequest,
        _role: str = Depends(require_sovereign_roles_dep()),
    ) -> RegisterResponse:
        """Mint a fresh sovereign LNS identity (PQC-signed IdentityRegister TX)."""
        name = req.lns_name.strip().lower()
        if not name or len(name) < 3:
            raise HTTPException(status_code=422, detail="lns_name too short")
        if not all(c.isalnum() or c in ".-_" for c in name):
            raise HTTPException(status_code=422, detail="lns_name contains forbidden characters")

        # Tenant resolution
        tenant_id = req.tenant_id
        tenant_doc = None
        if tenant_id:
            tenant_doc = await db.tenants.find_one({"tenant_id": tenant_id})
            if not tenant_doc:
                raise HTTPException(status_code=404, detail=f"tenant not found: {tenant_id}")
            if not name.endswith("." + tenant_doc["domain"]):
                raise HTTPException(
                    status_code=422,
                    detail=f"lns_name must end with .{tenant_doc['domain']} for tenant {tenant_id}",
                )
        else:
            cursor = db.tenants.find({}, {"_id": 0, "tenant_id": 1, "domain": 1})
            async for t in cursor:
                if name.endswith("." + t["domain"]):
                    tenant_id = t["tenant_id"]
                    tenant_doc = t
                    break
            if not tenant_doc:
                raise HTTPException(
                    status_code=422,
                    detail="lns_name must end with .<azienda> where <azienda> is a registered tenant domain",
                )

        existing = await db.lns.find_one({"lns_name": name})
        if existing:
            raise HTTPException(status_code=409, detail=f"Identity already registered: {name}")

        # License quota enforcement
        current_users = await db.lns.count_documents({"status": {"$ne": "REVOKED"}})
        if not licmod.check_user_quota(current_users):
            edition = (licmod.STATE.active or {}).get("edition", "community")
            max_u = licmod.STATE.active.get("max_users")
            raise HTTPException(
                status_code=402,
                detail=(
                    f"License quota exceeded: edition='{edition}' allows max_users={max_u}, "
                    f"already {current_users} active. Upgrade the license to add more seats."
                ),
            )

        ts = core.utc_iso()

        # Key generation: server-side vs client-side
        if req.public_key_hex:
            try:
                pk = bytes.fromhex(req.public_key_hex)
            except ValueError:
                raise HTTPException(status_code=422, detail="public_key_hex is not valid hex")
            if len(pk) != 1952:
                raise HTTPException(status_code=422,
                                    detail=f"public_key_hex wrong length: {len(pk)} (expected 1952)")
            await db.keystore.update_one(
                {"entity": name},
                {"$set": {
                    "entity": name,
                    "role": req.role,
                    "pk_hex": pk.hex(),
                    "fingerprint": core.pk_fingerprint(pk),
                    "client_managed": True,
                    "created_at": ts,
                    "algorithm": core.PQC_ALGORITHM,
                    **({"enc_pk_hex": req.enc_public_key_hex} if req.enc_public_key_hex else {}),
                }, "$unset": {"sk_hex": "", "sk": ""}},
                upsert=True,
            )
            key_cache.pop(name, None)
        else:
            pk, _sk = await core.get_or_create_keypair(name, role="lns")
            if req.enc_public_key_hex:
                await db.keystore.update_one(
                    {"entity": name},
                    {"$set": {"enc_pk_hex": req.enc_public_key_hex}},
                    upsert=True,
                )

        fp = core.pk_fingerprint(pk)
        did = f"did:lattice:{fp.lower()}"
        meta = await db.meta.find_one_and_update(
            {"_id": "seeded"},
            {"$inc": {"block_height": 1, "tx_total": 1, "qbft_round": 1}},
            return_document=True,
        )
        new_block_index = meta["block_height"]
        tx_id = f"tx-{core.det_hex(f'register-{name}-{ts}', 12)}"

        await db.lns.insert_one({
            "lns_name": name,
            "did": did,
            "public_key_fingerprint": fp,
            "registered_at": ts,
            "status": "ACTIVE",
            "department": req.department,
            "display_name": (req.display_name or "").strip() or None,
            "revoked_at": None,
            "tenant_id": tenant_id,
            "role": req.role,
        })
        if tenant_id:
            await db.tenants.update_one(
                {"tenant_id": tenant_id},
                {"$inc": {"employees_count": 1}},
            )

        summary = f"IdentityRegister · {name} · role={req.role} · dept={req.department}"
        signer_entity = "platform.notary" if req.public_key_hex else name
        tx_msg = ("|".join([tx_id, str(new_block_index), ts, "IdentityRegister", summary])).encode("utf-8")
        sig_hex, signer_fp = await core.pqc_sign(
            signer_entity, tx_msg, role="platform" if req.public_key_hex else "lns",
        )
        await chain.finalise_block_for_tx(
            index=new_block_index, timestamp=ts, tx_id=tx_id,
            kind="IdentityRegister", signer=name,
        )
        await db.transactions.insert_one({
            "tx_id": tx_id, "block_index": new_block_index, "timestamp": ts,
            "kind": "IdentityRegister", "summary": summary,
            "sender_public_key": signer_fp, "signature": sig_hex,
            "signed_with": core.PQC_ALGORITHM, "signer_entity": name,
        })
        await audit.append(
            db, "lns_register",
            node_id="admin-console", component="lattice-admin-console",
            message=f"LNS REGISTER · {name} · dept='{req.department}' · by={req.admin} · tx={tx_id}",
            lns_name=name, department=req.department, by=req.admin, tx_id=tx_id,
        )
        return RegisterResponse(
            ok=True, tx_id=tx_id, block_index=new_block_index,
            lns_name=name, did=did, public_key_fingerprint=fp, timestamp=ts,
            role=req.role, tenant_id=tenant_id,
            public_key_hex=pk.hex(),
            secret_key_hex=None if req.public_key_hex
                else (await core.get_or_create_keypair(name))[1].hex(),
            keypair_filename=f"{name}.keypair.json",
        )

    @router.post("/revoke", response_model=RevokeResponse)
    async def revoke_lns_endpoint(
        req: RevokeRequest,
        _role: str = Depends(require_sovereign_roles_dep()),
    ) -> RevokeResponse:
        record = await db.lns.find_one({"lns_name": req.lns_name}, {"_id": 0})
        if not record:
            raise HTTPException(status_code=404, detail=f"LNS identity not found: {req.lns_name}")
        if record["status"] == "REVOKED":
            raise HTTPException(status_code=409, detail=f"Identity already revoked: {req.lns_name}")

        ts = core.utc_iso()
        meta = await db.meta.find_one_and_update(
            {"_id": "seeded"},
            {"$inc": {"block_height": 1, "tx_total": 1, "qbft_round": 1}},
            return_document=True,
        )
        new_block_index = meta["block_height"]
        tx_id = f"tx-{core.det_hex(f'revoke-{req.lns_name}-{ts}', 12)}"

        summary = f"IdentityRevoke · {req.lns_name} · {req.reason}"
        await db.transactions.insert_one({
            "tx_id": tx_id, "block_index": new_block_index, "timestamp": ts,
            "kind": "IdentityRevoke", "summary": summary,
            "sender_public_key": core.det_hex(f"admin-{req.admin}", 32).upper(),
            "signature": core.det_hex(f"adminsig-{req.lns_name}-{ts}", 48).upper(),
            "signed_with": "legacy-seed",
        })
        tx_msg = ("|".join([tx_id, str(new_block_index), ts, "IdentityRevoke", summary])).encode("utf-8")
        sig_hex, signer_fp = await core.pqc_sign(f"admin.{req.admin}", tx_msg, role="admin")
        await chain.finalise_block_for_tx(
            index=new_block_index, timestamp=ts, tx_id=tx_id,
            kind="IdentityRevoke", signer=f"admin.{req.admin}",
        )
        await db.transactions.update_one(
            {"tx_id": tx_id},
            {"$set": {"signature": sig_hex, "sender_public_key": signer_fp,
                      "signed_with": core.PQC_ALGORITHM, "signer_entity": f"admin.{req.admin}"}},
        )
        await db.lns.update_one(
            {"lns_name": req.lns_name},
            {"$set": {"status": "REVOKED", "revoked_at": ts}},
        )
        await audit.append(
            db, "lns_revoke",
            node_id="admin-console", component="lattice-admin-console",
            message=f"LNS REVOKE · {req.lns_name} · by={req.admin} · reason='{req.reason}' · tx={tx_id}",
            lns_name=req.lns_name, by=req.admin, reason=req.reason, tx_id=tx_id,
        )
        return RevokeResponse(
            ok=True, tx_id=tx_id, block_index=new_block_index,
            lns_name=req.lns_name, timestamp=ts,
        )

    @router.post("/revoke-by-tenant-founder", response_model=RevokeResponse)
    async def revoke_lns_by_tenant_founder(
        req: RevokeRequest,
        user: dict = Depends(current_user_dep),
    ) -> RevokeResponse:
        """Iter_53 — Tenant founder revokes a compromised employee.

        Authorisation: requires that the caller is the **founder** of the
        same tenant as the target LNS (`tenants.admin_lns == user.lns`).
        Use case: a dipendente reports their .keypair.json has been stolen.
        The founder revokes it on-chain so the thief cannot keep using the
        SK, and the employee then registers a fresh identity (suffix _v2
        or new name) via the standard onboarding flow.
        """
        target = await db.lns.find_one({"lns_name": req.lns_name}, {"_id": 0, "tenant_id": 1, "status": 1})
        if not target:
            raise HTTPException(status_code=404, detail=f"LNS identity not found: {req.lns_name}")
        if target.get("status") == "REVOKED":
            raise HTTPException(status_code=409, detail=f"Identity already revoked: {req.lns_name}")
        tenant_id = target.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=403, detail="target LNS is not part of any tenant")
        tenant = await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0, "admin_lns": 1})
        if not tenant or tenant.get("admin_lns") != user.get("lns"):
            raise HTTPException(
                status_code=403,
                detail="Solo il fondatore del tenant può revocare un dipendente.",
            )
        if req.lns_name == tenant.get("admin_lns"):
            raise HTTPException(status_code=409, detail="non puoi revocare l'identità del fondatore")

        # Reuse the same on-chain machinery as the sovereign revoke path.
        ts = core.utc_iso()
        meta = await db.meta.find_one_and_update(
            {"_id": "seeded"},
            {"$inc": {"block_height": 1, "tx_total": 1, "qbft_round": 1}},
            return_document=True,
        )
        new_block_index = meta["block_height"]
        tx_id = f"tx-{core.det_hex(f'revoke-{req.lns_name}-{ts}', 12)}"
        summary = f"IdentityRevoke · {req.lns_name} · {req.reason} · by tenant-founder {user.get('lns')}"
        tx_msg = ("|".join([tx_id, str(new_block_index), ts, "IdentityRevoke", summary])).encode("utf-8")
        sig_hex, signer_fp = await core.pqc_sign(user.get("lns"), tx_msg, role="lns")
        await chain.finalise_block_for_tx(
            index=new_block_index, timestamp=ts, tx_id=tx_id,
            kind="IdentityRevoke", signer=user.get("lns"),
        )
        await db.transactions.insert_one({
            "tx_id": tx_id, "block_index": new_block_index, "timestamp": ts,
            "kind": "IdentityRevoke", "summary": summary,
            "sender_public_key": signer_fp, "signature": sig_hex,
            "signed_with": core.PQC_ALGORITHM, "signer_entity": user.get("lns"),
            "delegated_for": req.lns_name,
        })
        await db.lns.update_one(
            {"lns_name": req.lns_name},
            {"$set": {"status": "REVOKED", "revoked_at": ts,
                      "revoked_by": user.get("lns"), "revoke_reason": req.reason}},
        )
        # Wipe any active recovery enrollment & pending requests for the
        # compromised LNS — they should NOT survive a revoke.
        await db.recovery_enrollments.delete_one({"lns": req.lns_name})
        await db.recovery_requests.update_many(
            {"lns": req.lns_name, "status": {"$in": ["open", "ready"]}},
            {"$set": {"status": "cancelled_by_revoke", "cancelled_at": ts}},
        )
        await audit.append(
            db, "lns_revoke_by_tenant_founder",
            node_id="admin-console", component="lattice-admin-console",
            message=f"LNS REVOKE · {req.lns_name} · by={user.get('lns')} · reason='{req.reason}' · tx={tx_id}",
            lns_name=req.lns_name, by=user.get("lns"), reason=req.reason, tx_id=tx_id,
        )
        return RevokeResponse(
            ok=True, tx_id=tx_id, block_index=new_block_index,
            lns_name=req.lns_name, timestamp=ts,
        )

    @router.delete("/{lns_name}")
    async def delete_lns_endpoint(
        lns_name: str,
        _role: str = Depends(require_sovereign_roles_dep()),
    ) -> dict:
        """Permanently remove an LNS identity. Notarised as IdentityDelete."""
        name = lns_name.strip().lower()
        doc = await db.lns.find_one({"lns_name": name})
        if not doc:
            raise HTTPException(status_code=404, detail=f"lns not found: {name}")
        ts = core.utc_iso()
        archived = dict(doc)
        archived["deleted_at"] = ts
        archived.pop("_id", None)
        await db.lns_deleted.insert_one(archived)
        await db.lns.delete_one({"lns_name": name})
        if doc.get("tenant_id"):
            await db.tenants.update_one(
                {"tenant_id": doc["tenant_id"]},
                {"$inc": {"employees_count": -1}},
            )
        meta = await db.meta.find_one_and_update(
            {"_id": "seeded"},
            {"$inc": {"block_height": 1, "tx_total": 1, "qbft_round": 1}},
            return_document=True,
        )
        new_block_index = meta["block_height"]
        tx_id = f"tx-{core.det_hex(f'delete-{name}-{ts}', 12)}"
        summary = f"IdentityDelete · {name}"
        tx_msg = ("|".join([tx_id, str(new_block_index), ts, "IdentityDelete", summary])).encode("utf-8")
        sig_hex, signer_fp = await core.pqc_sign("admin.console.admin", tx_msg, role="admin")
        await chain.finalise_block_for_tx(
            index=new_block_index, timestamp=ts, tx_id=tx_id,
            kind="IdentityDelete", signer="admin.console.admin",
        )
        await db.transactions.insert_one({
            "tx_id": tx_id, "block_index": new_block_index, "timestamp": ts,
            "kind": "IdentityDelete", "summary": summary,
            "sender_public_key": signer_fp, "signature": sig_hex,
            "signed_with": core.PQC_ALGORITHM, "signer_entity": "admin.console.admin",
        })
        return {"ok": True, "lns_name": name, "tx_id": tx_id,
                "block_index": new_block_index, "deleted_at": ts}

    # ------------------------------------------------------------------
    # Rotate X25519 enc_pk (Iter_49) — used after a successful 2-of-3 key
    # recovery. The user proves ownership by signing
    #   b"rotate-enc-pk|<lns>|<new_enc_pk_hex>|<nonce>"
    # with the ML-DSA SK they just reconstructed. Backend verifies against
    # the existing keystore.pk_hex (which is unchanged by recovery) and
    # updates only the X25519 field. No identity rotation, no PQC key
    # rotation. Pure recovery hygiene.
    # ------------------------------------------------------------------
    @router.post("/rotate-enc-pk")
    async def rotate_enc_pk(req: RotateEncPkRequest) -> dict:
        name = req.lns_name.strip().lower()
        new_pk = (req.new_enc_public_key_hex or "").strip().lower()
        if not name or not new_pk or not req.signature_hex or not req.nonce:
            raise HTTPException(status_code=422, detail="missing required fields")
        # X25519 pubkey must be 32 bytes → 64 hex chars
        try:
            new_pk_bytes = bytes.fromhex(new_pk)
        except ValueError:
            raise HTTPException(status_code=422, detail="new_enc_public_key_hex is not valid hex")
        if len(new_pk_bytes) != 32:
            raise HTTPException(status_code=422, detail="X25519 pubkey must be exactly 32 bytes")

        lns_doc = await db.lns.find_one({"lns_name": name}, {"_id": 0, "status": 1})
        if not lns_doc:
            raise HTTPException(status_code=404, detail="lns not found")
        if lns_doc.get("status") == "REVOKED":
            raise HTTPException(status_code=403, detail="lns is revoked")
        ks = await db.keystore.find_one({"entity": name}, {"_id": 0, "enc_pk_hex": 1, "pk_hex": 1})
        if not ks or not ks.get("pk_hex"):
            raise HTTPException(status_code=404, detail="keystore not found for lns")
        if (ks.get("enc_pk_hex") or "").lower() == new_pk:
            return {"ok": True, "unchanged": True, "message": "enc_pk already equal to new value"}

        msg = f"rotate-enc-pk|{name}|{new_pk}|{req.nonce}".encode("utf-8")
        ok = await core.pqc_verify(name, msg, req.signature_hex)
        if not ok:
            raise HTTPException(
                status_code=401,
                detail="invalid ML-DSA signature on rotation message · cannot prove ownership of the LNS",
            )
        ts = core.utc_iso()
        await db.keystore.update_one(
            {"entity": name},
            {"$set": {"enc_pk_hex": new_pk, "enc_pk_rotated_at": ts, "enc_pk_rotation_reason": req.reason}},
        )
        # On-chain audit transaction
        meta = await db.meta.find_one_and_update(
            {"_id": "seeded"},
            {"$inc": {"block_height": 1, "tx_total": 1, "qbft_round": 1}},
            return_document=True,
        )
        new_block_index = meta["block_height"]
        tx_id = f"tx-{core.det_hex(f'rotate-enc-{name}-{ts}', 12)}"
        summary = f"EncPkRotate · {name} · fp={new_pk[:12]}… · reason={req.reason}"
        tx_msg = ("|".join([tx_id, str(new_block_index), ts, "EncPkRotate", summary])).encode("utf-8")
        sig_hex, signer_fp = await core.pqc_sign(name, tx_msg, role="lns")
        await chain.finalise_block_for_tx(
            index=new_block_index, timestamp=ts, tx_id=tx_id,
            kind="EncPkRotate", signer=name,
        )
        await db.transactions.insert_one({
            "tx_id": tx_id, "block_index": new_block_index, "timestamp": ts,
            "kind": "EncPkRotate", "summary": summary,
            "sender_public_key": signer_fp, "signature": sig_hex,
            "signed_with": core.PQC_ALGORITHM, "signer_entity": name,
        })
        await audit.append(
            db, "lns_rotate_enc_pk",
            node_id="admin-console", component="lattice-admin-console",
            message=f"LNS ROTATE_ENC_PK · {name} · reason={req.reason} · tx={tx_id}",
            lns_name=name, reason=req.reason, tx_id=tx_id,
        )
        return {"ok": True, "lns_name": name, "tx_id": tx_id,
                "block_index": new_block_index, "rotated_at": ts}

    api.include_router(router)
