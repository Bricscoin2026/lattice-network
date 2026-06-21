//! OpenTimestamps Bitcoin anchor — native Rust port of `backend/ots_anchor.py`
//! and `backend/routes/ots.py`. (M7 step 5)
//!
//! The implementation follows the public OTS calendar protocol:
//!
//!   POST https://<calendar>/digest   body = raw 32-byte SHA-256 digest
//!     → returns the initial timestamp proof (binary, ~150-200 bytes)
//!   GET  https://<calendar>/timestamp/<digest_hex>
//!     → returns the upgraded timestamp once Bitcoin block is mined.
//!
//! We treat the calendar response as **opaque proof bytes** persisted in
//! `db.ots_anchors`. The Bitcoin attestation is detected by searching the
//! proof bytes for the standard OpenTimestamps Bitcoin attestation tag
//! `0588960d73d71901` (see opentimestamps.core.notary.BitcoinBlockHeader
//! Attestation.TAG). This is exactly the same byte pattern emitted by the
//! Python reference implementation.
//!
//! Functional parity with Python:
//!   ✅ digest computation byte-identical (canonical payload string)
//!   ✅ submit to first responsive calendar (fail-over over 3 public pools)
//!   ✅ persistence schema (anchor_id, proof_b64, btc_attested, etc.)
//!   ✅ list / download / status / upgrade-all endpoints
//!   ⚠️  upgrade() does not merge attestation trees — it replaces the proof
//!       with the freshest calendar response. For BTC verification, users
//!       should download `.ots` and run `ots verify` after promotion.

use std::env;
use std::time::Duration;

use axum::{
    extract::{Path, State},
    http::{header, StatusCode},
    response::{IntoResponse, Response},
    Json,
};
use base64::Engine;
use bson::{doc, Document};
use chrono::Utc;
use serde::Serialize;
use sha2::{Digest as _, Sha256};

use crate::AppState;

pub const BTC_ATTESTATION_TAG: [u8; 8] = [0x05, 0x88, 0x96, 0x0d, 0x73, 0xd7, 0x19, 0x01];

/// OTS DetachedTimestampFile magic header (32 bytes incl. version).
/// Matches `opentimestamps.core.timestamp.DetachedTimestampFile.HEADER_MAGIC`
/// (31 bytes) followed by the file format major version `0x01`.
const OTS_HEADER_MAGIC: [u8; 31] = [
    0x00, 0x4f, 0x70, 0x65, 0x6e, 0x54, 0x69, 0x6d, 0x65, 0x73, 0x74, 0x61, 0x6d, 0x70, 0x73,
    0x00, 0x00, 0x50, 0x72, 0x6f, 0x6f, 0x66, 0x00, 0xbf, 0x89, 0xe2, 0xe8, 0x84, 0xe8, 0x92, 0x94,
];
const OTS_MAJOR_VERSION: u8 = 0x01;
/// `OpSHA256` op tag — the only file-hash-op our anchors use.
const OPS_SHA256_TAG: u8 = 0x08;

/// Wrap raw calendar `Timestamp` bytes into a standard `.ots`
/// `DetachedTimestampFile` envelope so the proof is verifiable with
/// the upstream `ots verify` CLI and parseable by `opentimestamps-py`.
fn wrap_dtf(file_digest: &[u8; 32], timestamp_bytes: &[u8]) -> Vec<u8> {
    let mut out = Vec::with_capacity(OTS_HEADER_MAGIC.len() + 1 + 1 + 32 + timestamp_bytes.len());
    out.extend_from_slice(&OTS_HEADER_MAGIC);
    out.push(OTS_MAJOR_VERSION);
    out.push(OPS_SHA256_TAG);
    out.extend_from_slice(file_digest);
    out.extend_from_slice(timestamp_bytes);
    out
}

/// Strip the DTF envelope back to the raw timestamp bytes (for upgrade).
/// Returns `None` if the envelope is malformed (we then keep the input as-is).
fn unwrap_dtf(blob: &[u8]) -> Option<&[u8]> {
    if blob.len() <= OTS_HEADER_MAGIC.len() + 1 + 1 + 32 { return None; }
    if &blob[..OTS_HEADER_MAGIC.len()] != OTS_HEADER_MAGIC { return None; }
    Some(&blob[OTS_HEADER_MAGIC.len() + 1 + 1 + 32 ..])
}

const DEFAULT_CALENDARS: &[&str] = &[
    "https://a.pool.opentimestamps.org",
    "https://b.pool.opentimestamps.org",
    "https://alice.btc.calendar.catallaxy.com",
];

