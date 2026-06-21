//! Lattice Network — Sovereign tokenless ledger node (Substrate-style).
//!
//! Block model loosely modelled on the Substrate frame primitives:
//! every block carries a `BlockHeader` (parent_hash, state_root,
//! extrinsics_root, digest log), a vector of `Extrinsic`s with
//! sender nonces and pre-computed weights, and a vector of `Event`s
//! emitted as a side-effect of extrinsic execution. The
//! `extrinsics_root` is a SHA3-512 Merkle root over the canonical
//! serialisation of each extrinsic.

use lattice_crypto::{verify_pqc_signature, compute_sha3_512};
use serde::{Serialize, Deserialize};
use std::collections::HashMap;

// ---------------------------------------------------------------------------
// Call dispatch & payload
// ---------------------------------------------------------------------------

/// Discriminated union of sovereign on-chain calls.
#[derive(Debug, Serialize, Deserialize, Clone)]
pub enum TransactionPayload {
    IdentityRegister { lns_name: String, did: String, public_key: Vec<u8> },
    NotarySeal { doc_hash: [u8; 64], metadata: String },
    IdentityRevoke { lns_name: String },
    /// Anchors a sealed Pulse conversation segment on-chain.
    PulseAnchor { conv_id: String, message_count: u64, anchor_hash: [u8; 64] },
}

/// A PQC-signed sovereign extrinsic (Substrate's `UncheckedExtrinsic`
/// equivalent).
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Transaction {
    pub payload: TransactionPayload,
    pub sender_public_key: Vec<u8>,
    pub signature: Vec<u8>,
    /// Anti-replay sender nonce.
    pub nonce: u64,
    /// Pre-computed weight (frame_support style).
    pub weight: u64,
}

// ---------------------------------------------------------------------------
// Events
// ---------------------------------------------------------------------------

/// Side-effects emitted by the runtime as it executes extrinsics.
#[derive(Debug, Serialize, Deserialize, Clone)]
pub enum Event {
    IdentityRegistered { lns_name: String },
    IdentityRevoked { lns_name: String },
    NotarySealed { doc_hash: [u8; 64] },
    PulseAnchored { conv_id: String, message_count: u64 },
    BlockFinalised { block_hash: [u8; 64] },
}

// ---------------------------------------------------------------------------
// Block header & block
// ---------------------------------------------------------------------------

/// Substrate-style block header.
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct BlockHeader {
    pub number: u64,
    pub parent_hash: [u8; 64],
    pub state_root: [u8; 64],
    pub extrinsics_root: [u8; 64],
    /// Free-form digest log (consensus engine items, justifications,
    /// etc.). We carry it as opaque bytes for forward-compatibility.
    pub digest: Vec<u8>,
}

/// A finalised block on the sovereign chain.
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Block {
    pub header: BlockHeader,
    pub index: u64,
    pub timestamp: i64,
    pub transactions: Vec<Transaction>,
    pub events: Vec<Event>,
    pub previous_hash: [u8; 64],
    pub block_hash: [u8; 64],
    pub weight_used: u64,
    pub proposer: String,
}

// ---------------------------------------------------------------------------
// Chain state
// ---------------------------------------------------------------------------

/// The local view of the sovereign chain (QBFT-finalised upstream).
pub struct SovereignChain {
    pub chain: Vec<Block>,
    pub pending_transactions: Vec<Transaction>,
    /// Anti-replay nonce tracking per sender public key fingerprint.
    pub nonces: HashMap<Vec<u8>, u64>,
    /// Maximum total weight allowed per finalised block.
    pub max_block_weight: u64,
}

impl Default for SovereignChain {
    fn default() -> Self { Self::new() }
}

impl SovereignChain {
    /// Initialise with a deterministic genesis block.
    pub fn new() -> Self {
        let genesis_header = BlockHeader {
            number: 0,
            parent_hash: [0u8; 64],
            state_root: [0u8; 64],
            extrinsics_root: [0u8; 64],
            digest: Vec::new(),
        };
        let genesis_block = Block {
            header: genesis_header,
            index: 0,
            timestamp: 1717416000,
            transactions: vec![],
            events: vec![Event::BlockFinalised { block_hash: [0u8; 64] }],
            previous_hash: [0u8; 64],
            block_hash: [0u8; 64],
            weight_used: 0,
            proposer: "GENESIS".to_string(),
        };
        Self {
            chain: vec![genesis_block],
            pending_transactions: Vec::new(),
            nonces: HashMap::new(),
            max_block_weight: 5_000_000,
        }
    }

