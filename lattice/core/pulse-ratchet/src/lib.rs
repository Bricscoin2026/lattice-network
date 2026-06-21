//! Lattice Network — Pulse Ratchet.
//!
//! PQXDH (Post-Quantum X3DH) + Double Ratchet sealed-sender session
//! layer for the Pulse Messenger. Mirrors the Signal-style key
//! agreement but the long-term and ephemeral KEM legs are
//! upgraded to **ML-KEM-768** (FIPS 203). Identity authentication
//! remains on **ML-DSA-65** (FIPS 204).
//!
//! This crate intentionally only carries the *protocol state*
//! types and the *key derivation* glue. The actual AEAD body
//! sealing is handled by `pulse-protocol::PulseEngine`.

use lattice_crypto::{
    compute_sha3_256, compute_sha3_512, fingerprint_pubkey,
    LatticeKemKeyPair, LatticeKeyPair,
};
use serde::{Serialize, Deserialize};
use sha3::{Digest, Sha3_256};

// ---------------------------------------------------------------------------
// PQXDH — pre-key bundle (published on the Lattice ledger by the
// recipient at registration time).
// ---------------------------------------------------------------------------

/// The pre-key bundle a peer publishes so others can open a sealed
/// session against them without further round-trips.
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct PreKeyBundle {
    /// Long-term ML-DSA-65 identity public key.
    pub identity_dsa_pk: Vec<u8>,
    /// Long-term ML-KEM-768 public key (signed by `identity_dsa_pk`).
    pub identity_kem_pk: Vec<u8>,
    /// ML-DSA-65 detached signature of `identity_kem_pk`.
    pub identity_kem_pk_sig: Vec<u8>,
    /// One-time ML-KEM-768 prekey (single-use).
    pub one_time_kem_pk: Vec<u8>,
    /// Optional one-time prekey id (so the recipient can throw it
    /// away after first use).
    pub one_time_kem_pk_id: u64,
}

/// Local KEM material that backs a `PreKeyBundle`.
pub struct PreKeySecrets {
    pub identity_dsa: LatticeKeyPair,
    pub identity_kem: LatticeKemKeyPair,
    pub one_time_kem: LatticeKemKeyPair,
    pub one_time_kem_id: u64,
}

impl PreKeySecrets {
    /// Generate a fresh local pre-key bundle. The `identity_kem_pk`
    /// is signed by `identity_dsa` so peers can verify provenance.
    pub fn generate(one_time_kem_id: u64) -> (Self, PreKeyBundle) {
        let dsa = LatticeKeyPair::generate_pqc_identity();
        let kem = LatticeKemKeyPair::generate_kem_identity();
        let ot = LatticeKemKeyPair::generate_kem_identity();
        let sig = dsa.sign_data(&kem.public_key);
        let bundle = PreKeyBundle {
            identity_dsa_pk: dsa.public_key.clone(),
            identity_kem_pk: kem.public_key.clone(),
            identity_kem_pk_sig: sig,
            one_time_kem_pk: ot.public_key.clone(),
            one_time_kem_pk_id: one_time_kem_id,
        };
        (
            Self {
                identity_dsa: dsa,
                identity_kem: kem,
                one_time_kem: ot,
                one_time_kem_id,
            },
            bundle,
        )
    }
}

// ---------------------------------------------------------------------------
// PQXDH — initial session derivation
// ---------------------------------------------------------------------------

/// The KEM ciphertexts the sender ships in the first sealed
/// envelope (`InitialMessage` in Signal nomenclature).
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct InitialKemCiphers {
    pub ct_to_identity_kem: Vec<u8>,
    pub ct_to_one_time_kem: Vec<u8>,
    pub ephemeral_kem_pk: Vec<u8>,
}

/// Derive the initial root key from the three concatenated KEM
/// shared secrets (HKDF-style with SHA3-512 KDF).
pub fn kdf_initial_root_key(
    ss_id_kem: &[u8; 32],
    ss_ot_kem: &[u8; 32],
    ss_eph: &[u8; 32],
    associated_data: &[u8],
) -> [u8; 64] {
    let mut h = sha3::Sha3_512::new();
    h.update(b"LATTICE-PQXDH-v1");
    h.update(ss_id_kem);
    h.update(ss_ot_kem);
    h.update(ss_eph);
    h.update(associated_data);
    let mut out = [0u8; 64];
    out.copy_from_slice(&h.finalize());
    out
}

// ---------------------------------------------------------------------------
// Double Ratchet
// ---------------------------------------------------------------------------