#[derive(Debug, Serialize)]
pub struct OtsError { pub detail: String }
fn err(code: StatusCode, msg: impl Into<String>) -> (StatusCode, Json<OtsError>) {
    (code, Json(OtsError { detail: msg.into() }))
}

pub fn is_enabled() -> bool {
    matches!(env::var("LATTICE_OTS_ENABLED").unwrap_or_default().trim(),
        "1" | "true" | "yes")
}

pub fn calendars() -> Vec<String> {
    let raw = env::var("LATTICE_OTS_CALENDARS").unwrap_or_default();
    let raw = raw.trim();
    if raw.is_empty() {
        DEFAULT_CALENDARS.iter().map(|s| s.to_string()).collect()
    } else {
        raw.split(',').map(|s| s.trim().to_string()).filter(|s| !s.is_empty()).collect()
    }
}

pub fn compute_anchor_digest(chain_id: &str, block_index: i64, block_hash: &str,
                             merkle_root: &str, ts_iso: &str) -> [u8; 32] {
    let payload = format!(
        "lattice-ots-v1|chain={}|height={}|block={}|merkle={}|ts={}",
        chain_id, block_index, block_hash, merkle_root, ts_iso,
    );
    let mut h = Sha256::new();
    sha2::Digest::update(&mut h, payload.as_bytes());
    h.finalize().into()
}

pub fn has_btc_attestation(proof: &[u8]) -> bool {
    proof.windows(BTC_ATTESTATION_TAG.len()).any(|w| w == BTC_ATTESTATION_TAG)
}

async fn submit_to_calendar(http: &reqwest::Client, url: &str, digest: &[u8; 32])
    -> Result<Vec<u8>, String>
{
    let endpoint = format!("{}/digest", url.trim_end_matches('/'));
    let resp = http.post(&endpoint)
        .header("User-Agent", "lattice-network-rust/0.30")
        .header(header::CONTENT_TYPE, "application/x-www-form-urlencoded")
        .body(digest.to_vec())
        .timeout(Duration::from_secs(15))
        .send().await
        .map_err(|e| format!("{e}"))?;
    if !resp.status().is_success() {
        return Err(format!("HTTP {}", resp.status()));
    }
    Ok(resp.bytes().await.map_err(|e| e.to_string())?.to_vec())
}

async fn fetch_upgrade(http: &reqwest::Client, url: &str, digest_hex: &str)
    -> Result<Vec<u8>, String>
{
    let endpoint = format!("{}/timestamp/{}", url.trim_end_matches('/'), digest_hex);
    let resp = http.get(&endpoint)
        .header("User-Agent", "lattice-network-rust/0.30")
        .timeout(Duration::from_secs(15))
        .send().await
        .map_err(|e| format!("{e}"))?;
    if resp.status() == 404 || resp.status() == 410 {
        return Err(format!("not yet known (HTTP {})", resp.status()));
    }
    if !resp.status().is_success() {
        return Err(format!("HTTP {}", resp.status()));
    }
    Ok(resp.bytes().await.map_err(|e| e.to_string())?.to_vec())
}

// ---------------------------------------------------------------------------
// GET /api/admin/ots/status
// ---------------------------------------------------------------------------

pub async fn ots_status(State(state): State<AppState>)
    -> Result<Json<serde_json::Value>, (StatusCode, Json<OtsError>)>
{
    let coll = state.db.collection::<Document>("ots_anchors");
    let mut anchors = Vec::new();
    use futures::StreamExt;
    let opts = mongodb::options::FindOptions::builder()
        .sort(doc! {"created_at": -1}).limit(20)
        .projection(doc! {"_id": 0, "proof_b64": 0}).build();
    if let Ok(mut cur) = coll.find(doc! {}).with_options(opts).await {
        while let Some(d) = cur.next().await {
            if let Ok(d) = d {
                anchors.push(bson::to_bson(&d).unwrap_or(bson::Bson::Null));
            }
        }
    }
    Ok(Json(serde_json::json!({
        "enabled": is_enabled(),
        "calendars": calendars(),
        "anchors": anchors,
    })))
}

// ---------------------------------------------------------------------------
// POST /api/admin/ots/anchor
// ---------------------------------------------------------------------------

