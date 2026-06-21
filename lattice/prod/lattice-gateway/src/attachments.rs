//! M8 batch — Attachments file storage (`POST/GET/DELETE /api/attachments/*`).
//!
//! On-disk layout (Python-compat): `/app/data/attachments/{attachment_id}` with
//! sidecar metadata in MongoDB collection `attachments`.
//!
//! Endpoints:
//!   POST   /api/attachments/upload         (multipart/form-data, field=file)
//!   GET    /api/attachments/{id}/meta      (metadata read)
//!   GET    /api/attachments/{id}           (file download stream)
//!   DELETE /api/attachments/{id}           (delete + unlink, owner-only)
//!
//! Access control mirrors Python `_attachment_access_check`:
//!   1. sovereign (no tenant_id) → full access
//!   2. owner_lns → full access
//!   3. participant on pulse_message that references this attachment
//!   4. party of certify_mail that references this attachment

use std::collections::HashSet;
use std::path::PathBuf;

use axum::{
    body::Body,
    extract::{Path, Request, State},
    http::{header, HeaderMap, StatusCode},
    response::{IntoResponse, Response},
    Json,
};
use bson::{doc, Document};
use chrono::{SecondsFormat, Utc};
use futures::StreamExt;
use rand::RngCore;
use serde::{Deserialize, Serialize};
use sha3::{Digest, Sha3_512};
use tokio::io::AsyncWriteExt;

use crate::misc::jwt_decode;
use crate::AppState;

const MAX_BYTES: usize = 10 * 1024 * 1024;
const ATTACH_DIR: &str = "/app/data/attachments";

fn allowed_extensions() -> HashSet<&'static str> {
    [".pdf",".doc",".docx",".xls",".xlsx",".ppt",".pptx",
     ".jpg",".jpeg",".png",".gif",".webp",".heic",
     ".txt",".csv",".md",".json",".xml",".zip",".7z",
     ".mp4",".mov",".mp3",".wav",".m4a"].into_iter().collect()
}
fn allowed_mime_prefixes() -> &'static [&'static str] {
    &["image/","application/","text/","video/mp4","audio/"]
}

#[derive(Debug, Serialize)]
pub struct AttError { pub detail: String }
fn err(code: StatusCode, msg: impl Into<String>) -> (StatusCode, Json<AttError>) {
    (code, Json(AttError { detail: msg.into() }))
}

fn utc_iso() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Micros, true)
}

fn rand_id(prefix: &str, len: usize) -> String {
    let mut b = vec![0u8; len / 2];
    rand::rngs::OsRng.fill_bytes(&mut b);
    format!("{}{}", prefix, hex::encode(b))
}

