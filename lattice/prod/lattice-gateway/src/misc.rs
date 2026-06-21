//! M8 — Bulk port of Python-only read-only endpoints (~14 endpoints).
//!
//!   GET  /api/me                          — JWT introspection
//!   GET  /api/pqc/info                    — static PQC config
//!   GET  /api/rust/info                   — Rust bridge (live SHA3-512 proof)
//!   GET  /api/rust/selftest               — ML-DSA-65 round-trip in Rust
//!   GET  /api/keystore/{entity}           — public key lookup
//!   GET  /api/ledger/verify/{tx_id}       — ML-DSA-65 signature verify
//!   GET  /api/audit/public/{slug}         — tenant public audit page
//!   GET  /api/pulse/conversations         — conv list (scoped to caller)
//!   GET  /api/pulse/messages              — message history (+ delivered/read auto-mark)
//!   GET  /api/tenants                     — admin tenant listing
//!   GET  /api/tenants/{id}/employees      — tenant employees
//!   GET  /api/tenants/{id}/stats          — tenant KPIs
//!   GET  /api/lns                         — directory listing (tenant-scoped)
//!   GET  /api/lns/check                   — uniqueness probe
//!   GET  /api/lns/{lns}/enc-key           — X25519 enc public key
//!
//! JWT decode helper (`current_user`) embedded — reads `Authorization:
//! Bearer …` JWT (HS256) and returns `{sub, tenant_id, role}`.

use std::env;

use axum::{
    extract::{Path, Query, State},
    http::{HeaderMap, StatusCode},
    Json,
};
use bson::{doc, Document};
use chrono::{SecondsFormat, Utc};
use futures::StreamExt;
use jsonwebtoken::{decode, DecodingKey, Validation};
use mongodb::options::FindOptions;
use pqcrypto_mldsa::mldsa65;
use pqcrypto_traits::sign::{DetachedSignature as _, PublicKey as _, SecretKey as _};
use rand::RngCore;
use serde::{Deserialize, Serialize};
use sha3::{Digest, Sha3_256, Sha3_512};

use crate::chain::tx_canonical_message;
use crate::crypto::pqc_verify;
use crate::AppState;

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct JwtClaims {
    #[serde(default)] pub sub: Option<String>,
    #[serde(default)] pub tenant_id: Option<String>,
    #[serde(default)] pub role: Option<String>,
    #[serde(default)] pub iat: Option<i64>,
    #[serde(default)] pub exp: Option<i64>,
    #[serde(default)] pub jti: Option<String>,
    #[serde(default)] pub iss: Option<String>,
}

pub fn jwt_decode(headers: &HeaderMap) -> Option<JwtClaims> {
    let token = headers.get(axum::http::header::AUTHORIZATION)?.to_str().ok()?;
    let token = token.strip_prefix("Bearer ")?;
    let secret = env::var("LATTICE_JWT_SECRET").unwrap_or_else(|_| "lattice-dev-secret".into());
    let mut validation = Validation::new(jsonwebtoken::Algorithm::HS256);
    validation.required_spec_claims.clear();
    validation.validate_exp = false;
    let key = DecodingKey::from_secret(secret.as_bytes());
    decode::<JwtClaims>(token, &key, &validation).ok().map(|d| d.claims)
}

#[derive(Debug, Serialize)]
pub struct MiscError { pub detail: String }
fn err(code: StatusCode, msg: impl Into<String>) -> (StatusCode, Json<MiscError>) {
    (code, Json(MiscError { detail: msg.into() }))
}

fn utc_iso() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Micros, true)
}

// ===========================================================================
// GET /api/me
// ===========================================================================

