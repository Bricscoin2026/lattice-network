"""
Lattice Network — /api/keyrecovery/* read-only routes (Iter_34)
================================================================

Read-only endpoints for the Shamir 2-of-3 social recovery scheme.

The mutating endpoints (enroll, request, contribute) STAY in server.py
because they call `_finalise_block_for_tx`, `_pqc_sign`, `audit.append`
and the meta block-height counter — many of which already exist as
modules but are still wired through server.py's local helpers.

Subsequent iteration will move them once `routes/lns.py` has its
mutating endpoints (same dependency surface).
"""
from __future__ import annotations

import hashlib
from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import audit
import chain
import core

router = APIRouter(prefix="/keyrecovery", tags=["keyrecovery"])


class KeyShareEnrollRequest(BaseModel):
    lns: str
    guardian1_lns: str
    guardian2_lns: str
    guardian3_lns: str
    encrypted_share1: dict
    encrypted_share2: dict
    encrypted_share3: dict
    share1_fingerprint: str
    share2_fingerprint: str
    share3_fingerprint: str


class KeyRecoveryRequestModel(BaseModel):
    lns: str
    reason: str = "lost_keypair"
    requester_enc_pk_hex: Optional[str] = Field(default=None, min_length=64, max_length=64)


class KeyRecoveryContribute(BaseModel):
    request_id: str
    guardian_lns: str
    contributed_share: dict


