//! Lattice Mixnet relay — native Rust port of `backend/mixnet_relay.py`.
//!
//! Each relay runs as an independent OS process on its own TCP port and
//! owns an X25519 keypair. When the gateway sends a Pulse message it
//! wraps the payload in 3 nested ChaCha20-Poly1305 layers (one per
//! relay). Each relay decrypts ONE layer using a fresh ECDH ephemeral
//! handshake, sleeps for a Poisson-distributed delay (ε-mixing) and
//! forwards to the next hop. The third relay POSTs the final
//! ciphertext to the gateway's recipient slot.
//!
//! Wire-compatible with the Python implementation:
//!   * Same MongoDB collection `mixnet_keystore`.
//!   * Same HKDF salt/info ("lattice-mixnet-v1") and AEAD AAD
//!     (`layer-<N>` as a single big-endian byte).
//!   * Same JSON wire format on `/health` and `/relay`.
//!
//! Run example:
//!   LATTICE_RELAY_ID=MIX-01 LATTICE_RELAY_PORT=9101 LATTICE_RELAY_LAYER=1 \
//!   MONGO_URL=mongodb://localhost:27017 DB_NAME=lattice ./mixnet-relay

use std::env;
use std::sync::Arc;
use std::time::Duration;

use anyhow::{Context, Result};
use axum::{
    extract::State,
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use bson::doc;
use chacha20poly1305::{
    aead::{Aead, KeyInit, Payload},
    ChaCha20Poly1305, Key as ChaChaKey, Nonce as ChaChaNonce,
};
use chrono::{SecondsFormat, Utc};
use hkdf::Hkdf;
use mongodb::{options::ClientOptions, Client, Database};
use rand_distr::{Distribution, Exp};
use serde::{Deserialize, Serialize};
use sha2::Sha256;
use tokio::net::TcpListener;
use tokio::sync::Mutex;
use tokio::time::sleep;
use tracing::{error, info, warn};
use x25519_dalek::{PublicKey as XPublicKey, StaticSecret};

fn utc_iso() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Micros, true)
}

// -- wire types --------------------------------------------------------------

#[derive(Debug, Deserialize, Serialize, Clone)]
struct OnionPacket {
    eph_pub_hex: String,
    ciphertext_hex: String,
    nonce_hex: String,
}

#[derive(Debug, Serialize)]
struct HealthResponse {
    ok: bool,
    relay_id: String,
    layer: u8,
    port: u16,
    pk_hex: Option<String>,
    started_at: Option<String>,
    relayed_total: u64,
    mean_delay_ms: u32,
    backend: &'static str,
}

#[derive(Debug, Serialize)]
struct ErrorResponse {
    detail: String,
}

#[derive(Debug, Serialize)]
struct RelayResponse {
    ok: bool,
    relay_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    terminal: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    forwarded_to: Option<String>,
}

// Peeled payload format (UTF-8 JSON) matches Python relay:
//   { next_endpoint, next_packet, terminal, gateway_url, delivery }
#[derive(Debug, Deserialize, Serialize)]
struct PeeledPayload {
    #[serde(default)]
    next_endpoint: Option<String>,
    #[serde(default)]
    next_packet: Option<OnionPacket>,
    #[serde(default)]
    terminal: bool,
    #[serde(default)]
    gateway_url: Option<String>,
    #[serde(default)]
    delivery: Option<serde_json::Value>,
}

// -- shared state -----------------------------------------------------------

#[derive(Clone)]
struct AppState {
    relay_id: String,
    relay_port: u16,
    layer: u8,
    mean_delay_ms: u32,
    inner: Arc<Mutex<InnerState>>,
}

#[derive(Default)]
struct InnerState {
    sk: Option<StaticSecret>,
    pk_bytes: Option<[u8; 32]>,
    started_at: Option<String>,
    relayed_total: u64,
}

// -- DB bootstrap ------------------------------------------------------------

