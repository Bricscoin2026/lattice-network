//! POST /api/auth/challenge + /api/auth/verify — native Rust port of
//! `backend/routes/auth.py`.
//!
//! Challenge-response flow:
//!   1. Client POSTs lns_name → server issues a one-time nonce + challenge_id
//!      stored with TTL=120s.
//!   2. Client signs the nonce with their ML-DSA-65 secret key and POSTs
//!      back (challenge_id, signature_hex).
//!   3. Server verifies the signature against the pk from `keystore`,
//!      marks the challenge consumed, issues a HS256 JWT with TTL=8h.
//!
//! Wire-compatible with the Python implementation: same JWT secret env
//! `LATTICE_JWT_SECRET`, same algorithm HS256, same claim set
//! (sub, tenant_id, role, iat, exp, iss, jti).

use std::time::{SystemTime, UNIX_EPOCH};

use axum::{extract::State, http::StatusCode, Json};
use bson::{doc, Document};
use chrono::{SecondsFormat, Utc};
use jsonwebtoken::{encode, EncodingKey, Header};
use pqcrypto_mldsa::mldsa65;
use pqcrypto_traits::sign::{DetachedSignature as _, PublicKey as _};
use rand::RngCore;
use serde::{Deserialize, Serialize};

use crate::AppState;

const CHALLENGE_TTL_SECONDS: i64 = 120;

fn jwt_secret() -> String {
    std::env::var("LATTICE_JWT_SECRET").unwrap_or_else(|_| "dev-only-please-rotate".into())
}

fn jwt_ttl_seconds() -> i64 {
    std::env::var("LATTICE_JWT_TTL_HOURS")
        .ok()
        .and_then(|s| s.parse::<i64>().ok())
        .unwrap_or(8)
        * 3600
}

fn utc_iso() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Micros, true)
}

fn now_unix() -> i64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs() as i64).unwrap_or(0)
}

fn random_hex(bytes: usize) -> String {
    let mut buf = vec![0u8; bytes];
    rand::rngs::OsRng.fill_bytes(&mut buf);
    hex::encode(buf)
}

// -- Wire types --------------------------------------------------------------

#[derive(Debug, Deserialize)]
pub struct ChallengeRequest {
    pub lns_name: String,
}

#[derive(Debug, Serialize)]
pub struct ChallengeResponse {
    pub challenge_id: String,
    pub lns_name: String,
    pub nonce_hex: String,
    pub issued_at: String,
    pub expires_in_seconds: i64,
}

#[derive(Debug, Deserialize)]
pub struct VerifyRequest {
    pub challenge_id: String,
    pub signature_hex: String,
}

#[derive(Debug, Serialize)]
pub struct AuthSession {
    pub ok: bool,
    pub token: String,
    pub lns: String,
    pub tenant_id: Option<String>,
    pub role: String,
    pub expires_in_seconds: i64,
}

#[derive(Debug, Serialize)]
pub struct AuthError {
    pub detail: String,
}

#[derive(Debug, Serialize)]
struct JwtClaims {
    sub: String,
    tenant_id: Option<String>,
    role: String,
    iat: i64,
    exp: i64,
    iss: String,
    jti: String,
}

fn err(code: StatusCode, msg: impl Into<String>) -> (StatusCode, Json<AuthError>) {
    (code, Json(AuthError { detail: msg.into() }))
}

// -- POST /api/auth/challenge -----------------------------------------------

pub async fn auth_challenge(
    State(state): State<AppState>,
    Json(req): Json<ChallengeRequest>,
) -> Result<Json<ChallengeResponse>, (StatusCode, Json<AuthError>)> {
    let name = req.lns_name.trim().to_lowercase();

    let lns = state.db.collection::<Document>("lns")
        .find_one(doc! {"lns_name": &name, "status": "ACTIVE"})
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    if lns.is_none() {
        // Do not leak existence — same 404 for unknown LNS and revoked.
        return Err(err(StatusCode::NOT_FOUND, "lns not active"));
    }

    let challenge_id = format!("chal-{}", random_hex(8));
    let nonce_hex = random_hex(32);
    let ts = utc_iso();
    let expires_at_ts = now_unix() + CHALLENGE_TTL_SECONDS;

    state.db.collection::<Document>("auth_challenges")
        .insert_one(doc! {
            "challenge_id": &challenge_id,
            "lns_name": &name,
            "nonce_hex": &nonce_hex,
            "issued_at": &ts,
            "expires_at_ts": expires_at_ts,
            "consumed": false,
        })
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("insert challenge: {e}")))?;

    Ok(Json(ChallengeResponse {
        challenge_id,
        lns_name: name,
        nonce_hex,
        issued_at: ts,
        expires_in_seconds: CHALLENGE_TTL_SECONDS,
    }))
}

// -- POST /api/auth/verify --------------------------------------------------