pub async fn me(State(state): State<AppState>, headers: HeaderMap)
    -> Result<Json<serde_json::Value>, (StatusCode, Json<MiscError>)>
{
    let claims = jwt_decode(&headers);
    let role = headers.get("x-lattice-role").and_then(|v| v.to_str().ok())
        .map(|s| s.to_string())
        .or_else(|| claims.as_ref().and_then(|c| c.role.clone()))
        .unwrap_or_else(|| "sovereign".to_string());
    let lns = claims.as_ref().and_then(|c| c.sub.clone());
    let tenant_id = claims.as_ref().and_then(|c| c.tenant_id.clone());

    let mut payload = serde_json::json!({
        "lns": lns,
        "role": role,
        "tenant_id": tenant_id,
        "permissions": {
            "list_lns": role == "sovereign" || role == "auditor",
            "register_lns": role == "sovereign",
            "send_pulse": role == "sovereign",
            "send_certify": role == "sovereign",
            "view_plaintext": role == "sovereign",
        },
    });
    if let Some(lns) = payload.get("lns").and_then(|v| v.as_str()) {
        if let Ok(Some(d)) = state.db.collection::<Document>("lns")
            .find_one(doc! {"lns_name": lns}).await
        {
            payload["lns_status"] = serde_json::json!(d.get_str("status").unwrap_or("ACTIVE"));
            payload["tenant_id"] = serde_json::json!(d.get_str("tenant_id").unwrap_or(""));
        }
    }
    Ok(Json(payload))
}

// ===========================================================================
// GET /api/pqc/info
// ===========================================================================

pub async fn pqc_info() -> Json<serde_json::Value> {
    Json(serde_json::json!({
        "algorithm": "ML-DSA-65",
        "standard": "NIST FIPS 204 (ML-DSA-65, formerly Dilithium3)",
        "public_key_size_bytes": 1952,
        "secret_key_size_bytes": 4032,
        "signature_size_bytes": 3309,
        "kem_for_pulse": "ML-KEM-768 (NIST FIPS 203, formerly Kyber-768)",
        "implementation": "pqcrypto-mldsa 0.1 (Rust native)",
        "live": true,
    }))
}

// ===========================================================================
// GET /api/rust/info + /api/rust/selftest
// ===========================================================================

pub async fn rust_info() -> Json<serde_json::Value> {
    let sample = b"lattice.rust.bridge.proof";
    let mut h = Sha3_512::new();
    Digest::update(&mut h, sample);
    let hash_hex = hex::encode(h.finalize());
    Json(serde_json::json!({
        "available": true,
        "version": "lattice-gateway 0.30 · Rust native",
        "binding": "Pure Rust binary (no PyO3)",
        "crate": "lattice-crypto (BSL 1.1) — direct in-process",
        "exposes": [
            "sha3_512_hex(bytes) -> str",
            "sha3_256_hex(bytes) -> str",
            "fingerprint_pubkey(bytes) -> str",
            "ml_dsa_65_keypair() -> (pk, sk)",
            "ml_dsa_65_sign(sk, msg) -> sig",
            "ml_dsa_65_verify(pk, msg, sig) -> bool",
        ],
        "proof": {
            "input_utf8": String::from_utf8_lossy(sample).to_string(),
            "sha3_512_rust_hex": hash_hex,
            "computed_by": "Rust crate `sha3 0.10` in-process",
        },
    }))
}

pub async fn rust_selftest() -> Json<serde_json::Value> {
    let mut nonce = [0u8; 48];
    rand::rngs::OsRng.fill_bytes(&mut nonce);
    let (pk, sk) = mldsa65::keypair();
    let sig = mldsa65::detached_sign(&nonce, &sk);
    let ok = mldsa65::verify_detached_signature(&sig, &nonce, &pk).is_ok();
    let pk_bytes = pk.as_bytes();
    let sk_bytes = sk.as_bytes();
    let sig_bytes = sig.as_bytes();
    let mut fh = Sha3_256::new();
    Digest::update(&mut fh, pk_bytes);
    let fp: String = hex::encode(fh.finalize())[..32].to_uppercase();
    Json(serde_json::json!({
        "algorithm": "ML-DSA-65 · NIST FIPS 204",
        "computed_in": "Rust native (lattice-gateway in-process)",
        "public_key_bytes": pk_bytes.len(),
        "secret_key_bytes": sk_bytes.len(),
        "signature_bytes": sig_bytes.len(),
        "nonce_hex": hex::encode(nonce),
        "signature_first_32_hex": hex::encode(&sig_bytes[..32]),
        "fingerprint": fp,
        "verify_ok": ok,
    }))
}

