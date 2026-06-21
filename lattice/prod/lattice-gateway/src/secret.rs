//! `/api/admin/secrets/*` — native Rust port of `backend/secret_manager.py`.
//!
//! Argon2id KDF + AES-256-GCM envelope encryption. Wire-compatible with
//! Python implementation: same salt/verifier schema in `secret_config`,
//! same time/memory/parallelism parameters, same AEAD ciphertext layout
//! `[nonce(12) || tag(16) || ciphertext]`.

use std::sync::RwLock;

use aes_gcm::aead::{Aead, KeyInit};
use aes_gcm::{Aes256Gcm, Key, Nonce};
use argon2::password_hash::{PasswordHash, PasswordVerifier};
use argon2::{Algorithm, Argon2, Params, Version};
use axum::{extract::State, http::StatusCode, Json};
use bson::{doc, Document};
use chrono::{SecondsFormat, Utc};
use once_cell::sync::Lazy;
use rand::RngCore;
use serde::{Deserialize, Serialize};

use crate::AppState;

const SALT_BYTES: usize = 16;
const HASH_LEN: u32 = 32;
const ARGON2_TIME_COST: u32 = 3;
const ARGON2_MEMORY_COST: u32 = 65_536; // KiB → 64 MiB
const ARGON2_PARALLELISM: u32 = 1;
const CONFIG_ID: &str = "envelope";

// -- Runtime envelope state (in-memory, never persisted) --------------------

struct EnvelopeRuntime {
    master_key: Option<[u8; 32]>,
    unlocked_at: Option<String>,
    source: String, // "static" | "passphrase" | "locked"
}

static RUNTIME: Lazy<RwLock<EnvelopeRuntime>> = Lazy::new(|| {
    RwLock::new(EnvelopeRuntime {
        master_key: None,
        unlocked_at: None,
        source: "locked".to_string(),
    })
});

/// True if the envelope has a usable master key in memory.
pub fn is_unlocked() -> bool {
    RUNTIME.read().map(|s| s.master_key.is_some()).unwrap_or(false)
}

/// Borrow the master key out of the runtime. Returns None if locked.
pub fn with_master_key<R>(f: impl FnOnce(&[u8; 32]) -> R) -> Option<R> {
    let guard = RUNTIME.read().ok()?;
    guard.master_key.as_ref().map(f)
}

fn set_master_key(key: [u8; 32], source: &str) {
    if let Ok(mut g) = RUNTIME.write() {
        g.master_key = Some(key);
        g.unlocked_at = Some(utc_iso());
        g.source = source.to_string();
    }
}

fn clear_master_key() {
    if let Ok(mut g) = RUNTIME.write() {
        // best-effort zeroize before drop
        if let Some(ref mut k) = g.master_key {
            for b in k.iter_mut() { *b = 0; }
        }
        g.master_key = None;
        g.unlocked_at = None;
        g.source = "locked".to_string();
    }
}

#[derive(Debug, Serialize)]
pub struct SecretStatus {
    pub mode: String,
    pub unlocked: bool,
    pub locked_reason: String,
    pub initialised: bool,
}

#[derive(Debug, Serialize)]
pub struct SecretError {
    pub detail: String,
}

fn err(code: StatusCode, msg: impl Into<String>) -> (StatusCode, Json<SecretError>) {
    (code, Json(SecretError { detail: msg.into() }))
}

fn utc_iso() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Micros, true)
}

/// Derive a 32-byte AES-256-GCM key from passphrase + salt with Argon2id.
pub fn derive_key(passphrase: &str, salt: &[u8]) -> Result<[u8; 32], String> {
    if passphrase.is_empty() {
        return Err("passphrase must be non-empty".into());
    }
    if salt.len() < SALT_BYTES {
        return Err(format!("salt must be >= {} bytes", SALT_BYTES));
    }
    let params = Params::new(ARGON2_MEMORY_COST, ARGON2_TIME_COST, ARGON2_PARALLELISM, Some(HASH_LEN as usize))
        .map_err(|e| format!("argon2 params: {e}"))?;
    let argon2 = Argon2::new(Algorithm::Argon2id, Version::V0x13, params);
    let mut out = [0u8; 32];
    argon2
        .hash_password_into(passphrase.as_bytes(), salt, &mut out)
        .map_err(|e| format!("argon2 hash: {e}"))?;
    Ok(out)
}

