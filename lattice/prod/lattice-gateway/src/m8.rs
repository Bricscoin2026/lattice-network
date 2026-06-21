//! M8 final batch — 2FA TOTP + admin/chain ops + PEC webhook.
//!
//! Endpoints:
//!   POST /api/auth/2fa/enroll      — generate base32 secret + otpauth URI
//!   POST /api/auth/2fa/verify      — RFC 6238 verify (window=1)
//!   POST /api/auth/2fa/disable     — verify code + delete
//!   POST /api/admin/chain/reset    — wipe all chain collections (sovereign-only)
//!   GET  /api/certify/pec/webhook  — health probe
//!   POST /api/certify/pec/webhook  — receive Aruba PEC delivery receipt
//!
//! 2FA TOTP wire-compat with Python:
//!   secret stored as `envelope.seal_text(secret_base32, aad=f"totp:{lns}")`
//!   = `"v1:<base64(nonce(12) || ct || tag)>"` AES-256-GCM with AAD.
//!   The crate `totp-rs 5.7` implements RFC 6238 with SHA1, period=30s,
//!   digits=6 — identical defaults to Python `pyotp.TOTP`.

use std::time::{SystemTime, UNIX_EPOCH};

use axum::{
    extract::{Path, Query, State},
    http::{HeaderMap, StatusCode},
    Json,
};
use bson::{doc, Document};
use chrono::{SecondsFormat, Utc};
use rand::RngCore;
use serde::{Deserialize, Serialize};
use totp_rs::{Algorithm, Secret, TOTP};

use crate::misc::jwt_decode;
use crate::secret::{envelope_open_text, envelope_seal_text};
use crate::AppState;

#[derive(Debug, Serialize)]
pub struct M8Error { pub detail: String }
fn err(code: StatusCode, msg: impl Into<String>) -> (StatusCode, Json<M8Error>) {
    (code, Json(M8Error { detail: msg.into() }))
}

fn utc_iso() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Micros, true)
}

fn require_sovereign(headers: &HeaderMap) -> Result<(), (StatusCode, Json<M8Error>)> {
    if let Some(r) = headers.get("x-lattice-role").and_then(|v| v.to_str().ok()) {
        if r.eq_ignore_ascii_case("sovereign") { return Ok(()); }
    }
    if let Some(c) = jwt_decode(headers) {
        if c.role.as_deref().map(|s| s.eq_ignore_ascii_case("sovereign")).unwrap_or(false) {
            return Ok(());
        }
    }
    Err(err(StatusCode::FORBIDDEN, "sovereign role required"))
}

fn require_lns(headers: &HeaderMap) -> Result<String, (StatusCode, Json<M8Error>)> {
    jwt_decode(headers).and_then(|c| c.sub)
        .ok_or_else(|| err(StatusCode::UNAUTHORIZED, "login required"))
}

/// Build a `totp_rs::TOTP` from a base32 secret (RFC 6238 defaults =
/// SHA-1, digits=6, period=30s — same as Python `pyotp`).
fn build_totp(secret_base32: &str, account: &str) -> Result<TOTP, String> {
    let bytes = Secret::Encoded(secret_base32.to_string())
        .to_bytes().map_err(|e| format!("base32: {e:?}"))?;
    TOTP::new(Algorithm::SHA1, 6, 1, 30, bytes,
        Some("Lattice Network".to_string()),
        account.to_string()).map_err(|e| format!("totp: {e}"))
}

fn current_unix() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0)
}

// ===========================================================================
// /api/auth/2fa/enroll · /verify · /disable
// ===========================================================================

pub async fn auth_2fa_enroll(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<M8Error>)> {
    let lns = require_lns(&headers)?;
    // Generate 20 random bytes → base32 (RFC 4648 no padding)
    let mut raw = [0u8; 20];
    rand::rngs::OsRng.fill_bytes(&mut raw);
    let secret_base32 = Secret::Raw(raw.to_vec()).to_encoded().to_string();

    // Seal secret with envelope key, AAD=`totp:{lns}` (Python wire-compat).
    let aad = format!("totp:{}", lns);
    let sealed = envelope_seal_text(&secret_base32, aad.as_bytes())
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("seal: {e}")))?;

    state.db.collection::<Document>("totp_secrets").update_one(
        doc! {"lns": &lns},
        doc! {"$set": {"lns": &lns, "secret_sealed": &sealed,
                       "enrolled_at": utc_iso(), "verified": false}},
    ).upsert(true).await
    .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;

    let totp = build_totp(&secret_base32, &lns)
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e))?;
    let uri = totp.get_url();
    Ok(Json(serde_json::json!({
        "ok": true, "secret_base32": secret_base32, "otpauth_uri": uri,
    })))
}

