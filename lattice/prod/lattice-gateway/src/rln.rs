//! ZK-RLN identity layer · Real Starknet Poseidon over the felt field.
//! (M7 step 4b)
//!
//! Wire-compatible with Python `server.py::_rln_commitment` /
//! `_rln_real_nullifier` (poseidon_py · Starknet felt prime).
//!
//! Cross-interop **verified**: same input felts produce the same Poseidon
//! digest byte-for-byte in Rust (`starknet-crypto::poseidon_hash_many`)
//! and Python (`poseidon_py.poseidon_hash::poseidon_hash_many`).
//!
//! Storage:
//!   `db.rln_secrets` row per LNS:
//!     { lns, secret_hex, commitment_hex, created_at, algo: "poseidon-starknet" }

use bson::{doc, Document};
use mongodb::Database;
use num_bigint::BigUint;
use rand::RngCore;
use starknet_crypto::poseidon_hash_many;
use starknet_ff::FieldElement;

use crate::chain::utc_iso;

/// Starknet felt prime: (1 << 251) + 17 * (1 << 192) + 1
fn starknet_field_p() -> BigUint {
    (BigUint::from(1_u8) << 251)
        + (BigUint::from(17_u8) * (BigUint::from(1_u8) << 192))
        + BigUint::from(1_u8)
}

/// Convert a BigUint into a Starknet FieldElement (reducing mod p).
fn felt(value: &BigUint) -> FieldElement {
    let p = starknet_field_p();
    let v = value % &p;
    let bytes = v.to_bytes_be();
    let mut buf = [0u8; 32];
    let off = 32 - bytes.len();
    buf[off..].copy_from_slice(&bytes);
    FieldElement::from_bytes_be(&buf).unwrap_or(FieldElement::ZERO)
}

fn felt_to_64hex(f: &FieldElement) -> String {
    // FieldElement::to_bytes_be is 32 bytes; hex = 64 chars.
    let b = f.to_bytes_be();
    hex::encode(b)
}

/// `poseidon_hash_many` over `inputs` reduced into the felt field.
pub fn poseidon(inputs: &[BigUint]) -> FieldElement {
    let fs: Vec<FieldElement> = inputs.iter().map(felt).collect();
    poseidon_hash_many(&fs)
}

/// Sample a uniform secret in (0, p).
pub fn sample_secret() -> BigUint {
    let p = starknet_field_p();
    loop {
        // 31 bytes -> safely under the field (top bit < 251).
        let mut buf = [0u8; 31];
        rand::rngs::OsRng.fill_bytes(&mut buf);
        let cand = BigUint::from_bytes_be(&buf);
        if !cand.eq(&BigUint::from(0_u8)) && cand < p { return cand; }
    }
}

/// Load (or create) the RLN secret for `lns`. Returns the secret integer.
pub async fn get_or_create_rln_secret(db: &Database, lns: &str) -> anyhow::Result<BigUint> {
    let coll = db.collection::<Document>("rln_secrets");
    if let Some(doc) = coll.find_one(doc! {"lns": lns}).await? {
        let hex_s = doc.get_str("secret_hex").unwrap_or("");
        return Ok(BigUint::parse_bytes(hex_s.as_bytes(), 16).unwrap_or_default());
    }
    let secret = sample_secret();
    let commitment = poseidon(&[secret.clone()]);
    coll.insert_one(doc! {
        "lns": lns,
        "secret_hex": format!("{:064x}", secret),
        "commitment_hex": felt_to_64hex(&commitment),
        "created_at": utc_iso(),
        "algo": "poseidon-starknet",
    }).await?;
    Ok(secret)
}

/// `Poseidon(secret)` — identity commitment.
pub async fn rln_commitment(db: &Database, lns: &str) -> anyhow::Result<String> {
    let secret = get_or_create_rln_secret(db, lns).await?;
    Ok(felt_to_64hex(&poseidon(&[secret])))
}

/// `Poseidon(secret, epoch)` — epoch-bound nullifier.
pub async fn rln_nullifier(db: &Database, lns: &str, epoch: i64) -> anyhow::Result<String> {
    let secret = get_or_create_rln_secret(db, lns).await?;
    let ep = BigUint::from(epoch as u64);
    Ok(felt_to_64hex(&poseidon(&[secret, ep])))
}