/// AES-256-GCM seal. Output = nonce(12) || ciphertext_with_tag(N+16).
pub fn aead_seal(key: &[u8; 32], plaintext: &[u8]) -> Result<Vec<u8>, String> {
    let cipher = Aes256Gcm::new(Key::<Aes256Gcm>::from_slice(key));
    let mut nonce_bytes = [0u8; 12];
    rand::rngs::OsRng.fill_bytes(&mut nonce_bytes);
    let nonce = Nonce::from_slice(&nonce_bytes);
    let ct = cipher.encrypt(nonce, plaintext).map_err(|e| format!("aead seal: {e}"))?;
    let mut out = Vec::with_capacity(12 + ct.len());
    out.extend_from_slice(&nonce_bytes);
    out.extend_from_slice(&ct);
    Ok(out)
}

/// AES-256-GCM open. Input = nonce(12) || ciphertext_with_tag.
pub fn aead_open(key: &[u8; 32], blob: &[u8]) -> Result<Vec<u8>, String> {
    if blob.len() < 28 {
        return Err("ciphertext too short".into());
    }
    let cipher = Aes256Gcm::new(Key::<Aes256Gcm>::from_slice(key));
    let nonce = Nonce::from_slice(&blob[..12]);
    cipher
        .decrypt(nonce, &blob[12..])
        .map_err(|e| format!("aead open: {e}"))
}

/// AES-256-GCM seal with AAD (Python `envelope.seal(plaintext, aad)` wire-compat).
pub fn aead_seal_aad(key: &[u8; 32], plaintext: &[u8], aad: &[u8]) -> Result<Vec<u8>, String> {
    use aes_gcm::aead::{Aead, Payload};
    let cipher = Aes256Gcm::new(Key::<Aes256Gcm>::from_slice(key));
    let mut nonce_bytes = [0u8; 12];
    rand::rngs::OsRng.fill_bytes(&mut nonce_bytes);
    let nonce = Nonce::from_slice(&nonce_bytes);
    let payload = Payload { msg: plaintext, aad };
    let ct = cipher.encrypt(nonce, payload).map_err(|e| format!("aead seal: {e}"))?;
    let mut out = Vec::with_capacity(12 + ct.len());
    out.extend_from_slice(&nonce_bytes);
    out.extend_from_slice(&ct);
    Ok(out)
}

/// AES-256-GCM open with AAD.
pub fn aead_open_aad(key: &[u8; 32], blob: &[u8], aad: &[u8]) -> Result<Vec<u8>, String> {
    use aes_gcm::aead::{Aead, Payload};
    if blob.len() < 28 { return Err("ciphertext too short".into()); }
    let cipher = Aes256Gcm::new(Key::<Aes256Gcm>::from_slice(key));
    let nonce = Nonce::from_slice(&blob[..12]);
    let payload = Payload { msg: &blob[12..], aad };
    cipher.decrypt(nonce, payload).map_err(|e| format!("aead open: {e}"))
}

/// 32-byte master key from `LATTICE_ENVELOPE_KEY` env (64 hex chars).
/// Returns `None` when not configured (passthrough mode like Python v0).
pub fn envelope_key() -> Option<[u8; 32]> {
    let raw = std::env::var("LATTICE_ENVELOPE_KEY").ok()?;
    let bytes = hex::decode(raw.trim()).ok()?;
    if bytes.len() != 32 { return None; }
    let mut out = [0u8; 32];
    out.copy_from_slice(&bytes);
    Some(out)
}

/// `envelope.seal_text(plaintext, aad)` → `"v1:<base64(nonce||ct||tag)>"`
/// or `"v0:<hex>"` if no envelope key (dev mode). Wire-compat with Python.
pub fn envelope_seal_text(plaintext: &str, aad: &[u8]) -> Result<String, String> {
    if let Some(key) = envelope_key() {
        let ct = aead_seal_aad(&key, plaintext.as_bytes(), aad)?;
        use base64::Engine;
        Ok(format!("v1:{}", base64::engine::general_purpose::STANDARD.encode(&ct)))
    } else {
        Ok(format!("v0:{}", hex::encode(plaintext.as_bytes())))
    }
}

/// `envelope.open_text(token, aad)` reverse of `envelope_seal_text`.
pub fn envelope_open_text(token: &str, aad: &[u8]) -> Result<String, String> {
    let (v, payload) = token.split_once(':').ok_or("invalid envelope token")?;
    if v == "v0" {
        let raw = hex::decode(payload).map_err(|e| format!("v0 hex: {e}"))?;
        return String::from_utf8(raw).map_err(|e| format!("utf8: {e}"));
    }
    if v != "v1" { return Err(format!("unknown envelope version: {v}")); }
    let key = envelope_key().ok_or("LATTICE_ENVELOPE_KEY not configured")?;
    use base64::Engine;
    let raw = base64::engine::general_purpose::STANDARD.decode(payload)
        .map_err(|e| format!("v1 base64: {e}"))?;
    let plain = aead_open_aad(&key, &raw, aad)?;
    String::from_utf8(plain).map_err(|e| format!("utf8: {e}"))
}