pub async fn ots_create_anchor(State(state): State<AppState>)
    -> Result<Json<serde_json::Value>, (StatusCode, Json<OtsError>)>
{
    if !is_enabled() {
        return Err(err(StatusCode::SERVICE_UNAVAILABLE,
            "OpenTimestamps anchoring is disabled (set LATTICE_OTS_ENABLED=1)"));
    }
    let tip = state.db.collection::<Document>("blocks")
        .find_one(doc! {})
        .sort(doc! {"index": -1})
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?
        .ok_or_else(|| err(StatusCode::CONFLICT, "ledger is empty — nothing to anchor"))?;

    let block_index = tip.get_i64("index")
        .or_else(|_| tip.get_i32("index").map(|v| v as i64))
        .unwrap_or(0);
    let block_hash = tip.get_str("block_hash").unwrap_or("").to_string();
    let merkle_root = tip.get_str("merkle_root")
        .ok().filter(|s| !s.is_empty())
        .unwrap_or(&block_hash).to_string();
    let chain_id = env::var("LATTICE_CHAIN_ID").unwrap_or_else(|_| "lattice-sovereign-it-prod".into());
    let ts_iso = Utc::now().to_rfc3339();
    let digest = compute_anchor_digest(&chain_id, block_index, &block_hash, &merkle_root, &ts_iso);
    let digest_hex = hex::encode(digest);

    // Try each calendar until one accepts.
    let mut proof_bytes: Option<Vec<u8>> = None;
    let mut accepted_by: String = String::new();
    let mut last_err = String::new();
    for url in calendars() {
        match submit_to_calendar(&state.http, &url, &digest).await {
            Ok(b) => { proof_bytes = Some(b); accepted_by = url; break; }
            Err(e) => { last_err = format!("{url}: {e}"); continue; }
        }
    }
    let proof_bytes = proof_bytes.ok_or_else(||
        err(StatusCode::SERVICE_UNAVAILABLE, format!("all OTS calendars failed (last_err={last_err})")))?;

    // Wrap the raw Timestamp into a standard `.ots` DetachedTimestampFile
    // envelope so it can be verified by upstream `ots verify` and parsed
    // by `opentimestamps-py` byte-for-byte.
    let dtf = wrap_dtf(&digest, &proof_bytes);

    let anchor_id = format!("ots-{}-{}",
        Utc::now().format("%Y%m%d-%H%M%S"),
        &digest_hex[..8]);
    let proof_b64 = base64::engine::general_purpose::STANDARD.encode(&dtf);
    let btc_attested = has_btc_attestation(&dtf);

    let _ = state.db.collection::<Document>("ots_anchors").insert_one(doc! {
        "anchor_id": &anchor_id,
        "created_at": &ts_iso,
        "chain_id": &chain_id,
        "block_index": block_index,
        "block_hash": &block_hash,
        "merkle_root": &merkle_root,
        "digest_hex": &digest_hex,
        "calendar_url": &accepted_by,
        "proof_b64": &proof_b64,
        "proof_size": dtf.len() as i64,
        "btc_attested": btc_attested,
        "via": "lattice-gateway-rust",
    }).await;

    Ok(Json(serde_json::json!({
        "ok": true,
        "anchor": {
            "anchor_id": anchor_id,
            "created_at": ts_iso,
            "chain_id": chain_id,
            "block_index": block_index,
            "block_hash": block_hash,
            "merkle_root": merkle_root,
            "digest_hex": digest_hex,
            "calendar_url": accepted_by,
            "proof_size": dtf.len(),
            "btc_attested": btc_attested,
        }
    })))
}

// ---------------------------------------------------------------------------
// POST /api/admin/ots/upgrade/{anchor_id}
// ---------------------------------------------------------------------------