async fn boot_key(state: &AppState, db: &Database) -> Result<()> {
    let coll = db.collection::<bson::Document>("mixnet_keystore");
    let doc = coll
        .find_one(doc! {"relay_id": &state.relay_id})
        .await
        .context("mixnet_keystore lookup failed")?;

    let sk: StaticSecret = if let Some(d) = doc {
        let sk_hex = d.get_str("sk_hex").context("sk_hex missing")?;
        let raw = hex::decode(sk_hex)?;
        let mut buf = [0u8; 32];
        if raw.len() != 32 {
            return Err(anyhow::anyhow!("sk_hex must be 32 bytes"));
        }
        buf.copy_from_slice(&raw);
        StaticSecret::from(buf)
    } else {
        // Generate a fresh X25519 secret with the OS rng.
        let sk = StaticSecret::random_from_rng(rand::rngs::OsRng);
        sk
    };

    let pk = XPublicKey::from(&sk);
    let pk_bytes = pk.to_bytes();
    let sk_bytes = sk.to_bytes();

    coll.update_one(
        doc! {"relay_id": &state.relay_id},
        doc! {"$set": {
            "relay_id": &state.relay_id,
            "layer": state.layer as i32,
            "port": state.relay_port as i32,
            "endpoint": format!("http://127.0.0.1:{}", state.relay_port),
            "pk_hex": hex::encode(pk_bytes),
            "sk_hex": hex::encode(sk_bytes),
            "boot_at": utc_iso(),
            "mean_delay_ms": state.mean_delay_ms as i32,
            "backend": "rust",
        }},
    )
    .upsert(true)
    .await?;

    {
        let mut g = state.inner.lock().await;
        g.sk = Some(sk);
        g.pk_bytes = Some(pk_bytes);
        g.started_at = Some(utc_iso());
    }
    Ok(())
}

// -- onion peeling -----------------------------------------------------------

fn derive_key(sk: &StaticSecret, eph_pub_hex: &str) -> Result<[u8; 32]> {
    let raw = hex::decode(eph_pub_hex).context("invalid eph_pub_hex")?;
    if raw.len() != 32 {
        return Err(anyhow::anyhow!("eph_pub must be 32 bytes"));
    }
    let mut pub_bytes = [0u8; 32];
    pub_bytes.copy_from_slice(&raw);
    let eph_pk = XPublicKey::from(pub_bytes);
    let shared = sk.diffie_hellman(&eph_pk);
    // HKDF-SHA256 with no salt, info = "lattice-mixnet-v1", out len 32.
    let hk = Hkdf::<Sha256>::new(None, shared.as_bytes());
    let mut okm = [0u8; 32];
    hk.expand(b"lattice-mixnet-v1", &mut okm)
        .map_err(|e| anyhow::anyhow!("HKDF expand: {e}"))?;
    Ok(okm)
}

fn peel(sk: &StaticSecret, layer: u8, packet: &OnionPacket) -> Result<PeeledPayload> {
    let key = derive_key(sk, &packet.eph_pub_hex)?;
    let cipher = ChaCha20Poly1305::new(ChaChaKey::from_slice(&key));
    let nonce_raw = hex::decode(&packet.nonce_hex).context("invalid nonce_hex")?;
    if nonce_raw.len() != 12 {
        return Err(anyhow::anyhow!("nonce must be 12 bytes"));
    }
    let nonce = ChaChaNonce::from_slice(&nonce_raw);
    let ct = hex::decode(&packet.ciphertext_hex).context("invalid ciphertext_hex")?;
    // AAD: "layer-" + one big-endian byte of layer (matches Python).
    let mut aad = b"layer-".to_vec();
    aad.push(layer);
    let plaintext = cipher
        .decrypt(nonce, Payload { msg: &ct, aad: &aad })
        .map_err(|e| anyhow::anyhow!("AEAD decrypt: {e}"))?;
    let json: PeeledPayload =
        serde_json::from_slice(&plaintext).context("inner JSON parse failed")?;
    Ok(json)
}

async fn poisson_delay(mean_ms: u32) {
    let lambda = 1.0_f64 / (mean_ms.max(1) as f64);
    let exp = Exp::new(lambda).unwrap_or_else(|_| Exp::new(0.01).unwrap());
    // Use OsRng (Send + Sync) so the future stays Send across awaits.
    let delay_ms_f = {
        let mut rng = rand::rngs::OsRng;
        exp.sample(&mut rng)
    };
    let mut delay_ms = (delay_ms_f as u64).min(500);
    if delay_ms == 0 {
        delay_ms = 1;
    }
    sleep(Duration::from_millis(delay_ms)).await;
}

// -- HTTP handlers -----------------------------------------------------------

async fn health(State(state): State<AppState>) -> Json<HealthResponse> {
    let g = state.inner.lock().await;
    Json(HealthResponse {
        ok: true,
        relay_id: state.relay_id.clone(),
        layer: state.layer,
        port: state.relay_port,
        pk_hex: g.pk_bytes.map(|b| hex::encode(b)),
        started_at: g.started_at.clone(),
        relayed_total: g.relayed_total,
        mean_delay_ms: state.mean_delay_ms,
        backend: "rust",
    })
}