// -- GET /api/admin/secrets/status ------------------------------------------

pub async fn secret_status(
    State(state): State<AppState>,
) -> Result<Json<SecretStatus>, (StatusCode, Json<SecretError>)> {
    let coll = state.db.collection::<Document>("secret_config");
    let cfg = coll
        .find_one(doc! {"_id": CONFIG_ID})
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let initialised = cfg.is_some();
    let static_key_present = std::env::var("LATTICE_ENVELOPE_KEY")
        .ok()
        .map(|s| !s.trim().is_empty())
        .unwrap_or(false);
    let pass_env_present = std::env::var("LATTICE_ENVELOPE_PASSPHRASE")
        .ok()
        .map(|s| !s.trim().is_empty())
        .unwrap_or(false);

    // If a static key is set and we haven't loaded it yet, do it now.
    if static_key_present && !is_unlocked() {
        if let Ok(static_hex) = std::env::var("LATTICE_ENVELOPE_KEY") {
            if let Ok(bytes) = hex::decode(static_hex.trim()) {
                if bytes.len() == 32 {
                    let mut k = [0u8; 32];
                    k.copy_from_slice(&bytes);
                    set_master_key(k, "static");
                }
            }
        }
    }
    // Auto-unlock via env passphrase at first call if initialised.
    if pass_env_present && initialised && !is_unlocked() {
        if let (Some(cfg_ref), Ok(pass)) = (cfg.as_ref(), std::env::var("LATTICE_ENVELOPE_PASSPHRASE")) {
            if let Ok(salt_hex) = cfg_ref.get_str("salt_hex") {
                if let Ok(salt) = hex::decode(salt_hex) {
                    if let Ok(k) = derive_key(&pass, &salt) {
                        set_master_key(k, "passphrase-env");
                    }
                }
            }
        }
    }

    let unlocked = is_unlocked();
    let runtime_source = RUNTIME.read().map(|g| g.source.clone()).unwrap_or_default();

    let (mode, reason) = if static_key_present {
        ("static".to_string(), String::new())
    } else if pass_env_present {
        if initialised {
            ("passphrase".to_string(), String::new())
        } else {
            (
                "passphrase".to_string(),
                "LATTICE_ENVELOPE_PASSPHRASE set but verifier not initialised — POST /admin/secrets/init".into(),
            )
        }
    } else if initialised {
        if unlocked {
            (runtime_source.clone(), String::new())
        } else {
            ("locked".to_string(), "Keystore locked. Call POST /api/admin/secrets/unlock.".to_string())
        }
    } else {
        ("locked".to_string(), "Keystore not initialised. Call POST /api/admin/secrets/init.".to_string())
    };

    Ok(Json(SecretStatus {
        mode,
        unlocked,
        locked_reason: reason,
        initialised,
    }))
}

// -- POST /api/admin/secrets/init -------------------------------------------

#[derive(Debug, Deserialize)]
pub struct InitPassphraseRequest {
    pub passphrase: String,
}

pub async fn secret_init(
    State(state): State<AppState>,
    Json(req): Json<InitPassphraseRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<SecretError>)> {
    if req.passphrase.len() < 12 {
        return Err(err(StatusCode::UNPROCESSABLE_ENTITY, "passphrase must be >= 12 chars"));
    }
    let coll = state.db.collection::<Document>("secret_config");
    if coll.find_one(doc! {"_id": CONFIG_ID}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?
        .is_some()
    {
        return Err(err(StatusCode::CONFLICT, "envelope already initialised"));
    }

    // Generate salt + derive verifier (Argon2id of passphrase with that salt).
    let mut salt = [0u8; SALT_BYTES];
    rand::rngs::OsRng.fill_bytes(&mut salt);

    // Self-check: derive the master key (caller responsible for keeping passphrase).
    let _master = derive_key(&req.passphrase, &salt)
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e))?;

    // Store salt + a verifier derived from the passphrase (argon2 PHC format).
    use argon2::PasswordHasher;
    use argon2::password_hash::SaltString;
    let salt_b64 = SaltString::encode_b64(&salt)
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let argon2 = Argon2::default();
    let verifier = argon2
        .hash_password(req.passphrase.as_bytes(), &salt_b64)
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?
        .to_string();

    coll.insert_one(doc! {
        "_id": CONFIG_ID,
        "salt_hex": hex::encode(salt),
        "verifier": verifier,
        "kdf": "argon2id",
        "time_cost": ARGON2_TIME_COST as i32,
        "memory_cost": ARGON2_MEMORY_COST as i32,
        "parallelism": ARGON2_PARALLELISM as i32,
        "created_at": utc_iso(),
    })
    .await
    .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("insert: {e}")))?;

    Ok(Json(serde_json::json!({
        "ok": true,
        "mode": "passphrase",
        "initialised": true,
        "message": "envelope initialised — keep the passphrase safe (no recovery)",
    })))
}

