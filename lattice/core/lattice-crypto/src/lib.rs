//! Lattice Network — Post-Quantum Cryptography primitives.
//!
//! Open-core module (BSL 1.1) providing the NIST-standardised PQC
//! primitives used by the rest of the Lattice ecosystem:
//!
//! * **ML-DSA-65** (FIPS 204, historically *Dilithium3*) — sovereign
//!   identity signatures.
//! * **ML-KEM-768** (FIPS 203, historically *Kyber-768*) — key
//!   encapsulation for PQXDH session bootstrap (used by
//!   `pulse-ratchet`).
//! * **SHA3-512 / SHA3-256** (FIPS 202) — payload digesting.
//! * **AES-256-GCM** (NIST SP 800-38D) — symmetric AEAD for the
//!   Pulse Protocol and the Loopix mixnet inner legs.

use pqcrypto_dilithium::dilithium3;
use pqcrypto_kyber::kyber768;
use pqcrypto_traits::sign::{
    DetachedSignature as _,
    PublicKey as DsaPublicKey,
    SecretKey as DsaSecretKey,
};
use pqcrypto_traits::kem::{
    Ciphertext as KemCiphertextTrait,
    PublicKey as KemPublicKey,
    SecretKey as KemSecretKey,
    SharedSecret as KemSharedSecret,
};
use sha3::{Digest, Sha3_512, Sha3_256};
use serde::{Serialize, Deserialize};

// ---------------------------------------------------------------------------
// ML-DSA-65 (Dilithium3) — Sovereign identity signatures
// ---------------------------------------------------------------------------

/// Sovereign identity key pair (ML-DSA-65 — NIST FIPS 204).
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct LatticeKeyPair {
    pub public_key: Vec<u8>,
    pub secret_key: Vec<u8>,
}

impl LatticeKeyPair {
    /// Generate a fresh sovereign PQC identity (ML-DSA-65).
    pub fn generate_pqc_identity() -> Self {
        let (pk, sk) = dilithium3::keypair();
        Self {
            public_key: pk.as_bytes().to_vec(),
            secret_key: sk.as_bytes().to_vec(),
        }
    }

    /// Produce a detached ML-DSA-65 signature over `data`.
    pub fn sign_data(&self, data: &[u8]) -> Vec<u8> {
        let sk = dilithium3::SecretKey::from_bytes(&self.secret_key)
            .expect("LatticeKeyPair: invalid secret key bytes");
        let sig = dilithium3::detached_sign(data, &sk);
        sig.as_bytes().to_vec()
    }
}

/// Verify a detached ML-DSA-65 signature against `data` using
/// `public_key`. Returns `false` on any decoding or verification
/// failure.
pub fn verify_pqc_signature(data: &[u8], signature: &[u8], public_key: &[u8]) -> bool {
    let pk = match dilithium3::PublicKey::from_bytes(public_key) {
        Ok(k) => k,
        Err(_) => return false,
    };
    let sig = match dilithium3::DetachedSignature::from_bytes(signature) {
        Ok(s) => s,
        Err(_) => return false,
    };
    dilithium3::verify_detached_signature(&sig, data, &pk).is_ok()
}

// ---------------------------------------------------------------------------
// ML-KEM-768 (Kyber768) — PQ Key Encapsulation
// ---------------------------------------------------------------------------

/// Sovereign KEM key pair (ML-KEM-768 — NIST FIPS 203). Used by
/// `pulse-ratchet` to bootstrap a PQXDH session.
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct LatticeKemKeyPair {
    pub public_key: Vec<u8>,
    pub secret_key: Vec<u8>,
}

impl LatticeKemKeyPair {
    /// Generate a fresh ML-KEM-768 key pair.
    pub fn generate_kem_identity() -> Self {
        let (pk, sk) = kyber768::keypair();
        Self {
            public_key: pk.as_bytes().to_vec(),
            secret_key: sk.as_bytes().to_vec(),
        }
    }
}

/// Result of ML-KEM-768 encapsulation against a peer public key.
pub struct KemEncapsulation {
    pub ciphertext: Vec<u8>,
    pub shared_secret: [u8; 32],
}

/// Encapsulate a fresh shared secret against `peer_public_key`.
pub fn kem_encapsulate(peer_public_key: &[u8]) -> Result<KemEncapsulation, &'static str> {
    let pk = kyber768::PublicKey::from_bytes(peer_public_key)
        .map_err(|_| "ML-KEM: invalid public key")?;
    let (ss, ct) = kyber768::encapsulate(&pk);
    let mut secret = [0u8; 32];
    let raw = ss.as_bytes();
    let n = raw.len().min(32);
    secret[..n].copy_from_slice(&raw[..n]);
    Ok(KemEncapsulation {
        ciphertext: ct.as_bytes().to_vec(),
        shared_secret: secret,
    })
}

/// Decapsulate a ciphertext using the local secret key.
pub fn kem_decapsulate(ciphertext: &[u8], secret_key: &[u8]) -> Result<[u8; 32], &'static str> {
    let sk = kyber768::SecretKey::from_bytes(secret_key)
        .map_err(|_| "ML-KEM: invalid secret key")?;
    let ct = kyber768::Ciphertext::from_bytes(ciphertext)
        .map_err(|_| "ML-KEM: invalid ciphertext")?;
    let ss = kyber768::decapsulate(&ct, &sk);
    let mut secret = [0u8; 32];
    let raw = ss.as_bytes();
    let n = raw.len().min(32);
    secret[..n].copy_from_slice(&raw[..n]);
    Ok(secret)
}

// ---------------------------------------------------------------------------
// SHA-3 digesting helpers
// ---------------------------------------------------------------------------

/// Compute a SHA3-512 digest of `payload` (NIST FIPS 202).
pub fn compute_sha3_512(payload: &[u8]) -> [u8; 64] {
    let mut hasher = Sha3_512::new();
    hasher.update(payload);
    let result = hasher.finalize();
    let mut hash = [0u8; 64];
    hash.copy_from_slice(&result);
    hash
}

/// Compute a SHA3-256 digest of `payload` (NIST FIPS 202).
pub fn compute_sha3_256(payload: &[u8]) -> [u8; 32] {
    let mut hasher = Sha3_256::new();
    hasher.update(payload);
    let result = hasher.finalize();
    let mut hash = [0u8; 32];
    hash.copy_from_slice(&result);
    hash
}

/// Compute a sovereign-identity fingerprint suitable for human
/// display: SHA3-256(public_key) truncated to 8 bytes formatted
/// as `AB:CD:EF:01:23:45:67:89`.
pub fn fingerprint_pubkey(public_key: &[u8]) -> String {
    let h = compute_sha3_256(public_key);
    h[..8].iter().map(|b| format!("{:02X}", b)).collect::<Vec<_>>().join(":")
}
