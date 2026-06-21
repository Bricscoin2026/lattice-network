//! Lattice QBFT validator — native Rust port of `backend/qbft_node.py`.
//!
//! Each validator runs as an independent OS process on its own TCP port.
//! It owns a real ML-DSA-65 (NIST FIPS 204) keypair and signs block
//! proposals broadcast by the lattice gateway. The aggregator collects
//! 2f+1 signatures before finalising a block — real Byzantine
//! fault-tolerant consensus over real network round-trips.
//!
//! Wire-compatible with the Python implementation:
//!   * Same MongoDB collections: `keystore`, `qbft_registry`,
//!     `qbft_votes_emitted`, `blocks`.
//!   * Same canonical block-message format (pipe-separated header fields).
//!   * Same SHA3-512 block-hash recomputation.
//!   * Same JSON wire format on `/health` and `/qbft/sign-block`.
//!
//! Run example:
//!   LATTICE_VAL_ID=VAL-01 LATTICE_VAL_PORT=9001 \
//!   MONGO_URL=mongodb://localhost:27017 DB_NAME=lattice \
//!   ./qbft-validator

use std::env;
use std::sync::Arc;

use anyhow::{anyhow, Context, Result};
use axum::{
    extract::State,
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use bson::doc;
use chrono::{SecondsFormat, Utc};
use mongodb::{options::ClientOptions, Client, Database};
use serde::{Deserialize, Serialize};
use tokio::net::TcpListener;
use tokio::sync::Mutex;
use tracing::{error, info};

use lattice_crypto::{compute_sha3_256, compute_sha3_512};
use pqcrypto_mldsa::mldsa65;
use pqcrypto_traits::sign::{
    DetachedSignature as _, PublicKey as DsaPublicKey, SecretKey as DsaSecretKey,
};

// -- module-internal helpers ------------------------------------------------

fn utc_iso() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Micros, true)
}

fn fingerprint(pk: &[u8]) -> String {
    let h = compute_sha3_256(pk);
    h[..16].iter().map(|b| format!("{:02X}", b)).collect::<Vec<_>>().join("")
}

// -- wire types --------------------------------------------------------------

#[derive(Debug, Deserialize)]
struct BlockProposal {
    index: i64,
    timestamp: String,
    previous_hash: String,
    block_hash: String,
    merkle_root: String,
    transactions_count: i64,
    chain_id: String,
}

#[derive(Debug, Serialize)]
struct SignedVote {
    validator_id: String,
    pk_fingerprint: String,
    signature_hex: String,
    signed_at: String,
    algorithm: String,
}

#[derive(Debug, Serialize)]
struct HealthResponse {
    ok: bool,
    validator_id: String,
    port: u16,
    pk_fingerprint: Option<String>,
    started_at: Option<String>,
    signed_total: u64,
    backend: &'static str,
}

#[derive(Debug, Serialize)]
struct ErrorResponse {
    detail: String,
}

// -- shared validator state --------------------------------------------------

#[derive(Clone)]
struct AppState {
    val_id: String,
    val_port: u16,
    chain_id: String,
    db: Database,
    inner: Arc<Mutex<InnerState>>,
}

#[derive(Default)]
struct InnerState {
    pk_bytes: Option<Vec<u8>>,
    sk_bytes: Option<Vec<u8>>,
    fingerprint: Option<String>,
    started_at: Option<String>,
    signed_total: u64,
}

// -- DB bootstrap ------------------------------------------------------------