#[derive(Debug, Deserialize)]
pub struct TotpCodeQuery { pub code: String }

pub async fn auth_2fa_verify(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(q): Query<TotpCodeQuery>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<M8Error>)> {
    let lns = require_lns(&headers)?;
    if q.code.len() != 6 {
        return Err(err(StatusCode::UNPROCESSABLE_ENTITY, "code must be 6 digits"));
    }
    let doc = state.db.collection::<Document>("totp_secrets")
        .find_one(doc! {"lns": &lns}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?
        .ok_or_else(|| err(StatusCode::NOT_FOUND,
            "no TOTP secret enrolled — call /auth/2fa/enroll first"))?;
    let sealed = doc.get_str("secret_sealed").unwrap_or("");
    let aad = format!("totp:{}", lns);
    let secret_b32 = envelope_open_text(sealed, aad.as_bytes())
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("open: {e}")))?;
    let totp = build_totp(&secret_b32, &lns)
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e))?;
    let now = current_unix();
    // window=1 → accept code from previous, current, or next 30s slot.
    let ok = totp.check(&q.code, now)
        || totp.check(&q.code, now.saturating_sub(30))
        || totp.check(&q.code, now + 30);
    if !ok {
        return Err(err(StatusCode::UNAUTHORIZED, "invalid TOTP code"));
    }
    state.db.collection::<Document>("totp_secrets").update_one(
        doc! {"lns": &lns}, doc! {"$set": {"verified": true}},
    ).await.map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    Ok(Json(serde_json::json!({"ok": true, "verified": true})))
}

pub async fn auth_2fa_disable(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(q): Query<TotpCodeQuery>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<M8Error>)> {
    let lns = require_lns(&headers)?;
    let coll = state.db.collection::<Document>("totp_secrets");
    let Some(doc) = coll.find_one(doc! {"lns": &lns}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))? else {
        return Ok(Json(serde_json::json!({"ok": true, "noop": true})));
    };
    if q.code.len() != 6 {
        return Err(err(StatusCode::UNPROCESSABLE_ENTITY, "code must be 6 digits"));
    }
    let sealed = doc.get_str("secret_sealed").unwrap_or("");
    let aad = format!("totp:{}", lns);
    let secret_b32 = envelope_open_text(sealed, aad.as_bytes())
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("open: {e}")))?;
    let totp = build_totp(&secret_b32, &lns)
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e))?;
    let now = current_unix();
    let ok = totp.check(&q.code, now)
        || totp.check(&q.code, now.saturating_sub(30))
        || totp.check(&q.code, now + 30);
    if !ok {
        return Err(err(StatusCode::UNAUTHORIZED, "invalid TOTP code"));
    }
    coll.delete_one(doc! {"lns": &lns}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    Ok(Json(serde_json::json!({"ok": true, "disabled": true})))
}

// ===========================================================================
// POST /api/admin/chain/reset (sovereign-only, dev/test ONLY)
// ===========================================================================

pub async fn admin_chain_reset(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<M8Error>)> {
    require_sovereign(&headers)?;
    if std::env::var("LATTICE_ALLOW_RESET").unwrap_or_default() != "1" {
        return Err(err(StatusCode::FORBIDDEN,
            "chain reset disabled (set LATTICE_ALLOW_RESET=1 in env to enable)"));
    }
    // Collections we wipe — same list as Python.
    let collections = [
        "blocks", "transactions", "lns", "tenants", "certify_mails",
        "pulse_messages", "pulse_conversations", "pulse_sessions",
        "rln_quota", "rln_nullifiers", "rln_secrets",
        "leads", "audit_log", "attachments", "ots_anchors",
        "alert_state", "totp_secrets", "revoked_jwts",
    ];
    let mut deleted = serde_json::Map::new();
    for name in collections.iter() {
        let r = state.db.collection::<Document>(name)
            .delete_many(doc! {}).await
            .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("{name}: {e}")))?;
        deleted.insert(name.to_string(), serde_json::json!(r.deleted_count));
    }
    let _ = state.db.collection::<Document>("meta").update_one(
        doc! {"_id": "seeded"},
        doc! {"$set": {"seeded": false, "block_height": 0_i64, "tx_total": 0_i64,
                       "qbft_round": 0_i64, "reset_at": utc_iso()}},
    ).upsert(true).await;
    Ok(Json(serde_json::json!({"ok": true, "deleted": deleted, "ts": utc_iso()})))
}

