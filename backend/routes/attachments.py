"""
Lattice Network — /api/attachments/* routes (Iter_40)
======================================================

POST /api/attachments/upload
GET  /api/attachments/{attachment_id}/meta
GET  /api/attachments/{attachment_id}

Extracted verbatim from server.py — Iter_40.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/attachments", tags=["attachments"])


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


ATTACH_DIR = Path("/app/data/attachments")
ATTACH_DIR.mkdir(parents=True, exist_ok=True)
MAX_ATTACH_BYTES = 10 * 1024 * 1024
ALLOWED_MIME_PREFIXES = ("image/", "application/", "text/", "video/mp4", "audio/")
ALLOWED_EXTS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic",
    ".txt", ".csv", ".md", ".json", ".xml",
    ".zip", ".7z",
    ".mp4", ".mov", ".mp3", ".wav", ".m4a",
}


class AttachmentMeta(BaseModel):
    attachment_id: str
    filename: str
    mime: str
    size: int
    sha3_512_hex: str
    uploaded_at: str
    owner_lns: Optional[str] = None


def register(
    api: APIRouter,
    *,
    db: Any,
    current_user_dep: Callable,
) -> None:

    async def _attachment_access_check(attachment_id: str, user: dict) -> dict:
        meta = await db.attachments.find_one({"attachment_id": attachment_id}, {"_id": 0})
        if not meta:
            raise HTTPException(status_code=404, detail="attachment not found")
        me = user.get("lns")
        if not user.get("tenant_id"):
            return meta
        if me and meta.get("owner_lns") == me:
            return meta
        msg = await db.pulse_messages.find_one(
            {"attachments.attachment_id": attachment_id},
            {"from_lns": 1, "to_lns": 1},
        )
        if msg and me in (msg.get("from_lns"), msg.get("to_lns")):
            return meta
        mail = await db.certify_mails.find_one(
            {"attachments.attachment_id": attachment_id},
            {"sender_lns": 1, "recipient_lns": 1},
        )
        if mail and me in (mail.get("sender_lns"), mail.get("recipient_lns")):
            return meta
        raise HTTPException(status_code=403, detail="you are not authorised to download this attachment")

    @router.post("/upload", response_model=AttachmentMeta)
    async def attachment_upload(
        file: UploadFile = File(...),
        user: dict = Depends(current_user_dep),
    ) -> AttachmentMeta:
        fname = file.filename or "unnamed"
        ext = Path(fname).suffix.lower()
        if ext and ext not in ALLOWED_EXTS:
            raise HTTPException(status_code=415, detail=f"extension not allowed: {ext}")
        claimed_mime = file.content_type or "application/octet-stream"
        if not claimed_mime.startswith(ALLOWED_MIME_PREFIXES):
            raise HTTPException(status_code=415, detail=f"mime not allowed: {claimed_mime}")

        blob = await file.read()
        if len(blob) == 0:
            raise HTTPException(status_code=422, detail="empty file")
        if len(blob) > MAX_ATTACH_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"file too large (max {MAX_ATTACH_BYTES // 1024 // 1024} MB)",
            )
        from security import assert_safe_attachment
        real_mime = assert_safe_attachment(blob, claimed_mime)
        mime = real_mime
        attachment_id = f"att-{secrets.token_hex(12)}"
        sha = hashlib.sha3_512(blob).hexdigest()
        target = ATTACH_DIR / attachment_id
        target.write_bytes(blob)
        meta = {
            "attachment_id": attachment_id,
            "filename": fname,
            "mime": mime,
            "size": len(blob),
            "sha3_512_hex": sha,
            "uploaded_at": _utc_iso(),
            "owner_lns": user.get("lns"),
            "tenant_id": user.get("tenant_id"),
            "path": str(target),
            "refs": [],
        }
        await db.attachments.insert_one(meta)
        return AttachmentMeta(
            attachment_id=attachment_id,
            filename=fname,
            mime=mime,
            size=len(blob),
            sha3_512_hex=sha,
            uploaded_at=meta["uploaded_at"],
            owner_lns=meta.get("owner_lns"),
        )

    @router.get("/{attachment_id}/meta", response_model=AttachmentMeta)
    async def attachment_meta(
        attachment_id: str,
        user: dict = Depends(current_user_dep),
    ) -> AttachmentMeta:
        meta = await _attachment_access_check(attachment_id, user)
        return AttachmentMeta(**{k: meta[k] for k in (
            "attachment_id", "filename", "mime", "size", "sha3_512_hex",
            "uploaded_at", "owner_lns",
        ) if k in meta})

    @router.get("/{attachment_id}")
    async def attachment_download(
        attachment_id: str,
        user: dict = Depends(current_user_dep),
    ):
        meta = await _attachment_access_check(attachment_id, user)
        path = Path(meta["path"])
        if not path.exists():
            raise HTTPException(status_code=410, detail="attachment file missing on disk")
        return StreamingResponse(
            path.open("rb"),
            media_type=meta["mime"],
            headers={
                "Content-Disposition": f'inline; filename="{meta["filename"]}"',
                "Content-Length": str(meta["size"]),
                "X-Attachment-Sha3-512": meta["sha3_512_hex"],
            },
        )

    api.include_router(router)