async fn boot_key(state: &AppState) -> Result<()> {
    let keystore = state.db.collection::<bson::Document>("keystore");
    let qbft_registry = state.db.collection::<bson::Document>("qbft_registry");

    let doc = keystore
        .find_one(doc! {"entity": &state.val_id})
        .await
        .context("keystore lookup failed")?;

    // PQClean ML-DSA-65 byte sizes (NIST FIPS 204).
    const ML_DSA_65_PK_LEN: usize = 1952;
    const ML_DSA_65_SK_LEN: usize = 4032;

    let (pk_bytes, sk_bytes) = if let Some(d) = doc {
        let pk_hex = d.get_str("pk_hex").context("keystore.pk_hex missing")?;
        let sk_hex = d.get_str("sk_hex").context("keystore.sk_hex missing")?;
        let pk = hex::decode(pk_hex)?;
        let sk = hex::decode(sk_hex)?;
        // Migration safety: legacy keypairs in the DB might be Dilithium3
        // (pre-FIPS) with sk=4000 bytes instead of 4032. If sizes don't
        // match the ML-DSA-65 spec, regenerate a fresh keypair.
        if pk.len() == ML_DSA_65_PK_LEN && sk.len() == ML_DSA_65_SK_LEN {
            (pk, sk)
        } else {
            info!(
                pk_len = pk.len(),
                sk_len = sk.len(),
                "legacy keypair detected — regenerating ML-DSA-65 (NIST FIPS 204)"
            );
            let (pk_new, sk_new) = mldsa65::keypair();
            let pk_bytes = pk_new.as_bytes().to_vec();
            let sk_bytes = sk_new.as_bytes().to_vec();
            let fp = fingerprint(&pk_bytes);
            keystore
                .update_one(
                    doc! {"entity": &state.val_id},
                    doc! {"$set": {
                        "pk_hex": hex::encode(&pk_bytes),
                        "sk_hex": hex::encode(&sk_bytes),
                        "fingerprint": &fp,
                        "regenerated_at": utc_iso(),
                        "regenerated_reason": "size-mismatch-legacy-dilithium",
                    }},
                )
                .await?;
            (pk_bytes, sk_bytes)
        }
    } else {
        let (pk, sk) = mldsa65::keypair();
        let pk_bytes = pk.as_bytes().to_vec();
        let sk_bytes = sk.as_bytes().to_vec();
        let fp = fingerprint(&pk_bytes);
        keystore
            .insert_one(doc! {
                "entity": &state.val_id,
                "role": "validator",
                "pk_hex": hex::encode(&pk_bytes),
                "sk_hex": hex::encode(&sk_bytes),
                "fingerprint": &fp,
                "created_at": utc_iso(),
            })
            .await?;
        (pk_bytes, sk_bytes)
    };

    let fp = fingerprint(&pk_bytes);
    let now = utc_iso();

    // Publish liveness so the gateway can discover us.
    qbft_registry
        .update_one(
            doc! {"validator_id": &state.val_id},
            doc! {"$set": {
                "validator_id": &state.val_id,
                "port": state.val_port as i32,
                "endpoint": format!("http://127.0.0.1:{}", state.val_port),
                "pk_fingerprint": &fp,
                "boot_at": &now,
                "last_seen": &now,
                "signed_total": 0_i64,
                "backend": "rust",
            }},
        )
        .upsert(true)
        .await?;

    {
        let mut g = state.inner.lock().await;
        g.pk_bytes = Some(pk_bytes);
        g.sk_bytes = Some(sk_bytes);
        g.fingerprint = Some(fp);
        g.started_at = Some(now);
    }
    Ok(())
}

// -- validation logic --------------------------------------------------------

fn expected_block_hash(p: &BlockProposal) -> String {
    let payload = format!(
        "{}|{}|{}|{}|{}|{}",
        p.chain_id, p.index, p.timestamp, p.previous_hash, p.merkle_root, p.transactions_count
    );
    let h = compute_sha3_512(payload.as_bytes());
    hex::encode(h)
}

fn canonical_message(p: &BlockProposal) -> Vec<u8> {
    format!(
        "{}|{}|{}|{}|{}|{}|{}",
        p.chain_id,
        p.index,
        p.timestamp,
        p.previous_hash,
        p.merkle_root,
        p.transactions_count,
        p.block_hash,
    )
    .into_bytes()
}

async fn is_well_formed(state: &AppState, p: &BlockProposal) -> Result<(), String> {
    if p.index < 0 {
        return Err("index < 0".into());
    }
    if p.chain_id != state.chain_id {
        return Err(format!("chain_id mismatch (expected {})", state.chain_id));
    }
    if p.block_hash.len() != 128 {
        return Err("block_hash length != 128 hex chars (SHA3-512)".into());
    }
    if p.previous_hash.len() != 128 {
        return Err("previous_hash length != 128 hex chars".into());
    }
    if p.merkle_root.len() != 64 {
        return Err("merkle_root length != 64 hex chars (SHA3-256)".into());
    }
    if p.block_hash != expected_block_hash(p) {
        return Err("block_hash does not match recomputed header hash".into());
    }

    // Chain integrity.
    let blocks = state.db.collection::<bson::Document>("blocks");
    let last = blocks
        .find_one(doc! {})
        .sort(doc! {"index": -1})
        .projection(doc! {"_id": 0, "block_hash": 1, "index": 1})
        .await
        .map_err(|e| format!("db error: {e}"))?;

    match last {
        None => {
            if p.previous_hash != "0".repeat(128) {
                return Err("expected genesis previous_hash but DB has no last block".into());
            }
            if p.index != 1 {
                return Err("expected index=1 for first non-genesis block".into());
            }
        }
        Some(l) => {
            let last_hash = l.get_str("block_hash").unwrap_or("");
            let last_index = l.get_i64("index").unwrap_or(-1);
            if p.previous_hash != last_hash {
                return Err("previous_hash != DB last block hash (chain reorg attempt?)".into());
            }
            if p.index <= last_index {
                return Err(format!(
                    "index {} must be strictly greater than last ({})",
                    p.index, last_index
                ));
            }
        }
    }

    // Anti-equivocation.
    let votes = state.db.collection::<bson::Document>("qbft_votes_emitted");
    let prior = votes
        .find_one(doc! {"validator_id": &state.val_id, "index": p.index})
        .projection(doc! {"_id": 0, "block_hash": 1})
        .await
        .map_err(|e| format!("db error: {e}"))?;

    if let Some(pr) = prior {
        let prior_hash = pr.get_str("block_hash").unwrap_or("");
        if prior_hash != p.block_hash {
            return Err(format!(
                "equivocation refused: already signed a different block at index {}",
                p.index
            ));
        }
    }

    Ok(())
}

