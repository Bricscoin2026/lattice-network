//! Lattice client-side ML-DSA-65 (FIPS 204) signer for the browser.
//!
//! Wire-format compatible with the server-side Python `pqcrypto.sign.ml_dsa_65`:
//!   * pk = 1952 bytes  (FIPS 204 §3.5.2 pkEncode)
//!   * sk = 4032 bytes  (FIPS 204 §3.5.3 skEncode, expanded form)
//!   * sig = 3309 bytes (FIPS 204 §3.5.4 sigEncode)
//!
//! Exposed to JavaScript via wasm-bindgen:
//!   - generate_keypair()  -> LatticeKeyPair
//!   - sign(sk_hex, msg)    -> signature_hex
//!   - sign_text(sk_hex, t) -> signature_hex
//!   - verify(pk_hex, msg, sig_hex) -> bool
//!   - algorithm()          -> "ML-DSA-65"

#![allow(clippy::missing_safety_doc, deprecated)]

extern crate alloc;

use alloc::format;
use alloc::string::String;
use alloc::vec::Vec;

use ml_dsa::{
    ExpandedSigningKey, ExpandedSigningKeyBytes, MlDsa65, Signature, SigningKey, VerifyingKey,
};
use ml_dsa::signature::{Keypair, Signer, Verifier, SignatureEncoding};
use ml_dsa::common::{Generate, KeyExport, KeyInit};
use wasm_bindgen::prelude::*;

#[wasm_bindgen(start)]
pub fn _start() {
    #[cfg(feature = "console_error_panic_hook")]
    console_error_panic_hook::set_once();
}

#[wasm_bindgen]
pub struct LatticeKeyPair {
    pk: Vec<u8>,
    sk: Vec<u8>,
}

#[wasm_bindgen]
impl LatticeKeyPair {
    #[wasm_bindgen(getter)]
    pub fn public_key_hex(&self) -> String { hex::encode(&self.pk) }
    #[wasm_bindgen(getter)]
    pub fn secret_key_hex(&self) -> String { hex::encode(&self.sk) }
    /// Zero out the buffers — call after exporting the keypair if you
    /// want the secret bytes scrubbed from WASM linear memory.
    pub fn wipe(&mut self) {
        for b in self.sk.iter_mut() { *b = 0; }
        for b in self.pk.iter_mut() { *b = 0; }
    }
}

/// Generate a fresh ML-DSA-65 keypair using browser entropy
/// (`crypto.getRandomValues` via `getrandom` + `wasm_js` backend).
#[wasm_bindgen]
pub fn generate_keypair() -> LatticeKeyPair {
    let sk: SigningKey<MlDsa65> = SigningKey::generate();
    let pk: VerifyingKey<MlDsa65> = sk.verifying_key();
    // Use FIPS 204 expanded form (4032 bytes) — wire-compatible with the
    // Python `pqcrypto.sign.ml_dsa_65` library on the server.
    LatticeKeyPair {
        sk: sk.expanded_key().to_expanded().to_vec(),
        pk: pk.to_bytes().to_vec(),
    }
}

fn decode_expanded_sk(hex_str: &str) -> Result<ExpandedSigningKey<MlDsa65>, JsError> {
    let bytes = hex::decode(hex_str.trim())
        .map_err(|e| JsError::new(&format!("secret_key_hex invalid: {e}")))?;
    let arr: &ExpandedSigningKeyBytes<MlDsa65> = bytes.as_slice().try_into()
        .map_err(|_| JsError::new(&format!(
            "secret key wrong length: got {}, expected 4032 (ML-DSA-65)", bytes.len()
        )))?;
    Ok(ExpandedSigningKey::<MlDsa65>::from_expanded(arr))
}

fn decode_pk(hex_str: &str) -> Result<VerifyingKey<MlDsa65>, JsError> {
    let bytes = hex::decode(hex_str.trim())
        .map_err(|e| JsError::new(&format!("public_key_hex invalid: {e}")))?;
    VerifyingKey::<MlDsa65>::new_from_slice(&bytes)
        .map_err(|_| JsError::new(&format!(
            "public key wrong length: got {}, expected 1952 (ML-DSA-65)", bytes.len()
        )))
}

