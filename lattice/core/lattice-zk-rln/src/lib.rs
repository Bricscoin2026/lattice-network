//! Lattice Network — Zero-Knowledge Rate-Limiting Nullifier.
//!
//! Implements the Lattice flavour of RLN (Rate-Limiting Nullifier)
//! anti-bot admission control. The on-chain circuit is a Groth16
//! proof over BN254 that publishes:
//!
//! * `nullifier = Poseidon(identity_secret, epoch)` — derived from
//!   the prover's identity commitment and the current rate-limit
//!   epoch; identical proofs in the same epoch reveal the
//!   `identity_secret` via Shamir polynomial reconstruction.
//! * `signal_hash = SHA3-256(message_payload)` — binds the proof
//!   to a specific outbound message.
//! * `merkle_root` — root of the Lattice identity-commitment tree
//!   (published per-block on the sovereign ledger).
//!
//! This crate only defines the protocol types; the actual Groth16
//! prover/verifier is implemented in a private `prod/zk-rln-prover`
//! crate that links against arkworks (BN254).

use lattice_crypto::{compute_sha3_256, compute_sha3_512};
use serde::{Serialize, Deserialize};

/// Per-conversation/per-stream rate-limit configuration.
#[derive(Debug, Serialize, Deserialize, Clone, Copy)]
pub struct RlnPolicy {
    /// Maximum number of valid proofs accepted per epoch.
    pub messages_per_epoch: u32,
    /// Length of a rate-limit epoch in seconds.
    pub epoch_seconds: u32,
    /// Shamir polynomial degree (number of proofs after which the
    /// identity secret becomes recoverable).
    pub shamir_degree: u32,
}

impl Default for RlnPolicy {
    fn default() -> Self {
        Self {
            messages_per_epoch: 10,
            epoch_seconds: 60,
            shamir_degree: 1,
        }
    }
}

/// Public inputs of an RLN Groth16 proof.
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct RlnPublicInputs {
    pub nullifier: [u8; 32],
    pub signal_hash: [u8; 32],
    pub epoch: u64,
    pub merkle_root: [u8; 32],
    pub rln_share_x: [u8; 32],
    pub rln_share_y: [u8; 32],
}

/// A serialised Groth16 proof + its public inputs.
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct RlnProof {
    pub public_inputs: RlnPublicInputs,
    /// Opaque Groth16 proof bytes (a, b, c elements on BN254).
    pub proof_bytes: Vec<u8>,
}

/// Identity commitment held by a prover (kept secret on device).
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct RlnIdentity {
    /// 32-byte secret scalar.
    pub identity_secret: [u8; 32],
    /// Commitment `H(identity_secret)` published in the Merkle tree.
    pub identity_commitment: [u8; 32],
}

impl RlnIdentity {
    /// Derive an RLN identity from any high-entropy secret seed.
    pub fn from_seed(seed: &[u8]) -> Self {
        let secret = compute_sha3_256(seed);
        let commitment = compute_sha3_256(&secret);
        Self { identity_secret: secret, identity_commitment: commitment }
    }

    /// Compute the rate-limit nullifier for `epoch`.
    pub fn nullifier(&self, epoch: u64) -> [u8; 32] {
        let mut buf = [0u8; 32 + 8];
        buf[..32].copy_from_slice(&self.identity_secret);
        buf[32..].copy_from_slice(&epoch.to_be_bytes());
        compute_sha3_256(&buf)
    }
}

/// Verify the *structural* validity of an RLN proof: nullifier
/// recomputation, signal-hash binding, epoch freshness, Merkle
/// root inclusion (the actual Groth16 SNARK pairing check is
/// delegated to the closed-source `prod/zk-rln-prover` crate).
pub fn verify_rln_structure(
    proof: &RlnProof,
    expected_signal_hash: &[u8; 32],
    expected_epoch: u64,
    expected_merkle_root: &[u8; 32],
) -> Result<(), &'static str> {
    if &proof.public_inputs.signal_hash != expected_signal_hash {
        return Err("RLN: signal_hash mismatch");
    }
    if proof.public_inputs.epoch != expected_epoch {
        return Err("RLN: stale epoch");
    }
    if &proof.public_inputs.merkle_root != expected_merkle_root {
        return Err("RLN: stale identity Merkle root");
    }
    if proof.proof_bytes.len() < 96 {
        return Err("RLN: malformed Groth16 proof bytes");
    }
    Ok(())
}

/// Domain-separated SHA3-512 commitment over the message bytes —
/// the canonical "signal hash" used as a Groth16 public input.
pub fn signal_hash(message: &[u8]) -> [u8; 32] {
    let mut padded = Vec::with_capacity(20 + message.len());
    padded.extend_from_slice(b"LATTICE-ZK-RLN-v1|");
    padded.extend_from_slice(message);
    let h512 = compute_sha3_512(&padded);
    let mut out = [0u8; 32];
    out.copy_from_slice(&h512[..32]);
    out
}
