//! Lattice Network — Pulse Protocol.
//!
//! Sealed-sender onion-encrypted chat transport with a SHA3-256
//! proof-of-work admission control. AES-256-GCM (NIST SP 800-38D)
//! is used for the inner session leg.

use aes_gcm::{Aes256Gcm, Key, Nonce};
use aes_gcm::aead::{Aead, KeyInit};
use sha3::{Digest, Sha3_256};
use serde::{Serialize, Deserialize};

/// A sealed-sender packet bound for an LNS destination. The
/// `encrypted_onion_payload` is the outer-most layer of the onion
/// envelope; intermediate relays peel one layer per hop.
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SealedSenderPacket {
    pub destination_lns: String,
    pub encrypted_onion_payload: Vec<u8>,
    pub ephemeral_nonce: [u8; 12],
}

/// Per-session AEAD engine.
pub struct PulseEngine {
    pub session_key: [u8; 32],
}

impl PulseEngine {
    /// Initialise the engine with a pre-shared (or KEM-derived)
    /// 256-bit session key.
    pub fn new(key: [u8; 32]) -> Self {
        Self { session_key: key }
    }

    /// AES-256-GCM seal of `plaintext` under `nonce_bytes`.
    pub fn encrypt_chat(&self, plaintext: &[u8], nonce_bytes: &[u8; 12]) -> Vec<u8> {
        let key = Key::<Aes256Gcm>::from_slice(&self.session_key);
        let cipher = Aes256Gcm::new(key);
        let nonce = Nonce::from_slice(nonce_bytes);
        cipher.encrypt(nonce, plaintext).expect("Encryption Failure")
    }

    /// AES-256-GCM open of `ciphertext` under `nonce_bytes`.
    pub fn decrypt_chat(&self, ciphertext: &[u8], nonce_bytes: &[u8; 12]) -> Vec<u8> {
        let key = Key::<Aes256Gcm>::from_slice(&self.session_key);
        let cipher = Aes256Gcm::new(key);
        let nonce = Nonce::from_slice(nonce_bytes);
        cipher.decrypt(nonce, ciphertext).expect("Decryption Failure")
    }

    /// Verify a client-side proof-of-work admission token. Returns
    /// `true` iff `SHA3-256(challenge || nonce_be)` has at least
    /// `difficulty` leading zero bits.
    pub fn verify_client_pow(challenge: &[u8], nonce: u64, difficulty: usize) -> bool {
        let mut hasher = Sha3_256::new();
        hasher.update(challenge);
        hasher.update(nonce.to_be_bytes());
        let result = hasher.finalize();
        let mut zero_bits = 0usize;
        for &byte in result.iter() {
            if byte == 0 {
                zero_bits += 8;
            } else {
                zero_bits += byte.leading_zeros() as usize;
                break;
            }
        }
        zero_bits >= difficulty
    }
}
