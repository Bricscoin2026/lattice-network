"""
Lattice Network — /api/pulse/* read-only routes (Iter_33)
==========================================================

Read-only Pulse endpoints (conversation list, message history,
session metadata). Mutating endpoint `POST /pulse/send` stays in
server.py because it depends on the Double-Ratchet + RLN + Mixnet
pipeline (~300 lines of intertwined crypto state) which is the next
extraction target after `chain.py` exists.
"""
from __future__ import annotations

from typing import Any, Callable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

import core
from models import PulseConversation, PulseMessage, PulseSession  # noqa: F401

router = APIRouter(prefix="/pulse", tags=["pulse"])


def register(
    api: APIRouter,
    *,
    db: Any,
    current_user_dep: Callable,
    role_dep: Callable,
    redact_for_role: Callable,
) -> None:
    @router.get("/conversations", response_model=List[PulseConversation])
    async def pulse_conversations(
        lns: Optional[str] = None,
        limit: int = Query(50, ge=1, le=200),
        user: dict = Depends(current_user_dep),
    ) -> List[PulseConversation]:
        """Personal conversation list — tenant users see ONLY their own."""
        q: dict = {}
        me = user.get("lns")
        if me:
            q["participants"] = me
        elif lns:
            q["participants"] = lns.lower()
        cursor = db.pulse_conversations.find(q, {"_id": 0}).sort("last_message_at", -1).limit(limit)
        return [PulseConversation(**c) async for c in cursor]

    @router.get("/messages", response_model=List[PulseMessage])
    async def pulse_messages(
        conv_id: str,
        limit: int = Query(100, ge=1, le=500),
        role: str = Depends(role_dep),
        user: dict = Depends(current_user_dep),
    ) -> List[PulseMessage]:
        """Messages of a conversation. Enforces participant membership +
        auto-marks messages addressed to the caller as delivered+read."""
        me = user.get("lns")
        if me:
            conv = await db.pulse_conversations.find_one(
                {"conv_id": conv_id}, {"_id": 0, "participants": 1}
            )
            if not conv:
                raise HTTPException(status_code=404, detail="conversation not found")
            if me not in (conv.get("participants") or []):
                raise HTTPException(status_code=403, detail="you are not a participant of this conversation")
            now_iso = core.utc_iso()
            await db.pulse_messages.update_many(
                {"conv_id": conv_id, "to_lns": me, "delivered_at": None},
                {"$set": {"delivered_at": now_iso}},
            )
            await db.pulse_messages.update_many(
                {"conv_id": conv_id, "to_lns": me, "read_at": None},
                {"$set": {"read_at": now_iso}},
            )
        cursor = db.pulse_messages.find({"conv_id": conv_id}, {"_id": 0}).sort("sealed_at", 1).limit(limit)
        raw = [m async for m in cursor]
        redacted = redact_for_role(role, "pulse_message", raw)
        return [PulseMessage(**m) for m in redacted]

    # Note: GET /pulse/session/{conv_id} stays in server.py because it
    # needs the lazy-materialisation helper `_pulse_session_fingerprint`
    # which is intertwined with the PQXDH key derivation routine.

    api.include_router(router)