#[axum::debug_handler]
async fn relay(
    State(state): State<AppState>,
    Json(packet): Json<OnionPacket>,
) -> Result<Json<RelayResponse>, (StatusCode, Json<ErrorResponse>)> {
    // Clone the secret key out of the mutex so we drop the guard
    // before any `.await` — keeps the future Send.
    let sk = {
        let g = state.inner.lock().await;
        g.sk.clone().ok_or((
            StatusCode::SERVICE_UNAVAILABLE,
            Json(ErrorResponse {
                detail: "relay key not initialised".into(),
            }),
        ))?
    };
    let peeled = peel(&sk, state.layer, &packet).map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            Json(ErrorResponse {
                detail: format!("layer decryption failed: {e}"),
            }),
        )
    })?;

    poisson_delay(state.mean_delay_ms).await;

    {
        let mut g = state.inner.lock().await;
        g.relayed_total += 1;
    }

    let http = reqwest::Client::builder()
        .timeout(Duration::from_secs(3))
        .build()
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse {
                    detail: format!("http client init: {e}"),
                }),
            )
        })?;

    if peeled.terminal {
        // Final hop: POST the delivery payload to the gateway.
        if let (Some(gateway), Some(delivery)) = (peeled.gateway_url, peeled.delivery) {
            let url = format!("{}/api/mixnet/deliver", gateway);
            // Best-effort: mixnet is lossy by spec, swallow errors.
            if let Err(e) = http.post(&url).json(&delivery).send().await {
                warn!("mixnet delivery failed (non-fatal): {}", e);
            }
        }
        return Ok(Json(RelayResponse {
            ok: true,
            relay_id: state.relay_id.clone(),
            terminal: Some(true),
            forwarded_to: None,
        }));
    }

    let next_endpoint = peeled.next_endpoint.ok_or((
        StatusCode::BAD_REQUEST,
        Json(ErrorResponse {
            detail: "malformed inner payload: next_endpoint missing".into(),
        }),
    ))?;
    let next_packet = peeled.next_packet.ok_or((
        StatusCode::BAD_REQUEST,
        Json(ErrorResponse {
            detail: "malformed inner payload: next_packet missing".into(),
        }),
    ))?;

    let url = format!("{}/relay", next_endpoint);
    http.post(&url).json(&next_packet).send().await.map_err(|e| {
        (
            StatusCode::BAD_GATEWAY,
            Json(ErrorResponse {
                detail: format!("hop forward failed: {e}"),
            }),
        )
    })?;

    Ok(Json(RelayResponse {
        ok: true,
        relay_id: state.relay_id.clone(),
        terminal: None,
        forwarded_to: Some(next_endpoint),
    }))
}

// ----------------------------------------------------------------------------

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
        .compact()
        .init();

    let relay_id = env::var("LATTICE_RELAY_ID").unwrap_or_else(|_| "MIX-XX".into());
    let relay_port: u16 = env::var("LATTICE_RELAY_PORT")
        .unwrap_or_else(|_| "9101".into())
        .parse()
        .context("invalid LATTICE_RELAY_PORT")?;
    let layer: u8 = env::var("LATTICE_RELAY_LAYER")
        .unwrap_or_else(|_| "1".into())
        .parse()
        .context("invalid LATTICE_RELAY_LAYER")?;
    let mean_delay_ms: u32 = env::var("LATTICE_MIX_MEAN_DELAY_MS")
        .unwrap_or_else(|_| "80".into())
        .parse()
        .unwrap_or(80);
    let mongo_url = env::var("MONGO_URL").context("MONGO_URL not set")?;
    let db_name = env::var("DB_NAME").context("DB_NAME not set")?;

    let opts = ClientOptions::parse(&mongo_url).await?;
    let client = Client::with_options(opts)?;
    let db = client.database(&db_name);

    let state = AppState {
        relay_id: relay_id.clone(),
        relay_port,
        layer,
        mean_delay_ms,
        inner: Arc::new(Mutex::new(InnerState::default())),
    };

    boot_key(&state, &db).await?;
    info!(
        relay = %relay_id,
        layer = layer,
        port = relay_port,
        mean_delay_ms = mean_delay_ms,
        "Lattice mixnet relay (Rust native) booted"
    );

    let app = Router::new()
        .route("/health", get(health))
        .route("/relay", post(relay))
        .with_state(state);

    let listener = TcpListener::bind(("0.0.0.0", relay_port)).await?;
    if let Err(e) = axum::serve(listener, app).await {
        error!("server error: {e}");
        return Err(e.into());
    }
    Ok(())
}