// ===========================================================================
// PEC webhook (`/api/certify/pec/webhook`) — Aruba inbound delivery receipt
// ===========================================================================

#[derive(Debug, Deserialize)]
pub struct PecWebhookBody {
    pub mail_id: String,
    pub event: String,           // "delivered" | "read" | "bounced" | …
    #[serde(default)] pub aruba_message_id: Option<String>,
    #[serde(default)] pub aruba_receipt_url: Option<String>,
    #[serde(default)] pub note: Option<String>,
}

pub async fn pec_webhook_health() -> Json<serde_json::Value> {
    Json(serde_json::json!({
        "ok": true, "service": "lattice-gateway-rust",
        "endpoint": "/api/certify/pec/webhook",
        "accepts": ["POST application/json", "events: delivered|read|bounced"],
    }))
}

pub async fn pec_webhook_receive(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<PecWebhookBody>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<M8Error>)> {
    // Optional shared-secret guard (Aruba PEC convention).
    if let Ok(expected) = std::env::var("LATTICE_PEC_WEBHOOK_SECRET") {
        if !expected.is_empty() {
            let got = headers.get("x-lattice-pec-secret")
                .and_then(|v| v.to_str().ok()).unwrap_or("");
            if got != expected {
                return Err(err(StatusCode::UNAUTHORIZED, "PEC webhook secret mismatch"));
            }
        }
    }
    let coll = state.db.collection::<Document>("certify_mails");
    let mail = coll.find_one(doc! {"mail_id": &body.mail_id}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?
        .ok_or_else(|| err(StatusCode::NOT_FOUND, format!("mail not found: {}", body.mail_id)))?;
    let now = utc_iso();
    let mut update = doc! {
        format!("pec.events.{}", body.event): &now,
        "pec.aruba_message_id": body.aruba_message_id.clone().unwrap_or_default(),
        "pec.last_event": &body.event,
        "pec.last_seen_at": &now,
    };
    if let Some(u) = body.aruba_receipt_url.as_ref() {
        update.insert("pec.aruba_receipt_url", u.clone());
    }
    if let Some(n) = body.note.as_ref() {
        update.insert("pec.last_note", n.clone());
    }
    coll.update_one(doc! {"mail_id": &body.mail_id}, doc! {"$set": update}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;

    // Audit trail
    let _ = state.db.collection::<Document>("audit_log").insert_one(doc! {
        "event": format!("pec_{}", body.event),
        "mail_id": &body.mail_id,
        "by": "aruba-pec-webhook",
        "ts": &now,
        "component": "lattice-pec",
        "message": format!("PEC {} · {}", body.event, body.mail_id),
    }).await;

    Ok(Json(serde_json::json!({"ok": true, "mail_id": body.mail_id, "event": body.event,
        "recipient": mail.get_str("recipient_lns").unwrap_or("")})))
}

// ===========================================================================
// GET /api/audit/export.jsonl  (sovereign-only)
// ===========================================================================

pub async fn audit_export(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<axum::response::Response, (StatusCode, Json<M8Error>)> {
    use axum::body::Body;
    use axum::http::header;
    use axum::response::IntoResponse;
    use futures::StreamExt;

    require_sovereign(&headers)?;
    let opts = mongodb::options::FindOptions::builder()
        .sort(doc! {"seq": 1}).projection(doc! {"_id": 0}).build();
    let mut cur = state.db.collection::<Document>("audit_log")
        .find(doc! {}).with_options(opts).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let mut out = Vec::<u8>::new();
    while let Some(d) = cur.next().await {
        if let Ok(d) = d {
            let v = bson::Bson::Document(d).into_relaxed_extjson();
            let line = serde_json::to_string(&v).unwrap_or_default();
            out.extend_from_slice(line.as_bytes());
            out.push(b'\n');
        }
    }
    let stamp = Utc::now().format("%Y%m%dT%H%M%S").to_string();
    let mut resp = Body::from(out).into_response();
    let h = resp.headers_mut();
    h.insert(header::CONTENT_TYPE, "application/x-ndjson".parse().unwrap());
    h.insert(header::CONTENT_DISPOSITION,
        format!("attachment; filename=\"lattice-audit-{}.jsonl\"", stamp).parse().unwrap());
    Ok(resp)
}

#[derive(Debug, Deserialize)]
pub struct _UnusedPath {
    pub _x: String,
}
// silence unused warnings for Path import (re-exported in some sub-modules)
#[allow(dead_code)]
fn _path_keepalive(_: Path<String>) {}