#[wasm_bindgen]
pub fn sign(secret_key_hex: &str, message: &[u8]) -> Result<String, JsError> {
    let sk = decode_expanded_sk(secret_key_hex)?;
    let sig: Signature<MlDsa65> = sk.sign(message);
    Ok(hex::encode(sig.to_bytes()))
}

#[wasm_bindgen]
pub fn sign_text(secret_key_hex: &str, text: &str) -> Result<String, JsError> {
    sign(secret_key_hex, text.as_bytes())
}

#[wasm_bindgen]
pub fn verify(public_key_hex: &str, message: &[u8], signature_hex: &str) -> Result<bool, JsError> {
    let pk = decode_pk(public_key_hex)?;
    let sig_bytes = hex::decode(signature_hex.trim())
        .map_err(|e| JsError::new(&format!("signature_hex invalid: {e}")))?;
    let sig = match Signature::<MlDsa65>::try_from(sig_bytes.as_slice()) {
        Ok(s) => s,
        Err(_) => return Ok(false),
    };
    Ok(pk.verify(message, &sig).is_ok())
}

#[wasm_bindgen]
pub fn algorithm() -> String { "ML-DSA-65".into() }

// ===========================================================================
// Shamir Secret Sharing over GF(256)  ·  2-of-3 backup of a ML-DSA-65 sk
// ===========================================================================
//
// Pure-Rust, byte-wise SSS. The user's 4032-byte ML-DSA-65 secret key is
// split into N shares (default 3) such that any K shares (default 2)
// recombine to the original secret. The server NEVER sees the secret nor
// any individual share in plaintext — only an X25519-ECIES ciphertext per
// guardian + the SHA3-256 fingerprint of each share (which is what gets
// notarised on-chain).
//
// Wire-format compatible with the Python helper at `backend/shamir.py`
// (Lagrange interpolation in GF(256), AES MDS polynomial 0x1B).

use getrandom::{fill as gr_fill, Error as GrError};
use core::convert::TryInto;
use sha3::{Digest, Sha3_256};

// --- GF(256) log/exp tables, identical to backend/shamir.py ----------------
const fn build_tables() -> ([u8; 256], [u8; 256]) {
    let mut log = [0u8; 256];
    let mut exp = [0u8; 256];
    let mut x: u16 = 1;
    let mut i: usize = 0;
    while i < 255 {
        exp[i] = x as u8;
        log[x as usize & 0xFF] = i as u8;
        let mut next = (x << 1) & 0xFF;
        if (x & 0x80) != 0 {
            next ^= 0x1B;
        }
        x = next;
        i += 1;
    }
    exp[255] = exp[0];
    (log, exp)
}
const GF_TABLES: ([u8; 256], [u8; 256]) = build_tables();

#[inline]
fn gf_mul(a: u8, b: u8) -> u8 {
    if a == 0 || b == 0 { return 0; }
    let (log, exp) = GF_TABLES;
    let s = (log[a as usize] as u16 + log[b as usize] as u16) % 255;
    exp[s as usize]
}

#[inline]
fn gf_div(a: u8, b: u8) -> u8 {
    if a == 0 { return 0; }
    if b == 0 { return 0; } // not reachable for valid shares
    let (log, exp) = GF_TABLES;
    let s = (log[a as usize] as i32 - log[b as usize] as i32).rem_euclid(255);
    exp[s as usize]
}

fn rand_bytes(out: &mut [u8]) -> Result<(), GrError> {
    gr_fill(out)
}