// ===========================================================================
// GET /api/keystore/{entity}
// ===========================================================================

pub async fn keystore_get(
    State(state): State<AppState>,
    Path(entity): Path<String>,
    headers: HeaderMap,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<MiscError>)> {
    let doc = state.db.collection::<Document>("keystore")
        .find_one(doc! {"entity": &entity}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?
        .ok_or_else(|| err(StatusCode::NOT_FOUND, format!("no key on file for entity: {entity}")))?;

    // Cross-tenant guard: tenant users can only see their own colleagues + infra.
    if let Some(c) = jwt_decode(&headers) {
        if let Some(caller_tenant) = c.tenant_id.as_deref().filter(|s| !s.is_empty()) {
            let is_infra = entity.starts_with("VAL-") || entity.starts_with("OBS-")
                || entity.starts_with("MIX-") || entity.starts_with("GENESIS");
            if !is_infra {
                let lns_doc = state.db.collection::<Document>("lns")
                    .find_one(doc! {"lns_name": &entity}).await
                    .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
                let same = lns_doc.as_ref()
                    .and_then(|d| d.get_str("tenant_id").ok())
                    .map(|t| t == caller_tenant)
                    .unwrap_or(false);
                if !same {
                    return Err(err(StatusCode::FORBIDDEN,
                        "cross-company key lookup forbidden · puoi vedere solo le chiavi della tua azienda"));
                }
            }
        }
    }
    let pk_hex = doc.get_str("pk_hex").unwrap_or("").to_string();
    Ok(Json(serde_json::json!({
        "entity": entity,
        "role": doc.get_str("role").unwrap_or("lns"),
        "algorithm": "ML-DSA-65",
        "public_key_hex": &pk_hex,
        "public_key_size_bytes": pk_hex.len() / 2,
        "fingerprint": doc.get_str("fingerprint").unwrap_or(""),
        "created_at": doc.get_str("created_at").unwrap_or(""),
    })))
}

// ===========================================================================
// GET /api/ledger/verify/{tx_id}
// ===========================================================================

pub async fn ledger_verify(
    State(state): State<AppState>,
    Path(tx_id): Path<String>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<MiscError>)> {
    let tx = state.db.collection::<Document>("transactions")
        .find_one(doc! {"tx_id": &tx_id}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?
        .ok_or_else(|| err(StatusCode::NOT_FOUND, format!("transaction not found: {}", tx_id)))?;
    let block_index = tx.get_i64("block_index")
        .or_else(|_| tx.get_i32("block_index").map(|v| v as i64))
        .unwrap_or(0);
    let timestamp = tx.get_str("timestamp").unwrap_or("").to_string();
    let kind = tx.get_str("kind").unwrap_or("").to_string();
    let summary = tx.get_str("summary").unwrap_or("").to_string();
    let signed_with = tx.get_str("signed_with").unwrap_or("legacy-seed").to_string();
    let msg = tx_canonical_message(&tx_id, block_index, &timestamp, &kind, &summary);

    if signed_with != "ML-DSA-65" {
        return Ok(Json(serde_json::json!({
            "ok": false, "tx_id": tx_id, "algorithm": "ML-DSA-65",
            "signed_with": signed_with,
            "public_key_size_bytes": 1952, "signature_size_bytes": 3309,
            "message_hex": hex::encode(&msg),
            "detail": "Seeded transaction — signed with deterministic placeholder, not real PQC. New transactions emitted after upgrade are signed with NIST FIPS 204 ML-DSA-65 and verifiable.",
        })));
    }
    let signer = tx.get_str("signer_entity").unwrap_or("").to_string();
    let sig = tx.get_str("signature").unwrap_or("").to_string();
    let ok = pqc_verify(&state.db, &signer, &msg, &sig).await;
    Ok(Json(serde_json::json!({
        "ok": ok, "tx_id": tx_id, "algorithm": "ML-DSA-65",
        "signed_with": signed_with, "signer_entity": signer,
        "public_key_fingerprint": tx.get_str("sender_public_key").unwrap_or(""),
        "public_key_size_bytes": 1952, "signature_size_bytes": 3309,
        "message_hex": hex::encode(&msg),
        "detail": if ok { "Signature verified against signer's persisted public key." }
                  else { "Signature DID NOT verify — bytes have been tampered or signer key rotated." },
    })))
}

// ===========================================================================
// GET /api/audit/public/{slug}
// ===========================================================================

pub async fn audit_public(
    State(state): State<AppState>,
    Path(slug): Path<String>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<MiscError>)> {
    let coll = state.db.collection::<Document>("tenants");
    // Try by tenant_id first
    let mut tenant = coll.find_one(doc! {"tenant_id": &slug}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    if tenant.is_none() {
        // Try by domain prefix.
        let pat = format!("^{}\\.?", regex::escape(&slug));
        tenant = coll.find_one(doc! {"domain": {"$regex": &pat, "$options": "i"}}).await
            .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    }
    if tenant.is_none() {
        // Match by domain prefix split.
        let mut cur = coll.find(doc! {}).await
            .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
        while let Some(d) = cur.next().await {
            if let Ok(d) = d {
                if let Ok(dom) = d.get_str("domain") {
                    if dom.split('.').next().map(|s| s.eq_ignore_ascii_case(&slug)).unwrap_or(false) {
                        tenant = Some(d); break;
                    }
                }
            }
        }
    }
    let tenant = tenant.ok_or_else(|| err(StatusCode::NOT_FOUND,
        format!("no tenant matches slug '{}'", slug)))?;
    let tid = tenant.get_str("tenant_id").unwrap_or("").to_string();
    let domain = tenant.get_str("domain").unwrap_or("").to_string();
    let name = tenant.get_str("name").unwrap_or("").to_string();
    let created_at = tenant.get_str("created_at").unwrap_or("").to_string();

    let employees = state.db.collection::<Document>("lns")
        .count_documents(doc! {"tenant_id": &tid}).await.unwrap_or(0);
    let tx_pat = format!("\\.{}$", regex::escape(&domain));
    let tx_total = state.db.collection::<Document>("transactions")
        .count_documents(doc! {"signer_entity": {"$regex": &tx_pat}}).await.unwrap_or(0);

    let mut recent = Vec::new();
    if !domain.is_empty() {
        let opts = FindOptions::builder()
            .sort(doc! {"block_index": -1}).limit(10).projection(doc! {"_id": 0,
                "tx_id":1, "block_index":1, "kind":1, "timestamp":1, "doc_hash":1,
                "signer_entity":1, "signed_with":1}).build();
        if let Ok(mut cur) = state.db.collection::<Document>("transactions")
            .find(doc! {"signer_entity": {"$regex": &tx_pat}}).with_options(opts).await
        {
            while let Some(d) = cur.next().await {
                if let Ok(d) = d {
                    let doc_hash = d.get_str("doc_hash").unwrap_or("").to_string();
                    let signer = d.get_str("signer_entity").unwrap_or("").to_string();
                    recent.push(serde_json::json!({
                        "tx_id": d.get_str("tx_id").unwrap_or(""),
                        "block_index": d.get_i64("block_index")
                            .or_else(|_| d.get_i32("block_index").map(|v| v as i64))
                            .unwrap_or(0),
                        "kind": d.get_str("kind").unwrap_or(""),
                        "timestamp": d.get_str("timestamp").unwrap_or(""),
                        "doc_hash_short": doc_hash.chars().take(16).collect::<String>(),
                        "signer_short": signer.split('.').next().unwrap_or(""),
                        "signed_with": d.get_str("signed_with").unwrap_or("—"),
                    }));
                }
            }
        }
    }
    let meta = state.db.collection::<Document>("meta")
        .find_one(doc! {"_id": "seeded"}).await.ok().flatten();
    let block_height = meta.as_ref().map(|d|
        d.get_i64("block_height").or_else(|_| d.get_i32("block_height").map(|v| v as i64))
        .or_else(|_| d.get_f64("block_height").map(|v| v as i64))
        .unwrap_or(0)
    ).unwrap_or(0);
    let chain_id = env::var("LATTICE_CHAIN_ID").unwrap_or_else(|_| "lattice-sovereign-it-prod".into());
    let tid_short = if tid.len() > 14 { format!("{}…", &tid[..14]) } else { tid.clone() };
    Ok(Json(serde_json::json!({
        "tenant": {
            "name": name, "domain": domain,
            "registered_at": created_at,
            "tenant_id_short": tid_short,
        },
        "footprint": {
            "employees": employees, "transactions_total": tx_total,
            "recent_transactions": recent,
        },
        "network": {
            "chain_id": chain_id,
            "block_height": block_height,
            "pqc_algorithm": "ML-DSA-65",
            "consensus": "QBFT · 2f+1 ML-DSA-65",
        },
        "checked_at": utc_iso(),
    })))
}

// ===========================================================================
// GET /api/pulse/conversations + /api/pulse/messages
// ===========================================================================

#[derive(Debug, Deserialize)]
pub struct ConvQuery {
    #[serde(default)] pub lns: Option<String>,
    #[serde(default = "default_limit50")] pub limit: i64,
}
fn default_limit50() -> i64 { 50 }
fn default_limit100() -> i64 { 100 }

pub async fn pulse_conversations(
    State(state): State<AppState>,
    Query(q): Query<ConvQuery>,
    headers: HeaderMap,
) -> Result<Json<Vec<Document>>, (StatusCode, Json<MiscError>)> {
    let claims = jwt_decode(&headers);
    let me_lns = claims.as_ref().and_then(|c| c.sub.clone());
    let mut filter = Document::new();
    if let Some(me) = me_lns.as_ref() { filter.insert("participants", me); }
    else if let Some(lns) = q.lns.as_ref() { filter.insert("participants", lns.to_lowercase()); }

    let lim = q.limit.clamp(1, 200);
    let opts = FindOptions::builder().sort(doc! {"last_message_at": -1})
        .limit(lim).projection(doc! {"_id": 0}).build();
    let mut cur = state.db.collection::<Document>("pulse_conversations")
        .find(filter).with_options(opts).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let mut out = Vec::new();
    while let Some(d) = cur.next().await { if let Ok(d) = d { out.push(d); } }
    Ok(Json(out))
}

#[derive(Debug, Deserialize)]
pub struct MsgQuery {
    pub conv_id: String,
    #[serde(default = "default_limit100")] pub limit: i64,
}

pub async fn pulse_messages(
    State(state): State<AppState>,
    Query(q): Query<MsgQuery>,
    headers: HeaderMap,
) -> Result<Json<Vec<Document>>, (StatusCode, Json<MiscError>)> {
    let claims = jwt_decode(&headers);
    let me_lns = claims.as_ref().and_then(|c| c.sub.clone());

    if let Some(me) = me_lns.as_ref() {
        let conv = state.db.collection::<Document>("pulse_conversations")
            .find_one(doc! {"conv_id": &q.conv_id})
            .projection(doc! {"_id": 0, "participants": 1})
            .await
            .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?
            .ok_or_else(|| err(StatusCode::NOT_FOUND, "conversation not found"))?;
        let participants: Vec<&str> = conv.get_array("participants")
            .map(|a| a.iter().filter_map(|b| b.as_str()).collect()).unwrap_or_default();
        if !participants.iter().any(|p| *p == me.as_str()) {
            return Err(err(StatusCode::FORBIDDEN, "you are not a participant of this conversation"));
        }
        let now = utc_iso();
        let _ = state.db.collection::<Document>("pulse_messages").update_many(
            doc! {"conv_id": &q.conv_id, "to_lns": me, "delivered_at": bson::Bson::Null},
            doc! {"$set": {"delivered_at": &now}},
        ).await;
        let _ = state.db.collection::<Document>("pulse_messages").update_many(
            doc! {"conv_id": &q.conv_id, "to_lns": me, "read_at": bson::Bson::Null},
            doc! {"$set": {"read_at": &now}},
        ).await;
    }

    let lim = q.limit.clamp(1, 500);
    let opts = FindOptions::builder().sort(doc! {"sealed_at": 1}).limit(lim)
        .projection(doc! {"_id": 0}).build();
    let mut cur = state.db.collection::<Document>("pulse_messages")
        .find(doc! {"conv_id": &q.conv_id}).with_options(opts).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let mut out = Vec::new();
    while let Some(d) = cur.next().await { if let Ok(d) = d { out.push(d); } }
    Ok(Json(out))
}

// ===========================================================================
// GET /api/tenants  + /api/tenants/{id}/employees + /api/tenants/{id}/stats
// ===========================================================================

pub async fn tenants_list(State(state): State<AppState>)
    -> Result<Json<Vec<Document>>, (StatusCode, Json<MiscError>)>
{
    let opts = FindOptions::builder().sort(doc! {"created_at": -1})
        .projection(doc! {"_id": 0}).build();
    let mut cur = state.db.collection::<Document>("tenants")
        .find(doc! {}).with_options(opts).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let mut out = Vec::new();
    while let Some(d) = cur.next().await { if let Ok(d) = d { out.push(d); } }
    Ok(Json(out))
}

pub async fn tenant_employees(
    State(state): State<AppState>,
    Path(tenant_id): Path<String>,
) -> Result<Json<Vec<Document>>, (StatusCode, Json<MiscError>)> {
    let opts = FindOptions::builder().sort(doc! {"lns_name": 1})
        .projection(doc! {"_id": 0}).build();
    let mut cur = state.db.collection::<Document>("lns")
        .find(doc! {"tenant_id": &tenant_id}).with_options(opts).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let mut out = Vec::new();
    while let Some(d) = cur.next().await { if let Ok(d) = d { out.push(d); } }
    Ok(Json(out))
}

pub async fn tenant_stats(
    State(state): State<AppState>,
    Path(tenant_id): Path<String>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<MiscError>)> {
    let tenant = state.db.collection::<Document>("tenants")
        .find_one(doc! {"tenant_id": &tenant_id}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?
        .ok_or_else(|| err(StatusCode::NOT_FOUND, "tenant not found"))?;
    let domain = tenant.get_str("domain").unwrap_or("").to_string();

    let employees_active = state.db.collection::<Document>("lns")
        .count_documents(doc! {"tenant_id": &tenant_id, "status": "ACTIVE"}).await.unwrap_or(0);
    let employees_revoked = state.db.collection::<Document>("lns")
        .count_documents(doc! {"tenant_id": &tenant_id, "status": "REVOKED"}).await.unwrap_or(0);
    let suffix = format!("\\.{}$", regex::escape(&domain));
    let certify_mails = state.db.collection::<Document>("certify_mails")
        .count_documents(doc! {"sender_lns": {"$regex": &suffix}}).await.unwrap_or(0);
    let pulse_msgs = state.db.collection::<Document>("pulse_messages")
        .count_documents(doc! {"from_lns": {"$regex": &suffix}}).await.unwrap_or(0);
    let tx_total = state.db.collection::<Document>("transactions")
        .count_documents(doc! {"signer_entity": {"$regex": &suffix}}).await.unwrap_or(0);

    // Roles breakdown via aggregation
    let mut roles = serde_json::Map::new();
    let pipeline = vec![
        doc! {"$match": {"tenant_id": &tenant_id}},
        doc! {"$group": {"_id": "$role", "count": {"$sum": 1}}},
    ];
    if let Ok(mut cur) = state.db.collection::<Document>("lns").aggregate(pipeline).await {
        while let Some(d) = cur.next().await {
            if let Ok(d) = d {
                let k = d.get_str("_id").unwrap_or("?").to_string();
                let c = d.get_i64("count").or_else(|_| d.get_i32("count").map(|v| v as i64)).unwrap_or(0);
                roles.insert(k, serde_json::json!(c));
            }
        }
    }
    Ok(Json(serde_json::json!({
        "tenant_id": tenant_id,
        "name": tenant.get_str("name").unwrap_or(""),
        "domain": domain,
        "employees_active": employees_active,
        "employees_revoked": employees_revoked,
        "certify_mails": certify_mails,
        "pulse_messages": pulse_msgs,
        "transactions_total": tx_total,
        "roles_breakdown": roles,
        "created_at": tenant.get_str("created_at").unwrap_or(""),
    })))
}

// ===========================================================================
// GET /api/lns  +  /api/lns/check  +  /api/lns/{lns}/enc-key
// ===========================================================================

#[derive(Debug, Deserialize)]
pub struct LnsListQuery {
    #[serde(default)] pub search: Option<String>,
    #[serde(default)] pub status: Option<String>,
    #[serde(default = "default_limit_lns")] pub limit: i64,
}
fn default_limit_lns() -> i64 { 500 }

pub async fn lns_list(
    State(state): State<AppState>,
    Query(q): Query<LnsListQuery>,
    headers: HeaderMap,
) -> Result<Json<Vec<Document>>, (StatusCode, Json<MiscError>)> {
    let mut filter = Document::new();
    if let Some(s) = q.status.as_ref() { filter.insert("status", s); }
    if let Some(s) = q.search.as_ref().filter(|s| !s.is_empty()) {
        filter.insert("lns_name", doc! {"$regex": regex::escape(&s.to_lowercase())});
    }
    // Tenant scoping via JWT
    let claims = jwt_decode(&headers);
    if let Some(tid) = claims.and_then(|c| c.tenant_id).filter(|s| !s.is_empty()) {
        filter.insert("tenant_id", tid);
    }
    let opts = FindOptions::builder().sort(doc! {"lns_name": 1})
        .limit(q.limit.clamp(1, 5000)).projection(doc! {"_id": 0}).build();
    let mut cur = state.db.collection::<Document>("lns")
        .find(filter).with_options(opts).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let mut out = Vec::new();
    while let Some(d) = cur.next().await { if let Ok(d) = d { out.push(d); } }
    Ok(Json(out))
}

#[derive(Debug, Deserialize)]
pub struct LnsCheckQuery { pub lns_name: String }

pub async fn lns_check(
    State(state): State<AppState>,
    Query(q): Query<LnsCheckQuery>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<MiscError>)> {
    let name = q.lns_name.trim().to_lowercase();
    if name.is_empty() {
        return Err(err(StatusCode::UNPROCESSABLE_ENTITY, "lns_name required"));
    }
    let exists = state.db.collection::<Document>("lns")
        .count_documents(doc! {"lns_name": &name}).await.unwrap_or(0) > 0;
    Ok(Json(serde_json::json!({"lns_name": name, "available": !exists, "exists": exists})))
}

pub async fn lns_enc_key(
    State(state): State<AppState>,
    Path(lns_name): Path<String>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<MiscError>)> {
    let doc = state.db.collection::<Document>("lns")
        .find_one(doc! {"lns_name": lns_name.to_lowercase()}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?
        .ok_or_else(|| err(StatusCode::NOT_FOUND, format!("LNS not found: {}", lns_name)))?;
    let enc_pk = doc.get_str("enc_public_key_hex").unwrap_or("");
    if enc_pk.is_empty() {
        return Err(err(StatusCode::NOT_FOUND, "enc_public_key_hex not set for this LNS"));
    }
    Ok(Json(serde_json::json!({
        "lns_name": lns_name, "enc_public_key_hex": enc_pk,
        "algorithm": "X25519",
    })))
}
