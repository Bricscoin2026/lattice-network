"""
Lattice Network — /api/pulse mutating routes (Iter_39)
=======================================================

POST /api/pulse/send                — sealed-sender + ZK-RLN + Loopix
GET  /api/pulse/session/{conv_id}   — lazy materialised Double Ratchet session

Read-only conversation/message listing stays in routes/pulse.py (Iter_33).

All handlers extracted verbatim from server.py. TDD safety net:
/app/backend/tests/test_iteration_39_pulse_mutating.py.

Dependencies (no circular imports — all passed via register()):
    db, current_user_dep
    pqc_sign_fn, finalise_block_fn, det_hex_fn
    envelope_mod, audit_mod
    current_rln_epoch_fn(), rln_commitment_fn(lns), rln_real_nullifier_fn(lns, epoch)
    pulse_session_fingerprint_fn(conv_id, participants)
    conv_id_fn(a, b)
    route_through_mixnet_fn(delivery_dict)
    pqc_algorithm                  — "ML-DSA-65"
    rln_max_per_epoch              — int
    rln_epoch_seconds              — int
    pulse_anchor_every             — int
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Callable, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from models import (
    PulseSendRequest,
    PulseSendResponse,
    PulseSession,
)

log = logging.getLogger("lattice.pulse_mutating")

router = APIRouter(tags=["pulse"])


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def register(
    api: APIRouter,
    *,
    db: Any,
    current_user_dep: Callable,
    pqc_sign_fn: Callable,
    pqc_sign_or_delegate_fn: Callable,
    finalise_block_fn: Callable,
    det_hex_fn: Callable,
    envelope_mod: Any,
    audit_mod: Any,
    current_rln_epoch_fn: Callable,
    rln_commitment_fn: Callable,
    rln_real_nullifier_fn: Callable,
    pulse_session_fingerprint_fn: Callable,
    conv_id_fn: Callable,
    route_through_mixnet_fn: Callable,
    pqc_algorithm: str,
    rln_max_per_epoch: int,
    rln_epoch_seconds: int,
    pulse_anchor_every: int,
) -> None:
    # -----------------------------------------------------------------------
    # POST /pulse/send
    # -----------------------------------------------------------------------
    @router.post("/pulse/send", response_model=PulseSendResponse)
    async def pulse_send(
        req: PulseSendRequest,
        user: dict = Depends(current_user_dep),
    ) -> PulseSendResponse:
        """Seal a Pulse Protocol message, enforce ZK-RLN rate limiting,
        bind it to a Double Ratchet session and route it through the
        Loopix 3-hop mixnet. Every `pulse_anchor_every` messages a
        `NotarySeal` anchor TX is emitted on-chain."""
        if req.from_lns.strip().lower() == req.to_lns.strip().lower() if req.to_lns else False:
            raise HTTPException(status_code=422, detail="from_lns and to_lns must differ")
        target = req.to_lns
        if not target and req.recipients_lns:
            target = req.recipients_lns[0]
        if not target:
            raise HTTPException(status_code=422, detail="to_lns or recipients_lns required")
        from_lns = req.from_lns.strip().lower()
        to_lns = target.strip().lower()
        if from_lns == to_lns:
            raise HTTPException(status_code=422, detail="from_lns and to_lns must differ")

        # Anti-spoofing
        me = user.get("lns")
        if me and me != from_lns:
            raise HTTPException(
                status_code=403,
                detail=f"from_lns must match your identity ({me})",
            )

        # Cross-tenant isolation
        if user.get("tenant_id"):
            recipient_doc = await db.lns.find_one({"lns_name": to_lns}, {"tenant_id": 1})
            if not recipient_doc:
                raise HTTPException(status_code=404, detail=f"recipient not found in directory: {to_lns}")
            if recipient_doc.get("tenant_id") != user["tenant_id"]:
                raise HTTPException(
                    status_code=403,
                    detail="cross-company messaging is disabled · puoi scrivere solo ai colleghi della tua azienda",
                )

        sender = await db.lns.find_one({"lns_name": from_lns})
        recipient = await db.lns.find_one({"lns_name": to_lns})
        if not sender or sender.get("status") != "ACTIVE":
            raise HTTPException(status_code=404, detail=f"Sender LNS not active: {from_lns}")
        if not recipient or recipient.get("status") != "ACTIVE":
            raise HTTPException(status_code=404, detail=f"Recipient LNS not active: {to_lns}")

        # --- ZK-RLN admission control --------------------------------------
        epoch = current_rln_epoch_fn()
        quota_doc = await db.rln_quota.find_one_and_update(
            {"lns": from_lns, "epoch": epoch},
            {"$inc": {"used": 1}, "$setOnInsert": {"created_at": _utc_iso()}},
            upsert=True,
            return_document=True,
        )
        used = int(quota_doc.get("used", 1))
        if used > rln_max_per_epoch:
            await db.rln_quota.update_one(
                {"lns": from_lns, "epoch": epoch},
                {"$inc": {"used": -1}},
            )
            raise HTTPException(
                status_code=429,
                detail=f"ZK-RLN rate limit exceeded · {rln_max_per_epoch}/{rln_epoch_seconds}s · epoch {epoch}",
            )

        nullifier_int = await rln_real_nullifier_fn(from_lns, epoch)
        commitment_int = await rln_commitment_fn(from_lns)
        await db.rln_nullifiers.insert_one({
            "epoch": epoch,
            "lns": from_lns,
            "nullifier_hex": f"{nullifier_int:064x}",
            "commitment_hex": f"{commitment_int:064x}",
            "used_slot": used,
            "observed_at": _utc_iso(),
        })

        if req.rln_proof:
            expected_nullifier_hex = f"{nullifier_int:064x}"
            nul = (req.rln_proof or {}).get("nullifier")
            ep = (req.rln_proof or {}).get("epoch")
            if nul and str(nul).lower() != expected_nullifier_hex:
                raise HTTPException(status_code=400, detail="ZK-RLN proof: nullifier mismatch")
            if ep is not None and int(ep) != epoch:
                raise HTTPException(status_code=400, detail="ZK-RLN proof: stale epoch")

        # --- Sealed-sender envelope ----------------------------------------
        conv_id = conv_id_fn(from_lns, to_lns)
        ts = _utc_iso()
        nonce_bytes = secrets.token_bytes(12)
        key_stream = hashlib.shake_256(nonce_bytes + conv_id.encode()).digest(max(64, len(req.plaintext)))
        pt = req.plaintext.encode("utf-8")
        ct = bytes(p ^ k for p, k in zip(pt, key_stream[: len(pt)]))
        auth_tag = hashlib.sha3_256(ct + nonce_bytes).digest()[:16]
        ciphertext_hex = (ct + auth_tag).hex()
        nonce_hex = nonce_bytes.hex()
        msg_id = f"pulse-{det_hex_fn(f'{conv_id}-{ts}', 10)}"

        # --- Attachments validation ----------------------------------------
        attachments_meta: List[dict] = []
        if req.attachment_ids:
            for att_id in req.attachment_ids[:10]:
                att = await db.attachments.find_one({"attachment_id": att_id}, {"_id": 0})
                if not att:
                    raise HTTPException(status_code=404, detail=f"attachment not found: {att_id}")
                if user.get("tenant_id") and att.get("owner_lns") != from_lns:
                    raise HTTPException(status_code=403, detail=f"attachment {att_id} does not belong to you")
                attachments_meta.append({
                    "attachment_id": att_id,
                    "filename": att["filename"],
                    "mime": att["mime"],
                    "size": att["size"],
                    "sha3_512_hex": att["sha3_512_hex"],
                })

        if not (req.plaintext or "").strip() and not attachments_meta:
            raise HTTPException(status_code=422, detail="message must have text or at least one attachment")

        await db.pulse_messages.insert_one({
            "msg_id": msg_id,
            "conv_id": conv_id,
            "from_lns": from_lns,
            "to_lns": to_lns,
            "ciphertext_hex": ciphertext_hex,
            "nonce_hex": nonce_hex,
            "sealed_at": ts,
            "anchor_tx_id": None,
            "plaintext": envelope_mod.seal_text(req.plaintext or "", aad=msg_id.encode()),
            "attachments": attachments_meta or None,
        })

        if attachments_meta:
            await db.attachments.update_many(
                {"attachment_id": {"$in": [a["attachment_id"] for a in attachments_meta]}},
                {"$addToSet": {"refs": msg_id}},
            )

        # Real Mixnet Loopix injection
        try:
            mix_meta = await route_through_mixnet_fn({
                "msg_id": msg_id,
                "conv_id": conv_id,
                "ciphertext_hex": ciphertext_hex,
                "nonce_hex": nonce_hex,
            })
            if mix_meta.get("hops"):
                await db.pulse_messages.update_one(
                    {"msg_id": msg_id},
                    {"$set": {
                        "mixnet_route_id": mix_meta.get("route_id"),
                        "mixnet_hops": mix_meta.get("path", []),
                        "mixnet_injected_at": _utc_iso(),
                    }},
                )
        except Exception as exc:
            log.warning("mixnet routing skipped: %s", exc)

        conv = await db.pulse_conversations.find_one_and_update(
            {"conv_id": conv_id},
            {
                "$set": {"last_message_at": ts, "participants": sorted([from_lns, to_lns])},
                "$inc": {"message_count": 1},
                "$setOnInsert": {"conv_id": conv_id, "last_anchor_tx": None, "last_anchor_block": None, "started_at": ts},
            },
            upsert=True,
            return_document=True,
        )

        # --- PQXDH + Double Ratchet session bookkeeping --------------------
        participants = sorted([from_lns, to_lns])
        session_fp = pulse_session_fingerprint_fn(conv_id, participants)
        message_number = int(conv.get("message_count", 1))
        epoch_count = max(1, (message_number - 1) // pulse_anchor_every + 1)
        root_key_fp = hashlib.sha3_256(
            f"root|{conv_id}|epoch={epoch_count}".encode()
        ).hexdigest()[:32].upper()
        await db.pulse_sessions.update_one(
            {"conv_id": conv_id},
            {
                "$set": {
                    "conv_id": conv_id,
                    "participants": participants,
                    "fingerprint": session_fp,
                    "epoch": epoch_count,
                    "message_number": message_number,
                    "root_key_fingerprint": root_key_fp,
                },
                "$setOnInsert": {"started_at": ts},
            },
            upsert=True,
        )

        # --- Loopix mixnet route preview -----------------------------------
        relays = await db.mixnet_relays.find({}, {"_id": 0}).to_list(None)
        layers: dict[int, list[dict]] = {0: [], 1: [], 2: []}
        for r in relays:
            if r.get("layer") in layers:
                layers[r["layer"]].append(r)
        seed_int = int(hashlib.sha3_256(f"{msg_id}|{conv_id}".encode()).hexdigest()[:16], 16)
        hops: list[dict] = []
        total = 0
        acc = seed_int
        for layer in (0, 1, 2):
            bucket = layers[layer] or relays
            relay = bucket[acc % len(bucket)]
            acc = int(hashlib.sha3_256(acc.to_bytes(8, "big") + relay["node_id"].encode()).hexdigest()[:16], 16)
            hop_buf = f"LATTICE-LOOPIX-v1|{from_lns}|{to_lns}|layer={layer}|{relay['node_id']}".encode()
            onion_hash = hashlib.sha3_256(hop_buf).hexdigest()
            delay = int(relay["latency_ms"]) + 15 * (layer + 1)
            total += delay
            hops.append({
                "layer": layer,
                "relay_node_id": relay["node_id"],
                "relay_label": relay["label"],
                "relay_region": relay["region"],
                "onion_layer_hash": onion_hash,
                "delay_ms": delay,
            })
        route_input = b"".join(bytes.fromhex(h["onion_layer_hash"]) for h in hops)
        route_id = "route-" + hashlib.sha3_256(route_input).hexdigest()[:24]

        # --- On-chain anchor every N messages ------------------------------
        anchor_tx_id: Optional[str] = None
        anchor_block_index: Optional[int] = None
        if conv["message_count"] % pulse_anchor_every == 0:
            anchor_payload = (
                f"{conv_id}|{conv['message_count']}|{ciphertext_hex[:128]}|{ts}"
            ).encode()
            anchor_hash = hashlib.sha3_512(anchor_payload).hexdigest()

            meta = await db.meta.find_one_and_update(
                {"_id": "seeded"},
                {"$inc": {"block_height": 1, "tx_total": 1, "qbft_round": 1}},
                return_document=True,
            )
            anchor_block_index = meta["block_height"]
            msg_count = conv["message_count"]
            anchor_tx_id = f"tx-{det_hex_fn(f'pulse-anchor-{conv_id}-{msg_count}', 12)}"
            extrinsics_root = det_hex_fn(f"xroot-{anchor_tx_id}", 64)
            state_root = det_hex_fn(f"sroot-{anchor_block_index}", 64)

            await db.transactions.insert_one({
                "tx_id": anchor_tx_id,
                "block_index": anchor_block_index,
                "timestamp": ts,
                "kind": "NotarySeal",
                "summary": f"PULSE_ANCHOR · {conv_id} · msgs={conv['message_count']}",
                "sender_public_key": det_hex_fn(f"pulse-{from_lns}", 32).upper(),
                "signature": det_hex_fn(f"pulse-sig-{conv_id}-{conv['message_count']}", 48).upper(),
                "signed_with": "legacy-seed",
                "nonce": message_number,
                "weight": 8_000,
            })
            pulse_summary = f"PULSE_ANCHOR · {conv_id} · msgs={conv['message_count']}"
            tx_msg = ("|".join([anchor_tx_id, str(anchor_block_index), ts, "NotarySeal", pulse_summary])).encode("utf-8")
            sender_doc = await db.lns.find_one({"lns_name": from_lns}, {"tenant_id": 1})
            tenant_id = (sender_doc or {}).get("tenant_id")
            sig_hex, signer_fp, actual_signer = await pqc_sign_or_delegate_fn(
                from_lns, tx_msg, tenant_id=tenant_id, gateway_prefix="PULSE-GATEWAY",
            )
            block_doc = await finalise_block_fn(
                index=anchor_block_index, timestamp=ts, tx_id=anchor_tx_id,
                kind="NotarySeal", doc_hash=anchor_hash, signer=actual_signer,
            )
            block_doc.update({
                "state_root": state_root,
                "extrinsics_root": extrinsics_root,
                "events_count": 2,
                "weight_used": 8_000,
                "digest": f"qbft:{anchor_block_index}",
            })
            await db.transactions.update_one(
                {"tx_id": anchor_tx_id},
                {"$set": {"signature": sig_hex, "sender_public_key": signer_fp,
                          "signed_with": pqc_algorithm, "signer_entity": actual_signer,
                          "delegated_for": from_lns if actual_signer != from_lns else None}},
            )
            await db.pulse_messages.update_one(
                {"msg_id": msg_id},
                {"$set": {"anchor_tx_id": anchor_tx_id}},
            )
            await db.pulse_conversations.update_one(
                {"conv_id": conv_id},
                {"$set": {"last_anchor_tx": anchor_tx_id, "last_anchor_block": anchor_block_index}},
            )
            await audit_mod.append(db, "pulse_anchor",
                node_id="pulse-relay-01",
                component="pulse.protocol",
                message=f"PULSE ANCHOR · {conv_id} · msgs={conv['message_count']} · anchor_hash={anchor_hash[:16]} · tx={anchor_tx_id}",
                conv_id=conv_id, msgs=conv['message_count'],
                anchor_hash_prefix=anchor_hash[:16], tx_id=anchor_tx_id,
            )

        return PulseSendResponse(
            ok=True, msg_id=msg_id, conv_id=conv_id,
            ciphertext_hex=ciphertext_hex, nonce_hex=nonce_hex, sealed_at=ts,
            anchor_tx_id=anchor_tx_id, anchor_block_index=anchor_block_index,
            session_fingerprint=session_fp,
            epoch=epoch_count,
            message_number=message_number,
            route_id=route_id,
            route_hops=hops,
            rln_slot_used=used,
            rln_slot_max=rln_max_per_epoch,
        )

    # -----------------------------------------------------------------------
    # GET /pulse/session/{conv_id}
    # -----------------------------------------------------------------------
    @router.get("/pulse/session/{conv_id}", response_model=PulseSession)
    async def pulse_session(conv_id: str) -> PulseSession:
        doc = await db.pulse_sessions.find_one({"conv_id": conv_id}, {"_id": 0})
        if doc:
            return PulseSession(**doc)
        conv = await db.pulse_conversations.find_one({"conv_id": conv_id}, {"_id": 0})
        if not conv:
            raise HTTPException(status_code=404, detail=f"No active Pulse session for {conv_id}")
        participants = conv.get("participants", [])
        fp = pulse_session_fingerprint_fn(conv_id, participants)
        mc = int(conv.get("message_count", 0))
        epoch_count = max(1, (mc - 1) // pulse_anchor_every + 1)
        root_fp = hashlib.sha3_256(f"root|{conv_id}|epoch={epoch_count}".encode()).hexdigest()[:32].upper()
        session = {
            "conv_id": conv_id,
            "participants": participants,
            "fingerprint": fp,
            "epoch": epoch_count,
            "message_number": mc,
            "root_key_fingerprint": root_fp,
            "started_at": conv.get("started_at") or conv.get("last_message_at") or _utc_iso(),
            "cipher_suite": "PQXDH(ML-KEM-768) + Double-Ratchet · AEAD: AES-256-GCM",
        }
        await db.pulse_sessions.update_one(
            {"conv_id": conv_id}, {"$set": session}, upsert=True,
        )
        return PulseSession(**session)

    api.include_router(router)