/// Split `secret_hex` into `total` shares with threshold `threshold`.
/// Returns a JS string of the form: `"x1:hex1,x2:hex2,..."`.
///
/// * `secret_hex`  — hex-encoded bytes (e.g. 8064 chars = 4032 bytes for ML-DSA-65 sk).
/// * `threshold`   — minimum shares needed to recover (e.g. 2).
/// * `total`       — total shares produced (e.g. 3).
#[wasm_bindgen]
pub fn shamir_split(secret_hex: &str, threshold: u32, total: u32) -> Result<String, JsError> {
    if !(1 < threshold && threshold <= total && total <= 255) {
        return Err(JsError::new("invalid threshold/total: need 1 < threshold <= total <= 255"));
    }
    let secret = hex::decode(secret_hex.trim())
        .map_err(|e| JsError::new(&format!("secret_hex invalid: {e}")))?;
    if secret.is_empty() {
        return Err(JsError::new("empty secret"));
    }

    let total_u = total as usize;
    let thr_u = threshold as usize;

    // Pre-allocate share buffers.
    let mut shares: Vec<Vec<u8>> = (0..total_u).map(|_| Vec::with_capacity(secret.len())).collect();
    let xs: Vec<u8> = (1..=total_u as u8).collect();

    // For each byte of the secret, build a random degree-(threshold-1) polynomial.
    let mut coeff_buf = alloc::vec![0u8; thr_u - 1];
    for &byte in secret.iter() {
        if !coeff_buf.is_empty() {
            rand_bytes(&mut coeff_buf).map_err(|e| JsError::new(&format!("rng: {e}")))?;
        }
        for (idx, &x) in xs.iter().enumerate() {
            // Horner evaluation: f(x) = a0 + a1·x + a2·x² + ...
            let mut y: u8 = 0;
            for &c in coeff_buf.iter().rev() {
                y = gf_mul(y, x) ^ c;
            }
            y = gf_mul(y, x) ^ byte;
            shares[idx].push(y);
        }
    }

    // Serialise as "x:hex,x:hex,...".
    let mut out = String::new();
    for (i, sh) in shares.iter().enumerate() {
        if i > 0 { out.push(','); }
        out.push_str(&format!("{}:{}", xs[i], hex::encode(sh)));
    }
    Ok(out)
}

/// Recombine the secret from any K shares.
/// Accepts the same comma-separated string format produced by `shamir_split`,
/// but only with `K` of the entries present. Returns hex-encoded secret.
#[wasm_bindgen]
pub fn shamir_recover(shares_csv: &str) -> Result<String, JsError> {
    let parts: Vec<&str> = shares_csv.split(',').collect();
    if parts.len() < 2 {
        return Err(JsError::new("need at least 2 shares"));
    }
    let mut xs: Vec<u8> = Vec::with_capacity(parts.len());
    let mut ys: Vec<Vec<u8>> = Vec::with_capacity(parts.len());
    for p in parts.iter() {
        let mut sp = p.splitn(2, ':');
        let x_str = sp.next().ok_or_else(|| JsError::new("malformed share"))?;
        let y_str = sp.next().ok_or_else(|| JsError::new("malformed share, missing ':'"))?;
        let x: u8 = x_str.trim().parse()
            .map_err(|_| JsError::new(&format!("invalid x coord: {x_str}")))?;
        let y = hex::decode(y_str.trim())
            .map_err(|e| JsError::new(&format!("invalid y hex: {e}")))?;
        xs.push(x);
        ys.push(y);
    }
    let n_bytes = ys[0].len();
    if ys.iter().any(|y| y.len() != n_bytes) {
        return Err(JsError::new("shares have different sizes"));
    }
    let mut out: Vec<u8> = Vec::with_capacity(n_bytes);
    for i in 0..n_bytes {
        // Lagrange interpolation at x=0 in GF(256).
        let mut result: u8 = 0;
        for j in 0..xs.len() {
            let mut num: u8 = 1;
            let mut den: u8 = 1;
            for k in 0..xs.len() {
                if k == j { continue; }
                num = gf_mul(num, xs[k]);
                den = gf_mul(den, xs[j] ^ xs[k]);
            }
            let term = gf_mul(ys[j][i], gf_div(num, den));
            result ^= term;
        }
        out.push(result);
    }
    Ok(hex::encode(out))
}

/// SHA3-256 fingerprint of a single share (`x || y`) — what gets pinned on-chain.
#[wasm_bindgen]
pub fn shamir_fingerprint(share: &str) -> Result<String, JsError> {
    let mut sp = share.splitn(2, ':');
    let x_str = sp.next().ok_or_else(|| JsError::new("malformed share"))?;
    let y_str = sp.next().ok_or_else(|| JsError::new("malformed share, missing ':'"))?;
    let x: u8 = x_str.trim().parse()
        .map_err(|_| JsError::new(&format!("invalid x coord: {x_str}")))?;
    let y = hex::decode(y_str.trim())
        .map_err(|e| JsError::new(&format!("invalid y hex: {e}")))?;
    let mut hasher = Sha3_256::new();
    hasher.update([x]);
    hasher.update(&y);
    Ok(hex::encode(hasher.finalize()))
}