    /// Verify a transaction's PQC signature, enforce the sender
    /// nonce monotonicity, and enqueue the extrinsic for the next
    /// QBFT round.
    pub fn submit_transaction(&mut self, tx: Transaction) -> Result<(), &'static str> {
        let serialized = serde_json::to_vec(&tx.payload)
            .map_err(|_| "Serialization Failure")?;
        if !verify_pqc_signature(&serialized, &tx.signature, &tx.sender_public_key) {
            return Err("Invalid PQC Signature");
        }
        let expected = self.nonces.get(&tx.sender_public_key).copied().unwrap_or(0);
        if tx.nonce != expected {
            return Err("Invalid sender nonce");
        }
        self.nonces.insert(tx.sender_public_key.clone(), expected + 1);
        self.pending_transactions.push(tx);
        Ok(())
    }

    /// Compute the SHA3-512 Merkle root of an ordered list of
    /// extrinsics. We use a simple binary tree with duplicated
    /// last leaf if the count is odd.
    pub fn compute_extrinsics_root(txs: &[Transaction]) -> [u8; 64] {
        if txs.is_empty() {
            return [0u8; 64];
        }
        let mut layer: Vec<[u8; 64]> = txs
            .iter()
            .map(|t| {
                let serialised = serde_json::to_vec(t).unwrap_or_default();
                compute_sha3_512(&serialised)
            })
            .collect();
        while layer.len() > 1 {
            if layer.len() % 2 == 1 {
                let last = *layer.last().unwrap();
                layer.push(last);
            }
            let mut next: Vec<[u8; 64]> = Vec::with_capacity(layer.len() / 2);
            for pair in layer.chunks(2) {
                let mut buf = [0u8; 128];
                buf[..64].copy_from_slice(&pair[0]);
                buf[64..].copy_from_slice(&pair[1]);
                next.push(compute_sha3_512(&buf));
            }
            layer = next;
        }
        layer[0]
    }

    /// Drain the mempool into a freshly finalised block. The
    /// `extrinsics_root` is the SHA3-512 Merkle root over the
    /// included extrinsics; events are emitted by replaying each
    /// payload against the runtime.
    pub fn process_block(&mut self) {
        let last_block = self.chain.last().expect("genesis must exist").clone();
        let mut events: Vec<Event> = Vec::new();
        let mut weight_used: u64 = 0;
        let mut included: Vec<Transaction> = Vec::new();

        for tx in self.pending_transactions.drain(..) {
            if weight_used.saturating_add(tx.weight) > self.max_block_weight {
                break;
            }
            weight_used += tx.weight;
            match &tx.payload {
                TransactionPayload::IdentityRegister { lns_name, .. } => {
                    events.push(Event::IdentityRegistered { lns_name: lns_name.clone() });
                }
                TransactionPayload::IdentityRevoke { lns_name } => {
                    events.push(Event::IdentityRevoked { lns_name: lns_name.clone() });
                }
                TransactionPayload::NotarySeal { doc_hash, .. } => {
                    events.push(Event::NotarySealed { doc_hash: *doc_hash });
                }
                TransactionPayload::PulseAnchor { conv_id, message_count, .. } => {
                    events.push(Event::PulseAnchored {
                        conv_id: conv_id.clone(),
                        message_count: *message_count,
                    });
                }
            }
            included.push(tx);
        }

        let extrinsics_root = Self::compute_extrinsics_root(&included);
        let state_root = compute_sha3_512(&serde_json::to_vec(&self.nonces).unwrap_or_default());

        let mut header = BlockHeader {
            number: last_block.index + 1,
            parent_hash: last_block.block_hash,
            state_root,
            extrinsics_root,
            digest: Vec::new(),
        };

        // Digest log: opaque consensus engine bytes (QBFT round id).
        header.digest.extend_from_slice(b"qbft:");
        header.digest.extend_from_slice(&header.number.to_be_bytes());

        let mut new_block = Block {
            header: header.clone(),
            index: last_block.index + 1,
            timestamp: 1717416001,
            transactions: included,
            events,
            previous_hash: last_block.block_hash,
            block_hash: [0u8; 64],
            weight_used,
            proposer: "VAL-01".to_string(),
        };

        let serialized = serde_json::to_vec(&new_block)
            .expect("block must be serialisable");
        new_block.block_hash = compute_sha3_512(&serialized);
        new_block.events.push(Event::BlockFinalised { block_hash: new_block.block_hash });

        self.chain.push(new_block);
    }
}