// -- HTTP handlers -----------------------------------------------------------

async fn health(State(state): State<AppState>) -> Json<HealthResponse> {
    let g = state.inner.lock().await;
    Json(HealthResponse {
        ok: true,
        validator_id: state.val_id.clone(),
        port: state.val_port,
        pk_fingerprint: g.fingerprint.clone(),
        started_at: g.started_at.clone(),
        signed_total: g.signed_total,
        backend: "rust",
    })
}

async fn sign_block(
    State(state): State<AppState>,
    Json(proposal): Json<BlockProposal>,
) -> Result<Json<SignedVote>, (StatusCode, Json<ErrorResponse>)> {
    if let Err(reason) = is_well_formed(&state, &proposal).await {
        return Err((
            StatusCode::BAD_REQUEST,
            Json(ErrorResponse {
                detail: format!("malformed block proposal: {reason}"),
            }),
        ));
    }

    let (signature, fp, signed_total) = {
        let mut g = state.inner.lock().await;
        let sk_bytes = g.sk_bytes.clone().ok_or((
            StatusCode::SERVICE_UNAVAILABLE,
            Json(ErrorResponse {
                detail: "validator key not initialised".into(),
            }),
        ))?;
        let sk = mldsa65::SecretKey::from_bytes(&sk_bytes).map_err(|_| (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse { detail: "invalid sk bytes in keystore".into() }),
        ))?;
        let msg = canonical_message(&proposal);
        let sig = mldsa65::detached_sign(&msg, &sk);
        let sig_bytes = sig.as_bytes().to_vec();
        g.signed_total += 1;
        (sig_bytes, g.fingerprint.clone().unwrap_or_default(), g.signed_total)
    };

    let ts = utc_iso();
    let votes = state.db.collection::<bson::Document>("qbft_votes_emitted");
    votes
        .update_one(
            doc! {"validator_id": &state.val_id, "index": proposal.index},
            doc! {"$set": {
                "validator_id": &state.val_id,
                "index": proposal.index,
                "block_hash": &proposal.block_hash,
                "signed_at": &ts,
            }},
        )
        .upsert(true)
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse {
                    detail: format!("persisting vote failed: {e}"),
                }),
            )
        })?;

    let registry = state.db.collection::<bson::Document>("qbft_registry");
    let _ = registry
        .update_one(
            doc! {"validator_id": &state.val_id},
            doc! {"$set": {"last_seen": &ts, "signed_total": signed_total as i64}},
        )
        .await;

    Ok(Json(SignedVote {
        validator_id: state.val_id.clone(),
        pk_fingerprint: fp,
        signature_hex: hex::encode(signature),
        signed_at: ts,
        algorithm: "ML-DSA-65".into(),
    }))
}

// ----------------------------------------------------------------------------

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
        .compact()
        .init();

    let val_id = env::var("LATTICE_VAL_ID").unwrap_or_else(|_| "VAL-XX".into());
    let val_port: u16 = env::var("LATTICE_VAL_PORT")
        .unwrap_or_else(|_| "9001".into())
        .parse()
        .context("invalid LATTICE_VAL_PORT")?;
    let chain_id =
        env::var("LATTICE_CHAIN_ID").unwrap_or_else(|_| "lattice-sovereign-it-prod".into());
    let mongo_url = env::var("MONGO_URL").context("MONGO_URL not set")?;
    let db_name = env::var("DB_NAME").context("DB_NAME not set")?;

    let opts = ClientOptions::parse(&mongo_url).await?;
    let client = Client::with_options(opts)?;
    let db = client.database(&db_name);

    let state = AppState {
        val_id: val_id.clone(),
        val_port,
        chain_id,
        db,
        inner: Arc::new(Mutex::new(InnerState::default())),
    };

    boot_key(&state)
        .await
        .map_err(|e| anyhow!("validator boot_key failed: {e}"))?;
    info!(
        validator = %val_id,
        port = val_port,
        "Lattice QBFT validator (Rust native) booted"
    );

    let app = Router::new()
        .route("/health", get(health))
        .route("/qbft/sign-block", post(sign_block))
        .with_state(state);

    let listener = TcpListener::bind(("0.0.0.0", val_port)).await?;
    if let Err(e) = axum::serve(listener, app).await {
        error!("server error: {e}");
        return Err(e.into());
    }
    Ok(())
}