pub async fn ots_upgrade(
    State(state): State<AppState>,
    Path(anchor_id): Path<String>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<OtsError>)> {
    if !is_enabled() {
        return Err(err(StatusCode::SERVICE_UNAVAILABLE, "OpenTimestamps anchoring is disabled"));
    }
    let coll = state.db.collection::<Document>("ots_anchors");
    let doc = coll.find_one(doc! {"anchor_id": &anchor_id}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?
        .ok_or_else(|| err(StatusCode::NOT_FOUND, format!("anchor not found: {}", anchor_id)))?;
    let digest_hex = doc.get_str("digest_hex").unwrap_or("").to_string();
    let current_b64 = doc.get_str("proof_b64").unwrap_or("").to_string();
    let current_dtf = base64::engine::general_purpose::STANDARD.decode(&current_b64)
        .unwrap_or_default();
    // Decode the file digest from the stored DTF (or fall back to digest_hex).
    let digest_vec = hex::decode(&digest_hex).unwrap_or_default();
    let mut file_digest = [0u8; 32];
    if digest_vec.len() == 32 { file_digest.copy_from_slice(&digest_vec); }

    // Try each calendar — keep the largest timestamp body (more attestations).
    let mut best_ts: Vec<u8> = unwrap_dtf(&current_dtf).map(|s| s.to_vec()).unwrap_or(current_dtf.clone());
    let mut last_status = String::from("no calendar response");
    let mut upgraded = false;
    for url in calendars() {
        match fetch_upgrade(&state.http, &url, &digest_hex).await {
            Ok(b) => {
                if b.len() > best_ts.len() || (!has_btc_attestation(&best_ts) && has_btc_attestation(&b)) {
                    best_ts = b;
                    upgraded = true;
                }
                last_status = "ok".to_string();
            }
            Err(e) => { last_status = format!("{url}: {e}"); continue; }
        }
    }
    let dtf = wrap_dtf(&file_digest, &best_ts);
    let btc_attested = has_btc_attestation(&dtf);
    let new_b64 = base64::engine::general_purpose::STANDARD.encode(&dtf);
    let now = Utc::now().to_rfc3339();
    coll.update_one(
        doc! {"anchor_id": &anchor_id},
        doc! {"$set": {
            "proof_b64": &new_b64,
            "proof_size": dtf.len() as i64,
            "btc_attested": btc_attested,
            "last_upgrade_at": &now,
            "last_upgrade_status": if upgraded { "ok".to_string() } else { format!("pending ({})", last_status) },
        }},
    ).await.map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;

    Ok(Json(serde_json::json!({
        "ok": true,
        "anchor": {
            "anchor_id": anchor_id,
            "btc_attested": btc_attested,
            "proof_size": dtf.len(),
            "last_upgrade_at": now,
            "last_upgrade_status": if upgraded { "ok".to_string() } else { format!("pending ({})", last_status) },
        }
    })))
}

// ---------------------------------------------------------------------------
// POST /api/admin/ots/upgrade-all
// ---------------------------------------------------------------------------

pub async fn ots_upgrade_all(State(state): State<AppState>)
    -> Result<Json<serde_json::Value>, (StatusCode, Json<OtsError>)>
{
    if !is_enabled() {
        return Err(err(StatusCode::SERVICE_UNAVAILABLE, "OpenTimestamps anchoring is disabled"));
    }
    let coll = state.db.collection::<Document>("ots_anchors");
    use futures::StreamExt;
    let opts = mongodb::options::FindOptions::builder()
        .projection(doc! {"_id": 0, "anchor_id": 1}).build();
    let mut cur = coll.find(doc! {"btc_attested": false}).with_options(opts).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let mut pending = Vec::<String>::new();
    while let Some(d) = cur.next().await {
        if let Ok(d) = d {
            if let Ok(s) = d.get_str("anchor_id") { pending.push(s.to_string()); }
        }
    }

    let mut results = Vec::<serde_json::Value>::new();
    let mut promoted = 0_i64;
    for anchor_id in &pending {
        match ots_upgrade(State(state.clone()), Path(anchor_id.clone())).await {
            Ok(j) => {
                let v = j.0;
                let is_btc = v["anchor"]["btc_attested"].as_bool().unwrap_or(false);
                if is_btc { promoted += 1; }
                results.push(serde_json::json!({
                    "anchor_id": anchor_id,
                    "btc_attested": is_btc,
                    "status": v["anchor"]["last_upgrade_status"].clone(),
                }));
            }
            Err((_, e)) => {
                results.push(serde_json::json!({"anchor_id": anchor_id, "error": e.0.detail}));
            }
        }
    }
    Ok(Json(serde_json::json!({
        "ok": true, "pending": pending.len(), "promoted": promoted, "results": results,
    })))
}

// ---------------------------------------------------------------------------
// GET /api/admin/ots/anchors/{anchor_id}/proof
// ---------------------------------------------------------------------------

pub async fn ots_proof_download(
    State(state): State<AppState>,
    Path(anchor_id): Path<String>,
) -> Result<Response, (StatusCode, Json<OtsError>)> {
    let doc = state.db.collection::<Document>("ots_anchors")
        .find_one(doc! {"anchor_id": &anchor_id}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?
        .ok_or_else(|| err(StatusCode::NOT_FOUND, format!("anchor not found: {}", anchor_id)))?;
    let b64 = doc.get_str("proof_b64")
        .map_err(|_| err(StatusCode::INTERNAL_SERVER_ERROR, "missing proof_b64"))?;
    let bytes = base64::engine::general_purpose::STANDARD.decode(b64)
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("b64: {e}")))?;
    let body = axum::body::Bytes::from(bytes);
    let mut resp = (StatusCode::OK, body).into_response();
    resp.headers_mut().insert(header::CONTENT_TYPE, "application/octet-stream".parse().unwrap());
    resp.headers_mut().insert(header::CONTENT_DISPOSITION,
        format!("attachment; filename=\"{}.ots\"", anchor_id).parse().unwrap());
    Ok(resp)
}