async fn access_check(state: &AppState, attachment_id: &str, headers: &HeaderMap)
    -> Result<Document, (StatusCode, Json<AttError>)>
{
    let coll = state.db.collection::<Document>("attachments");
    let meta = coll.find_one(doc! {"attachment_id": attachment_id})
        .projection(doc! {"_id": 0}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?
        .ok_or_else(|| err(StatusCode::NOT_FOUND, "attachment not found"))?;

    let claims = jwt_decode(headers);
    let me = claims.as_ref().and_then(|c| c.sub.clone()).unwrap_or_default();
    let tenant = claims.as_ref().and_then(|c| c.tenant_id.clone()).unwrap_or_default();

    // Sovereign caller (no tenant_id in JWT) gets unconditional access.
    if tenant.is_empty() { return Ok(meta); }

    if !me.is_empty() && meta.get_str("owner_lns").unwrap_or("") == me {
        return Ok(meta);
    }
    // Pulse references
    if let Ok(Some(m)) = state.db.collection::<Document>("pulse_messages")
        .find_one(doc! {"attachments.attachment_id": attachment_id})
        .projection(doc! {"from_lns": 1, "to_lns": 1}).await
    {
        let from = m.get_str("from_lns").unwrap_or("");
        let to = m.get_str("to_lns").unwrap_or("");
        if !me.is_empty() && (me == from || me == to) { return Ok(meta); }
    }
    // Certify references
    if let Ok(Some(m)) = state.db.collection::<Document>("certify_mails")
        .find_one(doc! {"attachments.attachment_id": attachment_id})
        .projection(doc! {"sender_lns": 1, "recipient_lns": 1}).await
    {
        let s = m.get_str("sender_lns").unwrap_or("");
        let r = m.get_str("recipient_lns").unwrap_or("");
        if !me.is_empty() && (me == s || me == r) { return Ok(meta); }
    }
    Err(err(StatusCode::FORBIDDEN, "you are not authorised to download this attachment"))
}

// ---------------------------------------------------------------------------
// POST /api/attachments/upload (multipart/form-data, field=file)
// ---------------------------------------------------------------------------

#[derive(Debug, Serialize)]
pub struct AttachmentMeta {
    pub attachment_id: String,
    pub filename: String,
    pub mime: String,
    pub size: i64,
    pub sha3_512_hex: String,
    pub uploaded_at: String,
    pub owner_lns: Option<String>,
}

pub async fn attachment_upload(
    State(state): State<AppState>,
    headers: HeaderMap,
    req: Request,
) -> Result<Json<AttachmentMeta>, (StatusCode, Json<AttError>)> {
    use multer::Multipart;
    let claims = jwt_decode(&headers);
    let me = claims.as_ref().and_then(|c| c.sub.clone());
    let tenant = claims.as_ref().and_then(|c| c.tenant_id.clone()).unwrap_or_default();

    let ct = req.headers().get(header::CONTENT_TYPE)
        .and_then(|v| v.to_str().ok()).unwrap_or("");
    let boundary = multer::parse_boundary(ct)
        .map_err(|e| err(StatusCode::UNSUPPORTED_MEDIA_TYPE, format!("not multipart: {e}")))?;
    let body_stream = req.into_body().into_data_stream()
        .map(|res| res.map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e.to_string())));
    let mut mp = Multipart::new(body_stream, boundary);

    let mut blob: Vec<u8> = Vec::new();
    let mut fname = String::new();
    let mut claimed_mime = "application/octet-stream".to_string();
    while let Some(field) = mp.next_field().await
        .map_err(|e| err(StatusCode::BAD_REQUEST, format!("multipart: {e}")))?
    {
        if field.name() == Some("file") {
            fname = field.file_name().unwrap_or("unnamed").to_string();
            claimed_mime = field.content_type().map(|m| m.to_string())
                .unwrap_or("application/octet-stream".to_string());
            let mut field = field;
            while let Some(chunk) = field.chunk().await
                .map_err(|e| err(StatusCode::BAD_REQUEST, format!("multipart chunk: {e}")))?
            {
                if blob.len() + chunk.len() > MAX_BYTES {
                    return Err(err(StatusCode::PAYLOAD_TOO_LARGE,
                        format!("file too large (max {} MB)", MAX_BYTES / 1024 / 1024)));
                }
                blob.extend_from_slice(&chunk);
            }
        }
    }
    if blob.is_empty() {
        return Err(err(StatusCode::UNPROCESSABLE_ENTITY, "empty file"));
    }

    let ext = std::path::Path::new(&fname).extension()
        .and_then(|s| s.to_str()).map(|s| format!(".{}", s.to_lowercase())).unwrap_or_default();
    let allowed = allowed_extensions();
    if !ext.is_empty() && !allowed.contains(ext.as_str()) {
        return Err(err(StatusCode::UNSUPPORTED_MEDIA_TYPE, format!("extension not allowed: {ext}")));
    }
    if !allowed_mime_prefixes().iter().any(|p| claimed_mime.starts_with(p)) {
        return Err(err(StatusCode::UNSUPPORTED_MEDIA_TYPE, format!("mime not allowed: {claimed_mime}")));
    }

    // Compute SHA3-512 + write to disk.
    let mut h = Sha3_512::new(); Digest::update(&mut h, &blob);
    let sha = hex::encode(h.finalize());
    let attachment_id = rand_id("att-", 24);
    tokio::fs::create_dir_all(ATTACH_DIR).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("mkdir: {e}")))?;
    let target = PathBuf::from(ATTACH_DIR).join(&attachment_id);
    let mut f = tokio::fs::File::create(&target).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("write: {e}")))?;
    f.write_all(&blob).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("write: {e}")))?;

    let ts = utc_iso();
    let meta = doc! {
        "attachment_id": &attachment_id,
        "filename": &fname,
        "mime": &claimed_mime,
        "size": blob.len() as i64,
        "sha3_512_hex": &sha,
        "uploaded_at": &ts,
        "owner_lns": me.clone().unwrap_or_default(),
        "tenant_id": &tenant,
        "path": target.to_string_lossy().to_string(),
        "refs": bson::Bson::Array(vec![]),
    };
    state.db.collection::<Document>("attachments").insert_one(meta).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;

    Ok(Json(AttachmentMeta {
        attachment_id, filename: fname, mime: claimed_mime,
        size: blob.len() as i64, sha3_512_hex: sha, uploaded_at: ts,
        owner_lns: me,
    }))
}