/// Direction of a Double Ratchet chain.
#[derive(Debug, Serialize, Deserialize, Clone, Copy, PartialEq, Eq)]
pub enum ChainDirection { Sending, Receiving }

/// One side of a Double Ratchet chain state.
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ChainState {
    pub direction: ChainDirection,
    pub chain_key: [u8; 32],
    pub message_number: u64,
}

impl ChainState {
    /// Advance the chain key one step and emit a message key
    /// (SHA3-256(chain_key || 0x01) → message_key; chain_key :=
    /// SHA3-256(chain_key || 0x02)).
    pub fn step(&mut self) -> [u8; 32] {
        let mut h = Sha3_256::new();
        h.update(self.chain_key);
        h.update([0x01]);
        let mk = h.finalize();
        let mut msg_key = [0u8; 32];
        msg_key.copy_from_slice(&mk);

        let mut h2 = Sha3_256::new();
        h2.update(self.chain_key);
        h2.update([0x02]);
        let ck = h2.finalize();
        self.chain_key.copy_from_slice(&ck);

        self.message_number += 1;
        msg_key
    }
}

/// The full Double Ratchet state for a sealed-sender session.
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct RatchetState {
    pub root_key: [u8; 64],
    pub sending: ChainState,
    pub receiving: ChainState,
    /// Number of messages sent in the previous sending chain (so
    /// the receiver can resolve out-of-order delivery).
    pub previous_sending_length: u64,
    /// Total DH-ratchet epochs elapsed since session start.
    pub epoch: u64,
    /// Cached human-readable session fingerprint (SAS).
    pub fingerprint: String,
}

impl RatchetState {
    /// Initialise a new Double Ratchet state from a derived
    /// initial root key and a deterministic split into a sending
    /// and a receiving chain key.
    pub fn init(root_key: [u8; 64], initiator: bool, peer_identity_pk: &[u8], local_identity_pk: &[u8]) -> Self {
        let mut split_send = compute_sha3_256(&{
            let mut v = root_key.to_vec();
            v.extend_from_slice(b"|chain-send");
            v
        });
        let mut split_recv = compute_sha3_256(&{
            let mut v = root_key.to_vec();
            v.extend_from_slice(b"|chain-recv");
            v
        });
        if !initiator {
            std::mem::swap(&mut split_send, &mut split_recv);
        }
        let mut sas_input = Vec::new();
        sas_input.extend_from_slice(&root_key);
        // Canonicalise peer order so both sides compute the same SAS.
        if local_identity_pk <= peer_identity_pk {
            sas_input.extend_from_slice(local_identity_pk);
            sas_input.extend_from_slice(peer_identity_pk);
        } else {
            sas_input.extend_from_slice(peer_identity_pk);
            sas_input.extend_from_slice(local_identity_pk);
        }
        let sas = fingerprint_pubkey(&sas_input);

        Self {
            root_key,
            sending: ChainState { direction: ChainDirection::Sending, chain_key: split_send, message_number: 0 },
            receiving: ChainState { direction: ChainDirection::Receiving, chain_key: split_recv, message_number: 0 },
            previous_sending_length: 0,
            epoch: 1,
            fingerprint: sas,
        }
    }

    /// Advance the DH-ratchet (called when a fresh ephemeral KEM
    /// public key arrives from the peer). Bumps the epoch and
    /// re-splits the root key from a fresh KEM shared secret.
    pub fn dh_ratchet_step(&mut self, fresh_kem_shared_secret: &[u8; 32]) {
        let mut buf = Vec::with_capacity(64 + 32);
        buf.extend_from_slice(&self.root_key);
        buf.extend_from_slice(fresh_kem_shared_secret);
        let new_rk = compute_sha3_512(&buf);
        self.previous_sending_length = self.sending.message_number;
        self.root_key = new_rk;
        let split_send = compute_sha3_256(&{
            let mut v = self.root_key.to_vec();
            v.extend_from_slice(b"|chain-send|epoch");
            v.extend_from_slice(&(self.epoch + 1).to_be_bytes());
            v
        });
        let split_recv = compute_sha3_256(&{
            let mut v = self.root_key.to_vec();
            v.extend_from_slice(b"|chain-recv|epoch");
            v.extend_from_slice(&(self.epoch + 1).to_be_bytes());
            v
        });
        self.sending = ChainState { direction: ChainDirection::Sending, chain_key: split_send, message_number: 0 };
        self.receiving = ChainState { direction: ChainDirection::Receiving, chain_key: split_recv, message_number: 0 };
        self.epoch += 1;
    }

    /// Produce the next message key on the sending chain.
    pub fn next_send_key(&mut self) -> [u8; 32] {
        self.sending.step()
    }
}