// -- POST /api/admin/secrets/unlock -----------------------------------------

#[derive(Debug, Deserialize)]
pub struct UnlockRequest {
    pub passphrase: String,
}

pub async fn secret_unlock(
    State(state): State<AppState>,
    Json(req): Json<UnlockRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<SecretError>)> {
    let coll = state.db.collection::<Document>("secret_config");
    let cfg = coll
        .find_one(doc! {"_id": CONFIG_ID})
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let cfg = match cfg {
        Some(c) => c,
        None => return Err(err(StatusCode::PRECONDITION_FAILED, "envelope not initialised — POST /admin/secrets/init first")),
    };

    let salt_hex = cfg
        .get_str("salt_hex")
        .map_err(|_| err(StatusCode::INTERNAL_SERVER_ERROR, "salt_hex missing"))?;
    let verifier = cfg
        .get_str("verifier")
        .map_err(|_| err(StatusCode::INTERNAL_SERVER_ERROR, "verifier missing"))?;
    let salt = hex::decode(salt_hex)
        .map_err(|_| err(StatusCode::INTERNAL_SERVER_ERROR, "salt corrupted"))?;

    // 1. Verify passphrase against the stored PHC hash.
    let phc = PasswordHash::new(verifier)
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("phc parse: {e}")))?;
    if Argon2::default()
        .verify_password(req.passphrase.as_bytes(), &phc)
        .is_err()
    {
        return Err(err(StatusCode::UNAUTHORIZED, "passphrase rejected"));
    }

    // 2. Derive the master key from the same salt (with our standard params).
    let key = derive_key(&req.passphrase, &salt)
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e))?;
    set_master_key(key, "passphrase");

    Ok(Json(serde_json::json!({
        "ok": true,
        "unlocked": true,
        "mode": "passphrase",
        "unlocked_at": utc_iso(),
    })))
}

// -- POST /api/admin/secrets/lock -------------------------------------------

pub async fn secret_lock() -> Json<serde_json::Value> {
    clear_master_key();
    Json(serde_json::json!({
        "ok": true,
        "unlocked": false,
        "locked_at": utc_iso(),
    }))
}

// -- POST /api/admin/secrets/seal -------------------------------------------

#[derive(Debug, Deserialize)]
pub struct SealRequest {
    pub plaintext_hex: String,
}

pub async fn secret_seal(
    Json(req): Json<SealRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<SecretError>)> {
    if !is_unlocked() {
        return Err(err(StatusCode::PRECONDITION_FAILED, "envelope locked"));
    }
    let plaintext = hex::decode(req.plaintext_hex.trim())
        .map_err(|_| err(StatusCode::BAD_REQUEST, "plaintext_hex not valid hex"))?;
    let ciphertext = with_master_key(|k| aead_seal(k, &plaintext))
        .ok_or_else(|| err(StatusCode::PRECONDITION_FAILED, "envelope locked"))?
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e))?;
    Ok(Json(serde_json::json!({
        "ok": true,
        "ciphertext_hex": hex::encode(ciphertext),
        "algorithm": "AES-256-GCM",
    })))
}

// -- POST /api/admin/secrets/open -------------------------------------------

#[derive(Debug, Deserialize)]
pub struct OpenRequest {
    pub ciphertext_hex: String,
}

pub async fn secret_open(
    Json(req): Json<OpenRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<SecretError>)> {
    if !is_unlocked() {
        return Err(err(StatusCode::PRECONDITION_FAILED, "envelope locked"));
    }
    let ct = hex::decode(req.ciphertext_hex.trim())
        .map_err(|_| err(StatusCode::BAD_REQUEST, "ciphertext_hex not valid hex"))?;
    let plaintext = with_master_key(|k| aead_open(k, &ct))
        .ok_or_else(|| err(StatusCode::PRECONDITION_FAILED, "envelope locked"))?
        .map_err(|e| err(StatusCode::UNPROCESSABLE_ENTITY, e))?;
    Ok(Json(serde_json::json!({
        "ok": true,
        "plaintext_hex": hex::encode(plaintext),
    })))
}

