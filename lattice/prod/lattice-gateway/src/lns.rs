//! POST /api/lns/register — native Rust port of `server.py::register_lns`.
//!
//! Server-side ML-DSA-65 keypair generation, IdentityRegister TX
//! notarised on-chain through QBFT consensus.
//!
//! NOTE — this is the M5 spike implementation. It covers the common
//! sovereign-mode path (server materialises the keypair). The
//! client-managed key path (req.public_key_hex set, WASM-generated PK)
//! is delegated back to the Python sidecar for now.

use axum::{extract::State, http::StatusCode, Json};
use bson::{doc, Document};
use serde::{Deserialize, Serialize};
use tracing::warn;

use crate::chain;
use crate::chain::utc_iso;
use crate::crypto::{det_hex, pqc_sign};
use crate::AppState;

#[derive(Debug, Deserialize, Serialize)]
pub struct LnsRegisterRequest {
    pub lns_name: String,
    #[serde(default)]
    pub department: Option<String>,
    #[serde(default)]
    pub admin: Option<String>,
    #[serde(default)]
    pub display_name: Option<String>,
    #[serde(default)]
    pub tenant_id: Option<String>,
    #[serde(default = "default_role")]
    pub role: String,
    /// If set, the server stores only the public key. Falls back to
    /// Python for now (not yet implemented in Rust).
    #[serde(default)]
    pub public_key_hex: Option<String>,
    #[serde(default)]
    pub enc_public_key_hex: Option<String>,
}

fn default_role() -> String {
    "lns".to_string()
}