pub async fn auth_verify(
    State(state): State<AppState>,
    Json(req): Json<VerifyRequest>,
) -> Result<Json<AuthSession>, (StatusCode, Json<AuthError>)> {
    let challenges = state.db.collection::<Document>("auth_challenges");
    let chal = challenges
        .find_one(doc! {"challenge_id": &req.challenge_id})
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let chal = match chal {
        Some(c) => c,
        None => return Err(err(StatusCode::NOT_FOUND, "challenge not found")),
    };

    if chal.get_bool("consumed").unwrap_or(false) {
        return Err(err(StatusCode::CONFLICT, "challenge already consumed"));
    }
    let expires_ts = chal.get_i64("expires_at_ts")
        .or_else(|_| chal.get_i32("expires_at_ts").map(|v| v as i64))
        .or_else(|_| chal.get_f64("expires_at_ts").map(|v| v as i64))
        .unwrap_or(0);
    if now_unix() > expires_ts {
        return Err(err(StatusCode::GONE, "challenge expired"));
    }

    let name = chal.get_str("lns_name").unwrap_or("").to_string();
    let nonce_hex = chal.get_str("nonce_hex").unwrap_or("");
    let nonce = hex::decode(nonce_hex)
        .map_err(|_| err(StatusCode::INTERNAL_SERVER_ERROR, "stored nonce is corrupted"))?;

    let ks = state.db.collection::<Document>("keystore")
        .find_one(doc! {"entity": &name})
        .projection(doc! {"_id": 0, "pk_hex": 1})
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let ks = match ks {
        Some(k) => k,
        None => return Err(err(StatusCode::NOT_FOUND, "no public key on file")),
    };
    let pk_hex = ks.get_str("pk_hex").unwrap_or("");
    let pk_bytes = hex::decode(pk_hex)
        .map_err(|_| err(StatusCode::INTERNAL_SERVER_ERROR, "stored pk corrupted"))?;
    let pk = mldsa65::PublicKey::from_bytes(&pk_bytes)
        .map_err(|_| err(StatusCode::INTERNAL_SERVER_ERROR, "stored pk size mismatch"))?;

    let sig_bytes = hex::decode(req.signature_hex.trim())
        .map_err(|_| err(StatusCode::BAD_REQUEST, "malformed signature_hex"))?;
    let sig = mldsa65::DetachedSignature::from_bytes(&sig_bytes)
        .map_err(|_| err(StatusCode::BAD_REQUEST, "signature size mismatch"))?;
    if mldsa65::verify_detached_signature(&sig, &nonce, &pk).is_err() {
        return Err(err(StatusCode::UNAUTHORIZED, "signature verification failed"));
    }

    // Mark challenge consumed (atomic CAS-like: only update if still un-consumed).
    challenges
        .update_one(
            doc! {"challenge_id": &req.challenge_id, "consumed": false},
            doc! {"$set": {"consumed": true, "consumed_at": utc_iso()}},
        )
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("update challenge: {e}")))?;

    // Resolve role + tenant.
    let lns_doc = state.db.collection::<Document>("lns")
        .find_one(doc! {"lns_name": &name})
        .projection(doc! {"_id": 0, "role": 1, "tenant_id": 1})
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let (role, tenant_id) = match lns_doc {
        Some(d) => (
            d.get_str("role").unwrap_or("operator").to_string(),
            d.get_str("tenant_id").ok().map(String::from).filter(|s| !s.is_empty()),
        ),
        None => ("operator".to_string(), None),
    };

    // Issue JWT (HS256, wire-compatible with auth_state.py).
    let now = now_unix();
    let ttl = jwt_ttl_seconds();
    let jti = {
        let mut buf = [0u8; 16];
        rand::rngs::OsRng.fill_bytes(&mut buf);
        base64_urlsafe(&buf)
    };
    let claims = JwtClaims {
        sub: name.clone(),
        tenant_id: tenant_id.clone(),
        role: role.clone(),
        iat: now,
        exp: now + ttl,
        iss: "lattice-gateway".to_string(),
        jti: jti.clone(),
    };
    let secret = jwt_secret();
    let token = encode(
        &Header::new(jsonwebtoken::Algorithm::HS256),
        &claims,
        &EncodingKey::from_secret(secret.as_bytes()),
    )
    .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("jwt encode: {e}")))?;

    // Access log (best-effort, fire-and-forget would also be fine).
    let _ = state.db.collection::<Document>("access_log")
        .insert_one(doc! {
            "ts": utc_iso(),
            "event": "login_success",
            "lns": &name,
            "tenant_id": tenant_id.clone().unwrap_or_default(),
            "role": &role,
            "jti": &jti,
            "via": "lattice-gateway-rust",
        })
        .await;

    Ok(Json(AuthSession {
        ok: true,
        token,
        lns: name,
        tenant_id,
        role,
        expires_in_seconds: ttl,
    }))
}

// -- URL-safe base64 without padding (matches Python's secrets.token_urlsafe).

fn base64_urlsafe(bytes: &[u8]) -> String {
    const CHARS: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    let mut out = String::with_capacity((bytes.len() * 4 + 2) / 3);
    let mut i = 0;
    while i + 3 <= bytes.len() {
        let n = ((bytes[i] as u32) << 16) | ((bytes[i + 1] as u32) << 8) | (bytes[i + 2] as u32);
        out.push(CHARS[((n >> 18) & 63) as usize] as char);
        out.push(CHARS[((n >> 12) & 63) as usize] as char);
        out.push(CHARS[((n >> 6) & 63) as usize] as char);
        out.push(CHARS[(n & 63) as usize] as char);
        i += 3;
    }
    let rem = bytes.len() - i;
    if rem == 1 {
        let n = (bytes[i] as u32) << 16;
        out.push(CHARS[((n >> 18) & 63) as usize] as char);
        out.push(CHARS[((n >> 12) & 63) as usize] as char);
    } else if rem == 2 {
        let n = ((bytes[i] as u32) << 16) | ((bytes[i + 1] as u32) << 8);
        out.push(CHARS[((n >> 18) & 63) as usize] as char);
        out.push(CHARS[((n >> 12) & 63) as usize] as char);
        out.push(CHARS[((n >> 6) & 63) as usize] as char);
    }
    out
}
