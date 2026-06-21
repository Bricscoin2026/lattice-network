//! PQC keystore lookup + ML-DSA-65 sign/verify.
//!
//! Wire-compatible with `backend/core.py::pqc_sign` and
//! `backend/core.py::pqc_verify`: same `keystore` collection schema,
//! same NIST FIPS 204 ML-DSA-65 algorithm, same hex encoding.

use anyhow::{anyhow, Context, Result};
use bson::{doc, Document};
use chrono::{SecondsFormat, Utc};
use mongodb::Database;
use pqcrypto_mldsa::mldsa65;
use pqcrypto_traits::sign::{
    DetachedSignature as _, PublicKey as DsaPublicKey, SecretKey as DsaSecretKey,
};
use sha3::{Digest, Sha3_256};
use tracing::warn;

const ML_DSA_65_PK_LEN: usize = 1952;
const ML_DSA_65_SK_LEN: usize = 4032;

fn fingerprint(pk: &[u8]) -> String {
    let mut h = Sha3_256::new();
    h.update(pk);
    let out = h.finalize();
    out[..16].iter().map(|b| format!("{:02X}", b)).collect::<Vec<_>>().join("")
}

fn utc_iso() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Micros, true)
}

pub struct PqcSignature {
    pub signature_hex: String,
    pub fingerprint: String,
}

/// Look up the keypair for `entity` in MongoDB; if missing or legacy
/// (Dilithium3 size mismatch), generate a fresh ML-DSA-65 keypair and
/// persist it. Returns (sk_bytes, pk_bytes).
async fn load_or_generate(db: &Database, entity: &str, role: &str) -> Result<(Vec<u8>, Vec<u8>)> {
    let coll = db.collection::<Document>("keystore");
    let existing = coll.find_one(doc! {"entity": entity}).await?;
    if let Some(d) = existing {
        let pk_hex = d.get_str("pk_hex").context("keystore.pk_hex missing")?;
        let sk_hex = d.get_str("sk_hex").context("keystore.sk_hex missing")?;
        let pk = hex::decode(pk_hex)?;
        let sk = hex::decode(sk_hex)?;
        if pk.len() == ML_DSA_65_PK_LEN && sk.len() == ML_DSA_65_SK_LEN {
            return Ok((sk, pk));
        }
        warn!(entity = %entity, pk_len = pk.len(), sk_len = sk.len(),
              "legacy keypair detected — regenerating ML-DSA-65 FIPS 204");
    }
    let (pk_new, sk_new) = mldsa65::keypair();
    let pk_bytes = pk_new.as_bytes().to_vec();
    let sk_bytes = sk_new.as_bytes().to_vec();
    let fp = fingerprint(&pk_bytes);
    coll.update_one(
        doc! {"entity": entity},
        doc! {"$set": {
            "entity": entity,
            "role": role,
            "pk_hex": hex::encode(&pk_bytes),
            "sk_hex": hex::encode(&sk_bytes),
            "fingerprint": &fp,
            "created_at": utc_iso(),
            "regenerated_by": "lattice-gateway-rust",
        }},
    )
    .upsert(true)
    .await?;
    Ok((sk_bytes, pk_bytes))
}

/// Sign `message` with the ML-DSA-65 secret key bound to `entity`.
pub async fn pqc_sign(db: &Database, entity: &str, message: &[u8], role: &str) -> Result<PqcSignature> {
    let (sk_bytes, pk_bytes) = load_or_generate(db, entity, role).await?;
    let sk = mldsa65::SecretKey::from_bytes(&sk_bytes)
        .map_err(|_| anyhow!("invalid SK bytes in keystore for {}", entity))?;
    let sig = mldsa65::detached_sign(message, &sk);
    let sig_bytes = sig.as_bytes().to_vec();

    // Self-check: verify the signature we just produced against the
    // public key we just persisted. Catches PK/SK desync regressions.
    let pk = mldsa65::PublicKey::from_bytes(&pk_bytes)
        .map_err(|_| anyhow!("invalid PK bytes in keystore for {}", entity))?;
    if mldsa65::verify_detached_signature(&sig, message, &pk).is_err() {
        return Err(anyhow!(
            "pqc_sign self-check FAILED for entity={} (msg_len={}, sig_len={}, pk_len={}, sk_len={})",
            entity, message.len(), sig_bytes.len(), pk_bytes.len(), sk_bytes.len()
        ));
    }

    Ok(PqcSignature {
        signature_hex: hex::encode(&sig_bytes),
        fingerprint: fingerprint(&pk_bytes),
    })
}

/// Verify the detached signature against the entity's public key.
pub async fn pqc_verify(db: &Database, entity: &str, message: &[u8], signature_hex: &str) -> bool {
    let coll = db.collection::<Document>("keystore");
    let doc = match coll.find_one(doc! {"entity": entity}).await {
        Ok(Some(d)) => d,
        _ => return false,
    };
    let pk_hex = match doc.get_str("pk_hex") {
        Ok(s) => s,
        Err(_) => return false,
    };
    let pk_bytes = match hex::decode(pk_hex) {
        Ok(b) => b,
        Err(_) => return false,
    };
    if pk_bytes.len() != ML_DSA_65_PK_LEN {
        return false;
    }
    let pk = match mldsa65::PublicKey::from_bytes(&pk_bytes) {
        Ok(p) => p,
        Err(_) => return false,
    };
    let sig_bytes = match hex::decode(signature_hex) {
        Ok(b) => b,
        Err(_) => return false,
    };
    let sig = match mldsa65::DetachedSignature::from_bytes(&sig_bytes) {
        Ok(s) => s,
        Err(_) => return false,
    };
    mldsa65::verify_detached_signature(&sig, message, &pk).is_ok()
}

/// Deterministic hex digest of `seed` truncated to `length` chars.
/// Matches `backend/core.py::det_hex`.
pub fn det_hex(seed: &str, length: usize) -> String {
    let mut h = Sha3_256::new();
    h.update(seed.as_bytes());
    let full = hex::encode(h.finalize());
    full.chars().take(length).collect()
}

/// Sign `message` on behalf of `entity`. If the keystore lacks an SK for
/// that entity (client-managed key) — fall back to a per-tenant gateway
/// key `<gateway_prefix>-<tenant_id>`. Returns
/// (signature_hex, fingerprint, actual_signer_entity).
///
/// Wire-compatible with `backend/server.py::_pqc_sign_or_delegate`.
pub async fn pqc_sign_or_delegate(
    db: &Database,
    entity: &str,
    message: &[u8],
    tenant_id: Option<&str>,
    gateway_prefix: &str,
) -> Result<(String, String, String)> {
    let coll = db.collection::<Document>("keystore");
    let existing = coll.find_one(doc! {"entity": entity}).await?;
    let has_sk = existing.as_ref()
        .and_then(|d| d.get_str("sk_hex").ok())
        .map(|s| !s.is_empty())
        .unwrap_or(false);
    if has_sk {
        let s = pqc_sign(db, entity, message, "lns").await?;
        return Ok((s.signature_hex, s.fingerprint, entity.to_string()));
    }
    let gw_entity = match tenant_id {
        Some(t) if !t.is_empty() => format!("{}-{}", gateway_prefix, t),
        _ => gateway_prefix.to_string(),
    };
    let s = pqc_sign(db, &gw_entity, message, "gateway").await?;
    Ok((s.signature_hex, s.fingerprint, gw_entity))
}