#[derive(Debug, Serialize, Deserialize)]
pub struct LnsRegisterResponse {
    pub ok: bool,
    pub lns_name: String,
    pub did: String,
    pub public_key_fingerprint: String,
    pub tx_id: String,
    pub block_index: i64,
    pub registered_at: String,
    pub status: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub public_key_hex: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub secret_key_hex: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct LnsError {
    pub detail: String,
}

fn err(code: StatusCode, msg: impl Into<String>) -> (StatusCode, Json<LnsError>) {
    (code, Json(LnsError { detail: msg.into() }))
}

/// Validate the LNS name + resolve / detect tenant.
async fn resolve_tenant(
    db: &mongodb::Database,
    name: &str,
    requested_tenant_id: Option<&str>,
) -> Result<(Option<String>, Option<Document>), (StatusCode, Json<LnsError>)> {
    if let Some(tid) = requested_tenant_id {
        let tenant = db
            .collection::<Document>("tenants")
            .find_one(doc! {"tenant_id": tid})
            .await
            .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
        let tenant = tenant.ok_or_else(|| err(
            StatusCode::NOT_FOUND,
            format!("tenant not found: {tid}"),
        ))?;
        let domain = tenant.get_str("domain").unwrap_or("");
        if !name.ends_with(&format!(".{}", domain)) {
            return Err(err(
                StatusCode::UNPROCESSABLE_ENTITY,
                format!("lns_name must end with .{} for tenant {}", domain, tid),
            ));
        }
        return Ok((Some(tid.to_string()), Some(tenant)));
    }
    use futures::StreamExt;
    let mut cur = db
        .collection::<Document>("tenants")
        .find(doc! {})
        .projection(doc! {"_id": 0, "tenant_id": 1, "domain": 1})
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    while let Some(t) = cur.next().await {
        let t = t.map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
        let domain = t.get_str("domain").unwrap_or("");
        if name.ends_with(&format!(".{}", domain)) {
            return Ok((Some(t.get_str("tenant_id").unwrap_or("").to_string()), Some(t)));
        }
    }
    Err(err(
        StatusCode::UNPROCESSABLE_ENTITY,
        "lns_name must end with .<azienda> where <azienda> is a registered tenant domain",
    ))
}

pub async fn register_lns(
    State(state): State<AppState>,
    Json(req): Json<LnsRegisterRequest>,
) -> Result<Json<LnsRegisterResponse>, (StatusCode, Json<LnsError>)> {
    // ------------- validation -------------
    let name = req.lns_name.trim().to_lowercase();
    if name.len() < 3 {
        return Err(err(StatusCode::UNPROCESSABLE_ENTITY, "lns_name too short"));
    }
    if !name.chars().all(|c| c.is_alphanumeric() || ".-_".contains(c)) {
        return Err(err(
            StatusCode::UNPROCESSABLE_ENTITY,
            "lns_name contains forbidden characters",
        ));
    }

    // Client-managed PK path → delegate to Python sidecar for now.
    if req.public_key_hex.is_some() {
        warn!(lns = %name, "client-managed PK path not yet in Rust, forwarding to Python");
        let py_url = std::env::var("LATTICE_PY_FALLBACK")
            .unwrap_or_else(|_| "http://127.0.0.1:8001".to_string());
        let url = format!("{}/api/lns/register", py_url);
        let body = serde_json::to_value(&req).unwrap();
        match state.http.post(&url).json(&body).send().await {
            Ok(resp) => {
                let status = resp.status();
                let bytes = resp.bytes().await.unwrap_or_default();
                if let Ok(parsed) = serde_json::from_slice::<LnsRegisterResponse>(&bytes) {
                    return Ok(Json(parsed));
                }
                let detail = String::from_utf8_lossy(&bytes).into_owned();
                return Err(err(status, detail));
            }
            Err(e) => return Err(err(StatusCode::BAD_GATEWAY, format!("python fallback: {e}"))),
        }
    }

    // Resolve tenant.
    let (tenant_id, _tenant_doc) = resolve_tenant(&state.db, &name, req.tenant_id.as_deref()).await?;

    // Uniqueness.
    let existing = state.db.collection::<Document>("lns")
        .find_one(doc! {"lns_name": &name})
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    if existing.is_some() {
        return Err(err(StatusCode::CONFLICT, format!("Identity already registered: {}", name)));
    }

    let ts = utc_iso();

    // ------------- atomic on-chain notarisation -------------
    let _guard = chain::BLOCK_LOCK.lock().await;
    let new_block_index = chain::peek_next_block_index(&state.db)
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("peek index: {e}")))?;

    // Bump legacy meta counters (best-effort).
    let _ = state.db.collection::<Document>("meta")
        .update_one(
            doc! {"_id": "seeded"},
            doc! {"$inc": {"block_height": 1_i64, "tx_total": 1_i64, "qbft_round": 1_i64}},
        )
        .upsert(true)
        .await;

    // Generate server-side keypair (will be returned to the caller exactly once).
    use pqcrypto_mldsa::mldsa65;
    use pqcrypto_traits::sign::{PublicKey as _, SecretKey as _};
    let (pk, sk) = mldsa65::keypair();
    let pk_bytes = pk.as_bytes().to_vec();
    let sk_bytes = sk.as_bytes().to_vec();
    let fp = {
        use sha3::{Digest, Sha3_256};
        let mut h = Sha3_256::new();
        h.update(&pk_bytes);
        let out = h.finalize();
        out[..16].iter().map(|b| format!("{:02X}", b)).collect::<String>()
    };
    let did = format!("did:lattice:{}", fp.to_lowercase());

    // Persist keypair in keystore (server-managed mode).
    state.db.collection::<Document>("keystore")
        .update_one(
            doc! {"entity": &name},
            doc! {"$set": {
                "entity": &name,
                "role": &req.role,
                "pk_hex": hex::encode(&pk_bytes),
                "sk_hex": hex::encode(&sk_bytes),
                "fingerprint": &fp,
                "created_at": &ts,
                "algorithm": "ML-DSA-65",
                "enc_pk_hex": req.enc_public_key_hex.clone().unwrap_or_default(),
            }},
        )
        .upsert(true)
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("keystore: {e}")))?;

    // Sign IdentityRegister TX.
    let department = req.department.clone().unwrap_or_default();
    let summary = format!(
        "IdentityRegister · {} · role={} · dept={}",
        name, req.role, department
    );
    let tx_id = format!("tx-{}", det_hex(&format!("register-{}-{}", name, ts), 12));
    let tx_msg = chain::tx_canonical_message(&tx_id, new_block_index, &ts, "IdentityRegister", &summary);
    let sig = pqc_sign(&state.db, &name, &tx_msg, &req.role)
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("pqc_sign: {e}")))?;

    // Insert LNS record BEFORE the block so the block also covers the LNS.
    state.db.collection::<Document>("lns")
        .insert_one(doc! {
            "lns_name": &name,
            "did": &did,
            "public_key_fingerprint": &fp,
            "registered_at": &ts,
            "status": "ACTIVE",
            "department": &department,
            "display_name": req.display_name.clone().unwrap_or_default(),
            "tenant_id": tenant_id.clone().unwrap_or_default(),
            "role": &req.role,
        })
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("insert lns: {e}")))?;
    if let Some(tid) = &tenant_id {
        let _ = state.db.collection::<Document>("tenants")
            .update_one(
                doc! {"tenant_id": tid},
                doc! {"$inc": {"employees_count": 1_i64}},
            )
            .await;
    }

    // Finalise the block.
    let finalised = chain::finalise_block_for_tx_locked(
        &state.db, &state.http,
        &tx_id, "IdentityRegister", "", &name, &ts,
    )
    .await
    .map_err(|e| err(StatusCode::SERVICE_UNAVAILABLE, format!("qbft: {e}")))?;
    if finalised.index != new_block_index {
        return Err(err(StatusCode::INTERNAL_SERVER_ERROR,
            format!("block_index drift: signed={} alloc={}", new_block_index, finalised.index)));
    }

    // Persist the TX.
    state.db.collection::<Document>("transactions")
        .insert_one(doc! {
            "tx_id": &tx_id,
            "block_index": new_block_index,
            "timestamp": &ts,
            "kind": "IdentityRegister",
            "summary": &summary,
            "sender_public_key": &sig.fingerprint,
            "signature": &sig.signature_hex,
            "signed_with": "ML-DSA-65",
            "lns_name": &name,
        })
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("insert tx: {e}")))?;

    Ok(Json(LnsRegisterResponse {
        ok: true,
        lns_name: name,
        did,
        public_key_fingerprint: fp,
        tx_id,
        block_index: new_block_index,
        registered_at: ts,
        status: "ACTIVE".into(),
        public_key_hex: Some(hex::encode(&pk_bytes)),
        secret_key_hex: Some(hex::encode(&sk_bytes)),
    }))
}
