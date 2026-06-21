//! `/api/admin/license/*` — native Rust port of `backend/license.py`.
//!
//! ML-DSA-65 license verification. Wire-compatible with the Python
//! implementation: same canonical JSON (sorted keys, no whitespace),
//! same `signature_hex` field, same PQClean ML-DSA-65 verify.

use axum::{extract::State, http::StatusCode, Json};
use bson::{doc, Document};
use chrono::{DateTime, Utc};
use pqcrypto_mldsa::mldsa65;
use pqcrypto_traits::sign::{DetachedSignature as _, PublicKey as _};
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::AppState;

const EDITIONS: &[&str] = &["community", "professional", "banking", "pa", "enterprise"];

#[derive(Debug, Serialize)]
pub struct LicenseStatus {
    pub edition: String,
    pub max_tenants: Option<i64>,
    pub max_users: Option<i64>,
    pub features: Vec<String>,
    pub valid_until: Option<String>,
    pub signed: bool,
    pub vendor_pk_fpr: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct LicenseError {
    pub detail: String,
}

#[derive(Debug, Deserialize)]
pub struct LicenseVerifyRequest {
    pub license_doc: serde_json::Value,
    pub vendor_pk_hex: String,
}

#[derive(Debug, Serialize)]
pub struct LicenseVerifyResponse {
    pub ok: bool,
    pub reason: String,
}

fn err(code: StatusCode, msg: impl Into<String>) -> (StatusCode, Json<LicenseError>) {
    (code, Json(LicenseError { detail: msg.into() }))
}

/// Canonical JSON: sorted keys, no whitespace, UTF-8. Matches Python's
/// `json.dumps(payload, sort_keys=True, separators=(",", ":"))`.
fn canonical_json(v: &Value) -> Vec<u8> {
    let mut buf = Vec::with_capacity(256);
    write_canonical(v, &mut buf);
    buf
}

fn write_canonical(v: &Value, out: &mut Vec<u8>) {
    match v {
        Value::Null => out.extend_from_slice(b"null"),
        Value::Bool(b) => out.extend_from_slice(if *b { b"true" } else { b"false" }),
        Value::Number(n) => out.extend_from_slice(n.to_string().as_bytes()),
        Value::String(s) => {
            out.push(b'"');
            for c in s.chars() {
                match c {
                    '"' => out.extend_from_slice(b"\\\""),
                    '\\' => out.extend_from_slice(b"\\\\"),
                    '\n' => out.extend_from_slice(b"\\n"),
                    '\r' => out.extend_from_slice(b"\\r"),
                    '\t' => out.extend_from_slice(b"\\t"),
                    '\x08' => out.extend_from_slice(b"\\b"),
                    '\x0c' => out.extend_from_slice(b"\\f"),
                    c if (c as u32) < 0x20 => {
                        out.extend_from_slice(format!("\\u{:04x}", c as u32).as_bytes());
                    }
                    c => {
                        let mut buf = [0u8; 4];
                        out.extend_from_slice(c.encode_utf8(&mut buf).as_bytes());
                    }
                }
            }
            out.push(b'"');
        }
        Value::Array(arr) => {
            out.push(b'[');
            for (i, item) in arr.iter().enumerate() {
                if i > 0 { out.push(b','); }
                write_canonical(item, out);
            }
            out.push(b']');
        }
        Value::Object(map) => {
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort();
            out.push(b'{');
            for (i, k) in keys.iter().enumerate() {
                if i > 0 { out.push(b','); }
                write_canonical(&Value::String((*k).clone()), out);
                out.push(b':');
                write_canonical(&map[*k], out);
            }
            out.push(b'}');
        }
    }
}

pub fn verify_license(license_doc: &Value, vendor_pk_hex: &str) -> (bool, String) {
    let obj = match license_doc.as_object() {
        Some(o) => o,
        None => return (false, "license must be a JSON object".into()),
    };
    let sig_hex = match obj.get("signature_hex").and_then(|v| v.as_str()) {
        Some(s) => s,
        None => return (false, "missing signature_hex".into()),
    };
    // Strip signature_hex for canonical computation.
    let mut payload_map = obj.clone();
    payload_map.remove("signature_hex");
    let payload = Value::Object(payload_map);

    let pk = match hex::decode(vendor_pk_hex.trim()) {
        Ok(b) => b,
        Err(_) => return (false, "vendor_pubkey not valid hex".into()),
    };
    let sig_bytes = match hex::decode(sig_hex) {
        Ok(b) => b,
        Err(_) => return (false, "signature not valid hex".into()),
    };
    if pk.len() != 1952 {
        return (false, "vendor_pubkey must be 1952 bytes (ML-DSA-65)".into());
    }
    if sig_bytes.len() != 3309 {
        return (false, "signature must be 3309 bytes (ML-DSA-65)".into());
    }
    let pk = match mldsa65::PublicKey::from_bytes(&pk) {
        Ok(p) => p,
        Err(_) => return (false, "vendor_pubkey load failed".into()),
    };
    let sig = match mldsa65::DetachedSignature::from_bytes(&sig_bytes) {
        Ok(s) => s,
        Err(_) => return (false, "signature load failed".into()),
    };
    let canonical = canonical_json(&payload);
    if mldsa65::verify_detached_signature(&sig, &canonical, &pk).is_err() {
        return (false, "signature verification failed".into());
    }

    // Expiry.
    if let Some(until) = payload.get("valid_until").and_then(|v| v.as_str()) {
        match DateTime::parse_from_rfc3339(&until.replace('Z', "+00:00")) {
            Ok(t) => {
                if t.with_timezone(&Utc) < Utc::now() {
                    return (false, format!("license expired on {}", until));
                }
            }
            Err(_) => return (false, "valid_until is not a valid ISO-8601 timestamp".into()),
        }
    }
    let edition = payload.get("edition").and_then(|v| v.as_str()).unwrap_or("");
    if !EDITIONS.contains(&edition) {
        return (false, format!("unknown edition: {}", edition));
    }
    (true, String::new())
}

// -- GET /api/admin/license/status ------------------------------------------

pub async fn license_status(
    State(state): State<AppState>,
) -> Result<Json<LicenseStatus>, (StatusCode, Json<LicenseError>)> {
    let coll = state.db.collection::<Document>("license_state");
    let doc = coll
        .find_one(doc! {"_id": "active"})
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;

    if let Some(d) = doc {
        let features = d.get_array("features").ok()
            .map(|arr| arr.iter().filter_map(|b| b.as_str().map(String::from)).collect())
            .unwrap_or_else(|| vec!["pulse".into(), "certify".into()]);
        return Ok(Json(LicenseStatus {
            edition: d.get_str("edition").unwrap_or("community").to_string(),
            max_tenants: d.get_i64("max_tenants").ok()
                .or_else(|| d.get_i32("max_tenants").ok().map(|v| v as i64)),
            max_users: d.get_i64("max_users").ok()
                .or_else(|| d.get_i32("max_users").ok().map(|v| v as i64)),
            features,
            valid_until: d.get_str("valid_until").ok().map(String::from),
            signed: d.get_bool("signed").unwrap_or(false),
            vendor_pk_fpr: d.get_str("vendor_pk_fpr").ok().map(String::from),
        }));
    }
    // Default community limits (no license installed).
    Ok(Json(LicenseStatus {
        edition: "community".into(),
        max_tenants: Some(1),
        max_users: Some(10),
        features: vec!["pulse".into(), "certify".into()],
        valid_until: None,
        signed: false,
        vendor_pk_fpr: None,
    }))
}

// -- POST /api/admin/license/verify -----------------------------------------

pub async fn license_verify(
    Json(req): Json<LicenseVerifyRequest>,
) -> Result<Json<LicenseVerifyResponse>, (StatusCode, Json<LicenseError>)> {
    let (ok, reason) = verify_license(&req.license_doc, &req.vendor_pk_hex);
    Ok(Json(LicenseVerifyResponse { ok, reason }))
}