def register(
    api: APIRouter,
    *,
    db: Any,
    current_user_dep: Callable,
    role_sovereign: str,
    pqc_sign_or_delegate_fn: Callable,
    finalise_block_fn: Callable,
    pqc_algorithm: str,
    secrets_token_hex: Callable | None = None,
) -> None:
    @router.get("/status/{request_id}")
    async def keyrecovery_status(
        request_id: str,
        user: dict = Depends(current_user_dep),
    ) -> dict:
        rq = await db.recovery_requests.find_one({"request_id": request_id}, {"_id": 0})
        if not rq:
            raise HTTPException(status_code=404, detail="no such request")
        return rq

    @router.get("/enrollment/{lns}")
    async def keyrecovery_enrollment(
        lns: str,
        user: dict = Depends(current_user_dep),
    ) -> dict:
        doc = await db.recovery_enrollments.find_one({"lns": lns}, {"_id": 0})
        if not doc:
            return {"enrolled": False, "lns": lns}
        return {
            "enrolled": True,
            "lns": lns,
            "guardians": doc.get("guardians", []),
            "threshold": doc.get("threshold", 2),
            "total": doc.get("total", 3),
            "enrolled_at": doc.get("enrolled_at"),
            "fingerprints": {
                "share1": doc.get("share1", {}).get("fingerprint"),
                "share2": doc.get("share2", {}).get("fingerprint"),
                "share3": doc.get("share3", {}).get("fingerprint"),
            },
        }

    @router.get("/share-for-guardian/{request_id}")
    async def keyrecovery_share_for_guardian(
        request_id: str,
        guardian_lns: str | None = None,
        user: dict = Depends(current_user_dep),
    ) -> dict:
        rq = await db.recovery_requests.find_one({"request_id": request_id}, {"_id": 0})
        if not rq:
            raise HTTPException(status_code=404, detail="no such request")
        me = user.get("lns")
        target = guardian_lns or me
        if not target:
            raise HTTPException(status_code=422, detail="guardian_lns missing")
        if target not in rq.get("guardians", []):
            raise HTTPException(status_code=403, detail="not one of the nominated guardians")
        if me != target and user.get("role") != role_sovereign:
            raise HTTPException(status_code=403, detail="only the guardian can fetch their own share")
        enroll = await db.recovery_enrollments.find_one({"lns": rq["lns"]}, {"_id": 0})
        if not enroll:
            raise HTTPException(status_code=404, detail="enrollment vanished")
        for slot_name in ("share1", "share2", "share3"):
            slot = enroll.get(slot_name) or {}
            if slot.get("guardian") == target:
                return {
                    "request_id": request_id,
                    "lns": rq["lns"],
                    "guardian_lns": target,
                    "sealed_envelope": slot.get("ciphertext"),
                    "fingerprint": slot.get("fingerprint"),
                }
        raise HTTPException(status_code=403, detail="caller is not a guardian of this LNS")

    @router.get("/requests/pending-as-guardian")
    async def keyrecovery_pending_as_guardian(
        user: dict = Depends(current_user_dep),
    ) -> dict:
        me = user.get("lns")
        if not me:
            raise HTTPException(status_code=401, detail="auth required")
        cursor = db.recovery_requests.find(
            {"status": "open", "guardians": me}, {"_id": 0},
        ).sort("opened_at", -1).limit(50)
        rows = []
        async for rq in cursor:
            contributed = any(c.get("guardian_lns") == me for c in rq.get("contributions", []))
            rows.append({
                "request_id": rq["request_id"],
                "lns": rq["lns"],
                "opened_at": rq.get("opened_at"),
                "opened_by": rq.get("opened_by"),
                "reason": rq.get("reason"),
                "contributions_count": len(rq.get("contributions", [])),
                "already_contributed": contributed,
            })
        return {"items": rows, "total": len(rows)}

    # ------------------------------------------------------------------
    # Mutating endpoints (Iter_36)
    # ------------------------------------------------------------------

    @router.get("/policy/{tenant_id}")
    async def keyrecovery_tenant_policy(
        tenant_id: str,
        user: dict = Depends(current_user_dep),
    ) -> dict:
        """Restituisce la policy di Key Recovery del tenant: i 3 LNS dei
        guardiani aziendali scelti dal fondatore + le rispettive chiavi
        pubbliche X25519 necessarie a ciascun dipendente per cifrare i 3
        share Shamir della propria SK durante l'auto-enroll."""
        if user.get("tenant_id") != tenant_id and user.get("role") != role_sovereign:
            raise HTTPException(status_code=403, detail="cross-tenant policy lookup forbidden")
        tenant = await db.tenants.find_one(
            {"tenant_id": tenant_id},
            {"_id": 0, "admin_lns": 1, "recovery_policy": 1, "name": 1},
        )
        if not tenant:
            raise HTTPException(status_code=404, detail="tenant not found")
        policy = tenant.get("recovery_policy") or {}
        guardians = policy.get("guardians") or []
        if not guardians:
            return {
                "tenant_id": tenant_id, "tenant_name": tenant.get("name"),
                "founder": tenant.get("admin_lns"),
                "policy_set": False,
                "guardians": [],
            }
        enriched = []
        for g in guardians:
            ks = await db.keystore.find_one({"entity": g}, {"_id": 0, "enc_pk_hex": 1, "pk_hex": 1})
            lns_doc = await db.lns.find_one({"lns_name": g}, {"_id": 0, "display_name": 1})
            enriched.append({
                "lns": g,
                "display_name": (lns_doc or {}).get("display_name"),
                "enc_public_key_hex": (ks or {}).get("enc_pk_hex"),
            })
        return {
            "tenant_id": tenant_id, "tenant_name": tenant.get("name"),
            "founder": tenant.get("admin_lns"),
            "policy_set": True,
            "guardians": enriched,
            "updated_at": policy.get("updated_at"),
            "updated_by": policy.get("updated_by"),
        }

    @router.post("/enroll")
    async def keyrecovery_enroll(
        req: KeyShareEnrollRequest,
        user: dict = Depends(current_user_dep),
    ) -> dict:
        """Register a 2-of-3 backup: 3 encrypted shares destined to 3 guardians.

        Authorisation rules (Iter_43+46):
        - Il **fondatore** del tenant può configurare un nuovo enroll con
          QUALSIASI scelta di 3 guardiani. La sua scelta viene SALVATA come
          policy di tenant (`tenants.recovery_policy.guardians`) e diventa
          obbligatoria per tutti gli enroll successivi dei dipendenti.
        - Gli altri membri del tenant possono fare l'enroll della PROPRIA LNS
          ma DEVONO usare ESATTAMENTE i 3 guardiani della policy aziendale.
          Questo permette a tutti i dipendenti di avere recovery, garantendo
          al tempo stesso il controllo centralizzato sui nominati.
        - Sovereign di piattaforma → sempre permesso, qualsiasi scelta.
        - Account non-tenant → comportamento legacy (owner-only).
        """
        if user.get("lns") != req.lns and user.get("role") != role_sovereign:
            raise HTTPException(status_code=403, detail="only the LNS owner (or sovereign) can enroll")
        owner_lns_doc = await db.lns.find_one({"lns_name": req.lns}, {"_id": 0, "tenant_id": 1})
        owner_tenant_id = (owner_lns_doc or {}).get("tenant_id")
        is_founder = False
        if owner_tenant_id and user.get("role") != role_sovereign:
            tenant = await db.tenants.find_one(
                {"tenant_id": owner_tenant_id},
                {"_id": 0, "admin_lns": 1, "recovery_policy": 1},
            )
            founder = (tenant or {}).get("admin_lns")
            is_founder = bool(founder and req.lns == founder)
            policy = (tenant or {}).get("recovery_policy") or {}
            policy_guardians = policy.get("guardians") or []
            requested = [req.guardian1_lns, req.guardian2_lns, req.guardian3_lns]
            if not is_founder:
                if not policy_guardians:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Il fondatore ({founder}) non ha ancora configurato i 3 "
                            "nominati aziendali. Chiedi al fondatore di completare il "
                            "setup del Key Recovery prima di iscriverti."
                        ),
                    )
                if sorted(requested) != sorted(policy_guardians):
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            "I 3 nominati devono coincidere con la policy aziendale: "
                            f"{', '.join(policy_guardians)}."
                        ),
                    )
        for g in {req.guardian1_lns, req.guardian2_lns, req.guardian3_lns}:
            ks = await db.keystore.find_one({"entity": g}, {"_id": 0, "enc_pk_hex": 1})
            if not ks or not ks.get("enc_pk_hex"):
                raise HTTPException(status_code=422, detail=f"guardian {g} has no enc_public_key_hex on file")
        ts = core.utc_iso()
        # If the founder is (re)enrolling, persist the chosen guardians as
        # the tenant-wide recovery policy. Subsequent employee enrolls must
        # match this list.
        if is_founder and owner_tenant_id:
            await db.tenants.update_one(
                {"tenant_id": owner_tenant_id},
                {"$set": {"recovery_policy": {
                    "guardians": [req.guardian1_lns, req.guardian2_lns, req.guardian3_lns],
                    "updated_at": ts, "updated_by": req.lns,
                }}},
            )
        doc = {
            "lns": req.lns,
            "guardians": [req.guardian1_lns, req.guardian2_lns, req.guardian3_lns],
            "share1": {"ciphertext": req.encrypted_share1, "fingerprint": req.share1_fingerprint, "guardian": req.guardian1_lns},
            "share2": {"ciphertext": req.encrypted_share2, "fingerprint": req.share2_fingerprint, "guardian": req.guardian2_lns},
            "share3": {"ciphertext": req.encrypted_share3, "fingerprint": req.share3_fingerprint, "guardian": req.guardian3_lns},
            "enrolled_at": ts, "threshold": 2, "total": 3,
        }
        # If a previous enrollment exists, any in-flight recovery requests for
        # this LNS still carry contributions built from the OLD shares. Mixing
        # those with the NEW shares would corrupt Shamir reconstruction and
        # produce an invalid ML-DSA SK ("malformed key s1/s3 outside ETA range").
        # Invalidate them defensively.
        prev = await db.recovery_enrollments.find_one({"lns": req.lns}, {"_id": 0, "enrolled_at": 1})
        if prev:
            stale = await db.recovery_requests.update_many(
                {"lns": req.lns, "status": {"$in": ["open", "ready"]}},
                {"$set": {"status": "cancelled_by_reenroll",
                          "cancelled_at": ts,
                          "cancel_reason": "owner re-enrolled with new Shamir shares"}},
            )
            if stale.modified_count:
                await audit.append(
                    db, "keyrecovery_reenroll_invalidated_requests",
                    lns=req.lns, invalidated=stale.modified_count,
                )
        await db.recovery_enrollments.replace_one({"lns": req.lns}, doc, upsert=True)

        meta = await db.meta.find_one_and_update(
            {"_id": "seeded"}, {"$inc": {"block_height": 1, "tx_total": 1}}, return_document=True,
        )
        new_idx = meta["block_height"]
        tx_id = f"tx-{core.det_hex(f'kse-{req.lns}-{ts}', 12)}"
        summary = f"KeyShareEnroll · {req.lns} · 2-of-3 guardians"
        recovery_canonical = "|".join([
            req.lns, req.guardian1_lns, req.guardian2_lns, req.guardian3_lns,
            req.share1_fingerprint, req.share2_fingerprint, req.share3_fingerprint,
        ]).encode()
        tx_msg = ("|".join([tx_id, str(new_idx), ts, "KeyShareEnroll", summary])).encode("utf-8")
        sig_hex, signer_fp = await core.pqc_sign("platform.notary", tx_msg, role="platform")
        on_chain_hash = hashlib.sha3_512(recovery_canonical).hexdigest()
        await chain.finalise_block_for_tx(
            index=new_idx, timestamp=ts, tx_id=tx_id,
            kind="KeyShareEnroll", doc_hash=on_chain_hash, signer="platform.notary",
        )
        await db.transactions.insert_one({
            "tx_id": tx_id, "block_index": new_idx, "timestamp": ts,
            "kind": "KeyShareEnroll", "summary": summary,
            "sender_public_key": signer_fp, "signature": sig_hex,
            "signed_with": core.PQC_ALGORITHM,
            "signer_entity": "platform.notary", "doc_hash": on_chain_hash,
        })
        await audit.append(db, "keyrecovery_enroll", lns=req.lns, guardians=doc["guardians"], tx_id=tx_id)
        return {"ok": True, "tx_id": tx_id, "block_index": new_idx, "threshold": 2, "total": 3}

    @router.post("/request")
    async def keyrecovery_open_request(
        req: KeyRecoveryRequestModel,
        user: dict = Depends(current_user_dep),
    ) -> dict:
        enroll = await db.recovery_enrollments.find_one({"lns": req.lns})
        if not enroll:
            raise HTTPException(status_code=404, detail=f"no recovery enrollment for {req.lns}")
        request_id = f"krq-{secrets_token_hex(8)}"
        ts = core.utc_iso()
        # ---- on-chain notarisation (Iter_55) ----
        # Notarize every recovery request so it is publicly verifiable in the
        # Block Explorer. The transaction is signed via the gateway delegation
        # mechanism (the requester may not even have a session yet — they lost
        # their key). The signer_entity is the gateway, `delegated_for` carries
        # the LNS of the requester. Hash of (request_id + lns + requester_enc_pk
        # + reason) goes on-chain so anyone can match the Explorer entry with a
        # locally-bookmarked recovery ticket.
        meta = await db.meta.find_one_and_update(
            {"_id": "seeded"},
            {"$inc": {"block_height": 1, "tx_total": 1, "qbft_round": 1}},
            return_document=True,
        )
        new_block_index = meta["block_height"]
        tx_id = f"tx-{core.det_hex(f'krqopen-{request_id}-{ts}', 12)}"
        doc_hash = core.det_hex(
            f"{request_id}|{req.lns}|{req.requester_enc_pk_hex}|{req.reason}", 32,
        )
        summary = (f"KeyShareRecover · request_open · {request_id} · for={req.lns} · "
                   f"reason={req.reason} · hash={doc_hash[:16]}")
        tx_msg = ("|".join([tx_id, str(new_block_index), ts,
                            "KeyShareRecover", summary])).encode("utf-8")
        # Gateway delegation: lost-key requesters often have no SK at hand.
        lns_doc = await db.lns.find_one({"lns_name": req.lns}, {"_id": 0, "tenant_id": 1})
        tenant_id = (lns_doc or {}).get("tenant_id")
        sig_hex, signer_fp, actual_signer = await pqc_sign_or_delegate_fn(
            req.lns, tx_msg, tenant_id=tenant_id, gateway_prefix="RECOVERY-GATEWAY",
        )
        block_doc = await finalise_block_fn(
            index=new_block_index, timestamp=ts, tx_id=tx_id,
            kind="KeyShareRecover", doc_hash=doc_hash, signer=actual_signer,
        )
        await db.transactions.insert_one({
            "tx_id": tx_id, "block_index": new_block_index, "timestamp": ts,
            "kind": "KeyShareRecover", "summary": summary,
            "doc_hash": doc_hash,
            "sender_public_key": signer_fp, "signature": sig_hex,
            "signed_with": pqc_algorithm, "signer_entity": actual_signer,
            "delegated_for": req.lns if actual_signer != req.lns else None,
            "event": "request_open", "request_id": request_id,
        })
        await db.recovery_requests.insert_one({
            "request_id": request_id, "lns": req.lns,
            "guardians": enroll["guardians"], "reason": req.reason,
            "status": "open", "contributions": [],
            "opened_at": ts, "opened_by": user.get("lns", "anonymous"),
            "requester_enc_pk_hex": req.requester_enc_pk_hex,
            "open_tx_id": tx_id, "open_block_index": new_block_index,
            "open_doc_hash": doc_hash,
        })
        await audit.append(db, "keyrecovery_request_open",
                           request_id=request_id, lns=req.lns,
                           by=user.get("lns"), tx_id=tx_id)
        return {"ok": True, "request_id": request_id,
                "guardians": enroll["guardians"], "threshold": 2,
                "tx_id": tx_id, "block_index": new_block_index,
                "doc_hash": doc_hash, "lns": req.lns}

    @router.post("/contribute")
    async def keyrecovery_contribute(
        req: KeyRecoveryContribute,
        user: dict = Depends(current_user_dep),
    ) -> dict:
        rq = await db.recovery_requests.find_one({"request_id": req.request_id})
        if not rq:
            raise HTTPException(status_code=404, detail="no such request")
        if rq.get("status") != "open":
            raise HTTPException(status_code=409, detail=f"request already {rq.get('status')}")
        if req.guardian_lns not in rq.get("guardians", []):
            raise HTTPException(status_code=403, detail="not one of the nominated guardians")
        if user.get("lns") != req.guardian_lns and user.get("role") != role_sovereign:
            raise HTTPException(status_code=403, detail="only the guardian can contribute their own share")
        contribs = list(rq.get("contributions", []))
        if any(c["guardian_lns"] == req.guardian_lns for c in contribs):
            raise HTTPException(status_code=409, detail="guardian already contributed")
        contribs.append({
            "guardian_lns": req.guardian_lns,
            "share": req.contributed_share,
            "contributed_at": core.utc_iso(),
        })
        new_status = "ready" if len(contribs) >= 2 else "open"
        await db.recovery_requests.update_one(
            {"request_id": req.request_id},
            {"$set": {"contributions": contribs, "status": new_status}},
        )
        await audit.append(db, "keyrecovery_contribute",
                           request_id=req.request_id, guardian=req.guardian_lns,
                           contributions_count=len(contribs), now_status=new_status)
        # ---- Per-contribution on-chain notarisation (Iter_55) ----
        # Every guardian contribution becomes its own KeyShareContribute tx,
        # firmata con la SK ML-DSA del guardiano (o gateway delegation). Così
        # nell'Explorer si vede l'intera catena: request_open → contribute_1
        # → contribute_2 → ready (con il finale già esistente sotto).
        contrib_ts = core.utc_iso()
        c_meta = await db.meta.find_one_and_update(
            {"_id": "seeded"},
            {"$inc": {"block_height": 1, "tx_total": 1, "qbft_round": 1}},
            return_document=True,
        )
        c_idx = c_meta["block_height"]
        c_tx_id = f"tx-{core.det_hex(f'kshare-{req.request_id}-{req.guardian_lns}-{contrib_ts}', 12)}"
        c_doc_hash = core.det_hex(
            f"{req.request_id}|{req.guardian_lns}|contributed", 32,
        )
        c_summary = (f"KeyShareContribute · {req.guardian_lns} → {rq['lns']} · "
                     f"req={req.request_id} · {len(contribs)}/2")
        c_msg = ("|".join([c_tx_id, str(c_idx), contrib_ts,
                           "KeyShareContribute", c_summary])).encode("utf-8")
        guardian_doc = await db.lns.find_one({"lns_name": req.guardian_lns},
                                              {"_id": 0, "tenant_id": 1})
        c_tenant = (guardian_doc or {}).get("tenant_id")
        c_sig, c_fp, c_signer = await pqc_sign_or_delegate_fn(
            req.guardian_lns, c_msg, tenant_id=c_tenant,
            gateway_prefix="RECOVERY-GATEWAY",
        )
        await finalise_block_fn(
            index=c_idx, timestamp=contrib_ts, tx_id=c_tx_id,
            kind="KeyShareContribute", doc_hash=c_doc_hash, signer=c_signer,
        )
        await db.transactions.insert_one({
            "tx_id": c_tx_id, "block_index": c_idx, "timestamp": contrib_ts,
            "kind": "KeyShareContribute", "summary": c_summary,
            "doc_hash": c_doc_hash,
            "sender_public_key": c_fp, "signature": c_sig,
            "signed_with": pqc_algorithm, "signer_entity": c_signer,
            "delegated_for": req.guardian_lns if c_signer != req.guardian_lns else None,
            "event": "contribute", "request_id": req.request_id,
        })
        extras: dict = {
            "contribute_tx_id": c_tx_id,
            "contribute_block_index": c_idx,
        }
        if new_status == "ready":
            ts = core.utc_iso()
            meta = await db.meta.find_one_and_update(
                {"_id": "seeded"}, {"$inc": {"block_height": 1, "tx_total": 1}}, return_document=True,
            )
            new_idx = meta["block_height"]
            tx_id = f"tx-{core.det_hex(f'ksr-{req.request_id}', 12)}"
            summary = f"KeyShareRecover · {rq['lns']} · 2/3 guardians"
            recovery_canonical = "|".join(
                [req.request_id, rq["lns"]] + [c["guardian_lns"] for c in contribs]
            ).encode()
            tx_msg = ("|".join([tx_id, str(new_idx), ts, "KeyShareRecover", summary])).encode("utf-8")
            sig_hex, signer_fp = await core.pqc_sign("platform.notary", tx_msg, role="platform")
            on_chain_hash = hashlib.sha3_512(recovery_canonical).hexdigest()
            await chain.finalise_block_for_tx(
                index=new_idx, timestamp=ts, tx_id=tx_id,
                kind="KeyShareRecover", doc_hash=on_chain_hash, signer="platform.notary",
            )
            await db.transactions.insert_one({
                "tx_id": tx_id, "block_index": new_idx, "timestamp": ts,
                "kind": "KeyShareRecover", "summary": summary,
                "sender_public_key": signer_fp, "signature": sig_hex,
                "signed_with": core.PQC_ALGORITHM,
                "signer_entity": "platform.notary", "doc_hash": on_chain_hash,
            })
            extras["ready_tx_id"] = tx_id
            extras["ready_block_index"] = new_idx
        return {"ok": True, "status": new_status, "contributions_count": len(contribs), **extras}

    api.include_router(router)
