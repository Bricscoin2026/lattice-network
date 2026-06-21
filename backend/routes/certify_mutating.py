"""
Lattice Network — /api/certify mutating routes (Iter_38)
=========================================================

POST /api/certify/send
POST /api/certify/{mail_id}/read
POST /api/certify/{mail_id}/restore
DELETE /api/certify/{mail_id}
GET /api/certify/{mail_id}/receipt.pdf

Read-only stats/recent stay in routes/certify.py (Iter_33).

All handlers extracted verbatim from server.py — TDD safety net is at
/app/backend/tests/test_iteration_38_auth_certify.py.

Dependencies (no circular imports — all passed via register()):
    db                       — Motor async client
    current_user_dep         — auth resolver
    pqc_sign_fn(entity, msg, role) -> (sig_hex, signer_fp)
    pqc_verify_fn(entity, msg, sig_hex) -> bool
    finalise_block_fn(**)    — QBFT block finaliser
    envelope_mod             — at-rest seal/open helper
    audit_mod                — hash-chained audit log
    det_hex_fn(seed, n)      — deterministic hex helper
    fire_pec_webhook_fn      — optional outbound webhook (best effort)
    pqc_algorithm            — "ML-DSA-65" string
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Callable, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from models import CertifyComposeRequest, CertifyComposeResponse

log = logging.getLogger("lattice.certify_mutating")

router = APIRouter(prefix="/certify", tags=["certify"])


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def register(
    api: APIRouter,
    *,
    db: Any,
    current_user_dep: Callable,
    pqc_sign_fn: Callable,
    pqc_sign_or_delegate_fn: Callable,
    pqc_verify_fn: Callable,
    finalise_block_fn: Callable,
    envelope_mod: Any,
    audit_mod: Any,
    det_hex_fn: Callable,
    fire_pec_webhook_fn: Callable,
    pqc_algorithm: str,
) -> None:
    # -----------------------------------------------------------------------
    # POST /certify/{mail_id}/read  (mark + optional PEC delivery receipt)
    # -----------------------------------------------------------------------
    @router.post("/{mail_id}/read")
    async def certify_mark_read(
        mail_id: str,
        req: dict = None,
        user: dict = Depends(current_user_dep),
    ) -> dict:
        me = user.get("lns")
        if not me:
            return {"ok": True, "noop": True}
        mail = await db.certify_mails.find_one({"mail_id": mail_id}, {"_id": 0})
        if not mail:
            raise HTTPException(status_code=404, detail="mail not found")
        if mail.get("recipient_lns") != me:
            return {"ok": True, "self": True}

        already_signed = bool(mail.get("delivery_receipt"))
        now_iso = _utc_iso()
        updates: dict = {}
        if not mail.get("read_at"):
            updates["read_at"] = now_iso

        signature_hex = (req or {}).get("signature_hex") if isinstance(req, dict) else None
        if signature_hex and not already_signed:
            canonical = "|".join([
                mail_id,
                mail.get("sealed_at", ""),
                mail.get("sender_lns", ""),
                mail.get("recipient_lns", ""),
                mail.get("doc_hash", ""),
            ]).encode()
            try:
                ok = await pqc_verify_fn(me, canonical, signature_hex)
            except Exception:
                ok = False
            if not ok:
                raise HTTPException(status_code=422, detail="invalid delivery signature")
            tx_id = f"tx-{secrets.token_hex(12)}"
            last = await db.blocks.find_one({}, {"_id": 0}, sort=[("index", -1)])
            new_block_index = (last["index"] + 1) if last else 1
            ts = now_iso
            tx_payload = {
                "tx_id": tx_id,
                "kind": "DeliveryReceipt",
                "summary": f"DeliveryReceipt · {mail_id} · {me}",
                "mail_id": mail_id,
                "recipient": me,
                "sender": mail.get("sender_lns"),
                "signature": signature_hex,
                "signature_hex": signature_hex,
                "sender_public_key": me,
                "signer": me,
                "signer_entity": me,
                "signed_with": pqc_algorithm,
                "signed_at": ts,
                "sealed_at": mail.get("sealed_at", ""),
                "doc_hash": mail.get("doc_hash", ""),
                "timestamp": ts,
                "block_index": new_block_index,
            }
            try:
                await finalise_block_fn(
                    index=new_block_index, timestamp=ts, tx_id=tx_id,
                    kind="DeliveryReceipt", doc_hash=mail.get("doc_hash", ""), signer=me,
                )
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"DeliveryReceipt block build error: {type(e).__name__}: {e}")
            await db.transactions.insert_one(tx_payload)
            receipt = {
                "signature_hex": signature_hex,
                "signed_at": ts,
                "tx_id": tx_id,
                "block_index": new_block_index,
                "signed_by": me,
                "canonical_preimage_sha3_512": hashlib.sha3_512(canonical).hexdigest(),
            }
            updates["delivery_receipt"] = receipt
            log.info("Delivery receipt notarised mail=%s recipient=%s tx=%s block=%d",
                     mail_id, me, tx_id, new_block_index)
            try:
                asyncio.create_task(fire_pec_webhook_fn(mail, receipt))
            except Exception as e:
                log.warning("PEC webhook scheduling failed: %s", e)

        if updates:
            await db.certify_mails.update_one({"mail_id": mail_id}, {"$set": updates})

        return {
            "ok": True,
            "read_at": updates.get("read_at") or mail.get("read_at"),
            "delivery_receipt": updates.get("delivery_receipt") or mail.get("delivery_receipt"),
        }

    # -----------------------------------------------------------------------
    # POST /certify/{mail_id}/restore
    # -----------------------------------------------------------------------
    @router.post("/{mail_id}/restore")
    async def certify_restore(
        mail_id: str,
        user: dict = Depends(current_user_dep),
    ) -> dict:
        me = user.get("lns")
        if not me:
            raise HTTPException(status_code=401, detail="login required")
        mail = await db.certify_mails.find_one({"mail_id": mail_id}, {"_id": 0})
        if not mail:
            raise HTTPException(status_code=404, detail="mail not found")
        deleted_by = mail.get("deleted_by") or []
        if me not in deleted_by:
            return {"ok": True, "noop": True}
        deleted_by.remove(me)
        await db.certify_mails.update_one({"mail_id": mail_id}, {"$set": {"deleted_by": deleted_by}})
        return {"ok": True, "restored": True}

    # -----------------------------------------------------------------------
    # GET /certify/{mail_id}/receipt.pdf
    # -----------------------------------------------------------------------
    @router.get("/{mail_id}/receipt.pdf")
    async def certify_receipt_pdf(
        mail_id: str,
        user: dict = Depends(current_user_dep),
    ):
        mail = await db.certify_mails.find_one({"mail_id": mail_id}, {"_id": 0})
        if not mail:
            raise HTTPException(status_code=404, detail="mail not found")
        me = user.get("lns")
        if user.get("tenant_id") and me not in (mail.get("sender_lns"), mail.get("recipient_lns")):
            raise HTTPException(status_code=403, detail="not a party of this mail")
        receipt = mail.get("delivery_receipt")
        if not receipt:
            raise HTTPException(
                status_code=409,
                detail="no PEC delivery receipt yet — recipient has not signed the open event",
            )

        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas as rl_canvas

        buf = BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=A4)
        W, H = A4
        M = 18 * mm
        GOLD = (0.831, 0.686, 0.216)
        DARK = (0.04, 0.06, 0.12)

        def section(title: str, y: float) -> float:
            c.setFillColorRGB(*GOLD)
            c.setFont("Helvetica-Bold", 8)
            c.drawString(M, y, title.upper())
            c.setStrokeColorRGB(*GOLD)
            c.setLineWidth(0.4)
            c.line(M, y - 2, W - M, y - 2)
            c.setFillColorRGB(0.05, 0.05, 0.05)
            return y - 6 * mm

        def kv(label: str, value: str, y: float, wrap=False) -> float:
            c.setFont("Helvetica", 7.5)
            c.setFillColorRGB(0.42, 0.42, 0.42)
            c.drawString(M, y, label.upper())
            c.setFillColorRGB(*DARK)
            c.setFont("Helvetica", 9.5)
            v = value or "—"
            if wrap and len(v) > 80:
                chunks = [v[i:i + 80] for i in range(0, len(v), 80)]
                for i, ch in enumerate(chunks):
                    c.drawString(M, y - 4 * mm - i * 4 * mm, ch)
                return y - 4 * mm - len(chunks) * 4 * mm - 2 * mm
            c.drawString(M, y - 4 * mm, v)
            return y - 8 * mm

        # Header
        c.setFillColorRGB(*DARK)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(M, H - M, "LATTICE NETWORK")
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(*GOLD)
        c.drawString(M, H - M - 5 * mm, "RICEVUTA DI CONSEGNA · PROVA LEGALE OPPONIBILE")
        c.setFillColorRGB(0.40, 0.40, 0.40)
        c.setFont("Helvetica", 8)
        c.drawRightString(W - M, H - M, datetime.now(timezone.utc).strftime("%d/%m/%Y · %H:%M UTC"))
        c.setStrokeColorRGB(*GOLD)
        c.setLineWidth(1.2)
        c.line(M, H - M - 9 * mm, W - M, H - M - 9 * mm)

        # 1. Mail metadata
        y = H - M - 17 * mm
        y = section("1. Identificazione comunicazione", y)
        y = kv("Mail ID", mail["mail_id"], y)
        y = kv("Mittente", mail.get("sender_lns", ""), y)
        y = kv("Destinatario", mail.get("recipient_lns", ""), y)
        y = kv("Data invio", mail.get("sealed_at", ""), y)
        y = kv("Classificazione", mail.get("classification", "INTERNAL"), y)
        y = kv("Oggetto", mail.get("subject", "—"), y)
        y = kv("Hash documento (SHA3-512)", mail.get("doc_hash", "")[:96] + "…", y, wrap=True)

        # 2. Receipt details
        y -= 2 * mm
        y = section("2. Ricevuta di apertura firmata digitalmente", y)
        y = kv("Firmata da (LNS destinatario)", receipt.get("signed_by", ""), y)
        y = kv("Data firma", receipt.get("signed_at", ""), y)
        y = kv("Algoritmo", "ML-DSA-65 (NIST FIPS 204 · post-quantum)", y)
        y = kv("Preimage hash (SHA3-512)", receipt.get("canonical_preimage_sha3_512", ""), y, wrap=True)
        y = kv("Firma digitale (ML-DSA-65, 3309 byte)", (receipt.get("signature_hex") or "")[:120] + "…", y, wrap=True)

        # 3. On-chain
        y -= 2 * mm
        y = section("3. Notarizzazione blockchain", y)
        y = kv("Transaction ID", receipt.get("tx_id", ""), y)
        y = kv("Block index", f"#{receipt.get('block_index', '?')}", y)
        y = kv("Consenso", "QBFT · 4 validatori · 3/4 firme ML-DSA-65", y)
        y = kv("Catena", "lattice-sovereign-it-prod", y)

        # 4. Verify instructions
        y -= 2 * mm
        y = section("4. Come verificare questa ricevuta", y)
        c.setFont("Helvetica", 8.5)
        c.setFillColorRGB(*DARK)
        lines = [
            "1. Ricostruisci il payload canonico:",
            "   <mail_id>|<sealed_at>|<sender_lns>|<recipient_lns>|<doc_hash>",
            "2. Recupera la chiave pubblica del destinatario dalla catena:",
            f"   GET /api/keystore/{mail.get('recipient_lns', '')}",
            "3. Verifica la firma digitale ML-DSA-65 con il payload canonico.",
            f"4. Verifica che il blocco #{receipt.get('block_index', '?')} contenga il TX {receipt.get('tx_id', '')}",
            "   (immutabile, firmato dai 4 validator).",
        ]
        for i, line in enumerate(lines):
            c.drawString(M, y - i * 4 * mm, line)
        y -= len(lines) * 4 * mm + 4 * mm

        # Legal footer
        c.setFillColorRGB(0.40, 0.40, 0.40)
        c.setFont("Helvetica-Oblique", 7.5)
        legal = (
            "Documento generato automaticamente dalla rete Lattice Network. La firma ML-DSA-65 è un primitivo "
            "post-quantum standardizzato da NIST (FIPS 204). Il blocco è finalizzato da 4 validatori indipendenti "
            "tramite consenso QBFT bizantino. La presente ricevuta è opponibile a terzi e verificabile in modo "
            "indipendente per sempre, senza necessità di affidamento a terzi."
        )
        words = legal.split()
        ll = ""
        yy = M + 6 * mm
        for w in words:
            if c.stringWidth(ll + " " + w, "Helvetica-Oblique", 7.5) > W - 2 * M:
                c.drawString(M, yy, ll.strip())
                yy -= 3.5 * mm
                ll = w
            else:
                ll += " " + w
        if ll:
            c.drawString(M, yy, ll.strip())

        c.setFillColorRGB(*GOLD)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(W / 2, M, "LATTICE NETWORK · cybersicurezza sovrana · WhatsApp +39 351 961 8068")

        c.showPage()
        c.save()
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="receipt-{mail_id}.pdf"'},
        )

    # -----------------------------------------------------------------------
    # DELETE /certify/{mail_id}
    # -----------------------------------------------------------------------
    @router.delete("/{mail_id}")
    async def certify_delete(
        mail_id: str,
        user: dict = Depends(current_user_dep),
    ) -> dict:
        me = user.get("lns")
        if not me:
            raise HTTPException(status_code=401, detail="login required to delete mail")
        mail = await db.certify_mails.find_one({"mail_id": mail_id}, {"_id": 0})
        if not mail:
            raise HTTPException(status_code=404, detail="mail not found")
        if me not in (mail.get("sender_lns"), mail.get("recipient_lns")):
            raise HTTPException(status_code=403, detail="you can only delete mails you sent or received")
        deleted_by = mail.get("deleted_by") or []
        if me in deleted_by:
            return {"ok": True, "already_deleted": True}
        deleted_by.append(me)
        other = mail.get("sender_lns") if me == mail.get("recipient_lns") else mail.get("recipient_lns")
        if other in deleted_by:
            await db.certify_mails.delete_one({"mail_id": mail_id})
            return {"ok": True, "hard_deleted": True}
        await db.certify_mails.update_one({"mail_id": mail_id}, {"$set": {"deleted_by": deleted_by}})
        return {"ok": True, "soft_deleted": True}

    # -----------------------------------------------------------------------
    # POST /certify/send
    # -----------------------------------------------------------------------
    @router.post("/send", response_model=CertifyComposeResponse)
    async def certify_send(
        req: CertifyComposeRequest,
        user: dict = Depends(current_user_dep),
    ) -> CertifyComposeResponse:
        # Anti-spoofing — sender_lns must match the authenticated identity
        # (platform operator with no tenant_id can forge for ops).
        me = user.get("lns")
        if me and me != (req.sender_lns or "").strip().lower():
            raise HTTPException(
                status_code=403,
                detail=f"sender_lns must match your identity ({me})",
            )
        primary = (req.recipient_lns or "").strip().lower()
        multi = [r.strip().lower() for r in (req.recipients_lns or []) if r and r.strip()]
        cc = [r.strip().lower() for r in (req.cc_lns or []) if r and r.strip()]
        to_list: list[str] = []
        seen = set()
        for r in ([primary] if primary else []) + multi:
            if r and r not in seen:
                seen.add(r)
                to_list.append(r)
        if not to_list:
            raise HTTPException(status_code=422, detail="At least one recipient is required")
        cc = [r for r in cc if r not in seen]

        if user.get("tenant_id"):
            for r in to_list + cc:
                r_doc = await db.lns.find_one({"lns_name": r}, {"tenant_id": 1})
                if not r_doc:
                    raise HTTPException(status_code=404, detail=f"recipient not found: {r}")
                if r_doc.get("tenant_id") != user["tenant_id"]:
                    raise HTTPException(
                        status_code=403,
                        detail=f"cross-company mail disabled · {r} non appartiene alla tua azienda",
                    )

        all_recipients = to_list + cc
        raw = (
            f"From: {req.sender_lns}\n"
            f"To: {', '.join(to_list)}\n"
            + (f"Cc: {', '.join(cc)}\n" if cc else "")
            + f"Subject: {req.subject}\n"
            f"X-Lattice-Class: {req.classification}\n"
            f"\n{req.body}"
        ).encode("utf-8")
        doc_hash = hashlib.sha3_512(raw).hexdigest()
        bytes_len = len(raw)
        ts = _utc_iso()

        meta = await db.meta.find_one_and_update(
            {"_id": "seeded"},
            {"$inc": {"block_height": 1, "tx_total": 1, "qbft_round": 1}},
            return_document=True,
        )
        new_block_index = meta["block_height"]
        tx_id = f"tx-{det_hex_fn(f'certify-{doc_hash}-{ts}', 12)}"
        extrinsics_root = det_hex_fn(f"xroot-{tx_id}", 64)
        state_root = det_hex_fn(f"sroot-{new_block_index}", 64)
        primary_mail_id = f"mail-{det_hex_fn(f'mail-{doc_hash}-{ts}', 10)}"

        # Attachments
        attachments_meta: List[dict] = []
        if req.attachment_ids:
            for att_id in req.attachment_ids[:10]:
                att = await db.attachments.find_one({"attachment_id": att_id}, {"_id": 0})
                if not att:
                    raise HTTPException(status_code=404, detail=f"attachment not found: {att_id}")
                if user.get("tenant_id") and att.get("owner_lns") != req.sender_lns:
                    raise HTTPException(status_code=403, detail=f"attachment {att_id} does not belong to you")
                attachments_meta.append({
                    "attachment_id": att_id,
                    "filename": att["filename"],
                    "mime": att["mime"],
                    "size": att["size"],
                    "sha3_512_hex": att["sha3_512_hex"],
                })

        # One mail row per recipient leg
        mail_rows = []
        for i, recipient in enumerate(all_recipients):
            mail_rows.append({
                "mail_id": primary_mail_id if i == 0 else f"mail-{det_hex_fn(f'mail-{doc_hash}-{ts}-{i}', 10)}",
                "sender_lns": req.sender_lns,
                "recipient_lns": recipient,
                "subject_redacted": f"[REDACTED · CLASS-{req.classification}]"
                    + (f" · {'TO' if i < len(to_list) else 'CC'}({i + 1}/{len(all_recipients)})" if len(all_recipients) > 1 else ""),
                "doc_hash": doc_hash,
                "sealed_at": ts,
                "bytes": bytes_len,
                "subject": req.subject,
                "body": (
                    req.body if req.body_e2e_envelope else
                    envelope_mod.seal_text(req.body or "", aad=primary_mail_id.encode())
                ),
                "body_e2e_envelope": req.body_e2e_envelope,
                "is_e2e_encrypted": bool(req.body_e2e_envelope),
                "classification": req.classification,
                "tx_id": tx_id,
                "block_index": new_block_index,
                "attachments": attachments_meta or None,
            })
        await db.certify_mails.insert_many(mail_rows)
        if attachments_meta:
            await db.attachments.update_many(
                {"attachment_id": {"$in": [a["attachment_id"] for a in attachments_meta]}},
                {"$addToSet": {"refs": primary_mail_id}},
            )
        summary = f"NotarySeal · {doc_hash[:16].upper()} · {req.classification} · {len(all_recipients)} recipient(s)"
        tx_msg = ("|".join([tx_id, str(new_block_index), ts, "NotarySeal", summary])).encode("utf-8")
        sig_hex, signer_fp, actual_signer = await pqc_sign_or_delegate_fn(
            req.sender_lns, tx_msg, tenant_id=user.get("tenant_id"),
            gateway_prefix="CERTIFY-GATEWAY",
        )
        block_doc = await finalise_block_fn(
            index=new_block_index, timestamp=ts, tx_id=tx_id,
            kind="NotarySeal", doc_hash=doc_hash, signer=actual_signer,
        )
        await db.blocks.update_one({"index": block_doc["index"]}, {"$set": {
            "state_root": state_root,
            "extrinsics_root": extrinsics_root,
            "events_count": 2,
            "weight_used": 12_500,
            "digest": f"qbft:{new_block_index}",
        }})
        await db.transactions.insert_one({
            "tx_id": tx_id,
            "block_index": new_block_index,
            "timestamp": ts,
            "kind": "NotarySeal",
            "summary": summary,
            "sender_public_key": signer_fp,
            "signature": sig_hex,
            "signed_with": pqc_algorithm,
            "signer_entity": actual_signer,
            "delegated_for": req.sender_lns if actual_signer != req.sender_lns else None,
            "nonce": 0,
            "weight": 12_500,
        })
        await audit_mod.append(db, "certify_notary_seal",
            node_id="certify-gateway",
            component="certify.gateway",
            message=f"NOTARY SEAL · {req.sender_lns} → {len(all_recipients)} recipient(s) · class={req.classification} · doc={doc_hash[:16]} · tx={tx_id}",
            sender_lns=req.sender_lns, recipients_count=len(all_recipients),
            classification=req.classification, doc_hash_prefix=doc_hash[:16], tx_id=tx_id,
        )
        return CertifyComposeResponse(
            ok=True, mail_id=primary_mail_id, tx_id=tx_id,
            block_index=new_block_index, doc_hash=doc_hash, sealed_at=ts,
            fanout=len(all_recipients),
        )

    api.include_router(router)