// ---------------------------------------------------------------------------
// GET /api/attachments/{id}/meta
// ---------------------------------------------------------------------------

pub async fn attachment_meta(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(attachment_id): Path<String>,
) -> Result<Json<AttachmentMeta>, (StatusCode, Json<AttError>)> {
    let meta = access_check(&state, &attachment_id, &headers).await?;
    Ok(Json(AttachmentMeta {
        attachment_id: meta.get_str("attachment_id").unwrap_or("").to_string(),
        filename: meta.get_str("filename").unwrap_or("").to_string(),
        mime: meta.get_str("mime").unwrap_or("").to_string(),
        size: meta.get_i64("size").or_else(|_| meta.get_i32("size").map(|v| v as i64)).unwrap_or(0),
        sha3_512_hex: meta.get_str("sha3_512_hex").unwrap_or("").to_string(),
        uploaded_at: meta.get_str("uploaded_at").unwrap_or("").to_string(),
        owner_lns: meta.get_str("owner_lns").ok().map(String::from),
    }))
}

// ---------------------------------------------------------------------------
// GET /api/attachments/{id}   (streaming download)
// ---------------------------------------------------------------------------

pub async fn attachment_download(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(attachment_id): Path<String>,
) -> Result<Response, (StatusCode, Json<AttError>)> {
    let meta = access_check(&state, &attachment_id, &headers).await?;
    let path = meta.get_str("path").unwrap_or("").to_string();
    let mime = meta.get_str("mime").unwrap_or("application/octet-stream").to_string();
    let fname = meta.get_str("filename").unwrap_or("download").to_string();
    let size = meta.get_i64("size").or_else(|_| meta.get_i32("size").map(|v| v as i64)).unwrap_or(0);
    let sha = meta.get_str("sha3_512_hex").unwrap_or("").to_string();

    let file = tokio::fs::File::open(&path).await
        .map_err(|_| err(StatusCode::GONE, "attachment file missing on disk"))?;
    let stream = tokio_util::io::ReaderStream::new(file);
    let body = Body::from_stream(stream);
    let mut resp = body.into_response();
    *resp.status_mut() = StatusCode::OK;
    let h = resp.headers_mut();
    h.insert(header::CONTENT_TYPE, mime.parse().unwrap_or("application/octet-stream".parse().unwrap()));
    h.insert(header::CONTENT_LENGTH, size.to_string().parse().unwrap());
    h.insert(header::CONTENT_DISPOSITION,
        format!("inline; filename=\"{}\"", fname.replace('"',"")).parse().unwrap());
    if let Ok(v) = sha.parse() { h.insert("X-Attachment-Sha3-512", v); }
    Ok(resp)
}

// ---------------------------------------------------------------------------
// DELETE /api/attachments/{id}   (owner-only)
// ---------------------------------------------------------------------------

pub async fn attachment_delete(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(attachment_id): Path<String>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<AttError>)> {
    let meta = access_check(&state, &attachment_id, &headers).await?;
    let me = jwt_decode(&headers).and_then(|c| c.sub).unwrap_or_default();
    let tenant = jwt_decode(&headers).and_then(|c| c.tenant_id).unwrap_or_default();
    // Only owner OR sovereign (no tenant) can delete.
    let owner = meta.get_str("owner_lns").unwrap_or("");
    if !tenant.is_empty() && owner != me {
        return Err(err(StatusCode::FORBIDDEN, "only the owner can delete this attachment"));
    }
    let path = meta.get_str("path").unwrap_or("").to_string();
    if !path.is_empty() {
        let _ = tokio::fs::remove_file(&path).await;
    }
    let _ = state.db.collection::<Document>("attachments")
        .delete_one(doc! {"attachment_id": &attachment_id}).await;
    Ok(Json(serde_json::json!({"ok": true, "deleted": attachment_id})))
}
