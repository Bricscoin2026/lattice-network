//! Lattice — chain canonicalisation + QBFT finalisation.
//!
//! Native Rust port of `backend/chain.py` (M4 partial, started during M3).
//! Wire-compatible with the Python implementation byte-for-byte:
//! same canonical separators (`|`), same SHA3-256 leaf hash, same
//! SHA3-512 block-header hash, same JSON proposal format on the
//! `/qbft/sign-block` wire.

use std::time::Duration;

use anyhow::{anyhow, Result};
use bson::{doc, Document};
use chrono::{SecondsFormat, Utc};
use futures::future::join_all;
use mongodb::Database;
use serde::{Deserialize, Serialize};
use sha3::{Digest, Sha3_256, Sha3_512};
use tokio::sync::Mutex;
use tracing::warn;

use crate::crypto::pqc_verify;

pub const QBFT_TIMEOUT_MS: u64 = 800;

// A coarse mutex that serialises block proposals so we never insert
// two competing blocks at the same height. Same role as
// `chain.BLOCK_PROPOSAL_LOCK` on the Python side.
pub static BLOCK_LOCK: tokio::sync::Mutex<()> = Mutex::const_new(());

pub fn chain_id() -> String {
    std::env::var("LATTICE_CHAIN_ID")
        .unwrap_or_else(|_| "lattice-sovereign-it-prod".to_string())
}

pub fn utc_iso() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Micros, true)
}

// -- Canonical bytes --------------------------------------------------------

pub fn tx_canonical_message(tx_id: &str, block_index: i64, ts: &str, kind: &str, summary: &str) -> Vec<u8> {
    format!("{}|{}|{}|{}|{}", tx_id, block_index, ts, kind, summary).into_bytes()
}

pub fn block_canonical_message(b: &BuiltBlock) -> Vec<u8> {
    format!(
        "{}|{}|{}|{}|{}|{}|{}",
        b.chain_id, b.index, b.timestamp, b.previous_hash,
        b.merkle_root, b.transactions_count, b.block_hash,
    )
    .into_bytes()
}

// -- Hashing ----------------------------------------------------------------

pub fn merkle_root(leaves: &[String]) -> String {
    if leaves.is_empty() {
        return "0".repeat(64);
    }
    let mut level: Vec<Vec<u8>> = leaves
        .iter()
        .map(|h| hex::decode(h).unwrap_or_default())
        .collect();
    while level.len() > 1 {
        if level.len() % 2 == 1 {
            level.push(level.last().cloned().unwrap_or_default());
        }
        let mut nxt = Vec::with_capacity(level.len() / 2);
        for pair in level.chunks(2) {
            let mut h = Sha3_256::new();
            h.update(&pair[0]);
            h.update(&pair[1]);
            nxt.push(h.finalize().to_vec());
        }
        level = nxt;
    }
    hex::encode(&level[0])
}

pub fn tx_leaf_hash(tx_id: &str, kind: &str, doc_hash: &str, signer: &str, ts: &str) -> String {
    let payload = format!("{}|{}|{}|{}|{}", tx_id, kind, doc_hash, signer, ts);
    let mut h = Sha3_256::new();
    h.update(payload.as_bytes());
    hex::encode(h.finalize())
}

pub fn compute_block_hash(
    chain_id: &str,
    index: i64,
    timestamp: &str,
    previous_hash: &str,
    merkle_root_hex: &str,
    transactions_count: i64,
) -> String {
    let payload = format!(
        "{}|{}|{}|{}|{}|{}",
        chain_id, index, timestamp, previous_hash, merkle_root_hex, transactions_count
    );
    let mut h = Sha3_512::new();
    h.update(payload.as_bytes());
    hex::encode(h.finalize())
}

// -- Builder ----------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct TxLeaf {
    pub tx_id: String,
    pub kind: String,
    pub doc_hash: String,
    pub signer: String,
    pub timestamp: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct BuiltBlock {
    pub chain_id: String,
    pub index: i64,
    pub timestamp: String,
    pub previous_hash: String,
    pub merkle_root: String,
    pub transactions_count: i64,
    pub tx_ids: Vec<String>,
    pub block_hash: String,
}

pub fn build_signed_block(
    index: i64,
    timestamp: &str,
    previous_hash: &str,
    transactions: &[TxLeaf],
) -> BuiltBlock {
    let leaves: Vec<String> = transactions
        .iter()
        .map(|t| tx_leaf_hash(&t.tx_id, &t.kind, &t.doc_hash, &t.signer, &t.timestamp))
        .collect();
    let merkle = merkle_root(&leaves);
    let cid = chain_id();
    let count = transactions.len() as i64;
    let block_hash = compute_block_hash(&cid, index, timestamp, previous_hash, &merkle, count);
    BuiltBlock {
        chain_id: cid,
        index,
        timestamp: timestamp.to_string(),
        previous_hash: previous_hash.to_string(),
        merkle_root: merkle,
        transactions_count: count,
        tx_ids: transactions.iter().map(|t| t.tx_id.clone()).collect(),
        block_hash,
    }
}

// -- QBFT finalisation -----------------------------------------------------

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct QbftVote {
    pub validator_id: String,
    pub pk_fingerprint: String,
    pub signature_hex: String,
    #[serde(default)]
    pub signed_at: String,
    #[serde(default)]
    pub algorithm: String,
}

#[derive(Debug, Serialize)]
struct BlockProposalWire<'a> {
    index: i64,
    timestamp: &'a str,
    previous_hash: &'a str,
    block_hash: &'a str,
    merkle_root: &'a str,
    transactions_count: i64,
    chain_id: &'a str,
}

#[derive(Debug, Clone, Serialize)]
pub struct FinalisedBlock {
    pub chain_id: String,
    pub index: i64,
    pub timestamp: String,
    pub previous_hash: String,
    pub merkle_root: String,
    pub transactions_count: i64,
    pub tx_ids: Vec<String>,
    pub block_hash: String,
    pub proposer: String,
    pub proposer_signature: String,
    pub proposer_pk_fingerprint: String,
    pub signed_with: String,
    pub qbft_votes: Vec<QbftVote>,
    pub qbft_quorum: usize,
    pub qbft_total_validators: usize,
}

async fn fetch_validators(db: &Database) -> Result<Vec<(String, String)>> {
    use futures::StreamExt;
    use mongodb::options::FindOptions;
    let coll = db.collection::<Document>("qbft_registry");
    let opts = FindOptions::builder().sort(doc! {"validator_id": 1}).build();
    let mut cur = coll.find(doc! {}).with_options(opts).await?;
    let mut out = Vec::new();
    while let Some(d) = cur.next().await {
        let d = d?;
        let vid = d.get_str("validator_id").unwrap_or("?").to_string();
        let endpoint = d.get_str("endpoint").unwrap_or("").to_string();
        if !endpoint.is_empty() {
            out.push((vid, endpoint));
        }
    }
    Ok(out)
}

pub async fn qbft_finalise(
    db: &Database,
    http: &reqwest::Client,
    built: BuiltBlock,
) -> Result<FinalisedBlock> {
    let validators = fetch_validators(db).await?;
    if validators.is_empty() {
        return Err(anyhow!(
            "QBFT validator registry empty · refuse to publish block (security)"
        ));
    }
    let total = validators.len();
    let f = (total - 1) / 3;
    let quorum = 2 * f + 1;

    let proposal = BlockProposalWire {
        index: built.index,
        timestamp: &built.timestamp,
        previous_hash: &built.previous_hash,
        block_hash: &built.block_hash,
        merkle_root: &built.merkle_root,
        transactions_count: built.transactions_count,
        chain_id: &built.chain_id,
    };
    let proposal_json = serde_json::to_value(&proposal)?;

    // Concurrent ask to every validator with strict 800 ms budget.
    let tasks: Vec<_> = validators
        .iter()
        .map(|(_vid, endpoint)| {
            let url = format!("{}/qbft/sign-block", endpoint);
            let body = proposal_json.clone();
            let http = http.clone();
            async move {
                let res = tokio::time::timeout(
                    Duration::from_millis(QBFT_TIMEOUT_MS),
                    http.post(&url).json(&body).send(),
                )
                .await;
                match res {
                    Ok(Ok(resp)) if resp.status().is_success() => {
                        resp.json::<QbftVote>().await.ok()
                    }
                    _ => None,
                }
            }
        })
        .collect();
    let raw_votes: Vec<Option<QbftVote>> = join_all(tasks).await;

    // Verify each vote independently with PQC.
    let msg = block_canonical_message(&built);
    let mut seen: std::collections::HashSet<String> = Default::default();
    let mut votes: Vec<QbftVote> = Vec::new();
    for v in raw_votes.into_iter().flatten() {
        if seen.contains(&v.validator_id) {
            continue;
        }
        if pqc_verify(db, &v.validator_id, &msg, &v.signature_hex).await {
            seen.insert(v.validator_id.clone());
            votes.push(v);
        } else {
            warn!(validator = %v.validator_id, "QBFT signature verification FAILED — vote discarded");
        }
    }

    if votes.len() < quorum {
        return Err(anyhow!(
            "QBFT quorum not reached · need {} got {} of {}",
            quorum,
            votes.len(),
            total
        ));
    }

    let primary = votes[0].clone();
    Ok(FinalisedBlock {
        chain_id: built.chain_id,
        index: built.index,
        timestamp: built.timestamp,
        previous_hash: built.previous_hash,
        merkle_root: built.merkle_root,
        transactions_count: built.transactions_count,
        tx_ids: built.tx_ids,
        block_hash: built.block_hash,
        proposer: primary.validator_id,
        proposer_signature: primary.signature_hex,
        proposer_pk_fingerprint: primary.pk_fingerprint,
        signed_with: "ML-DSA-65".to_string(),
        qbft_quorum: quorum,
        qbft_total_validators: total,
        qbft_votes: votes,
    })
}

// -- End-to-end: build, finalise, insert ------------------------------------

pub async fn finalise_block_for_tx(
    db: &Database,
    http: &reqwest::Client,
    tx_id: &str,
    kind: &str,
    doc_hash: &str,
    signer: &str,
    timestamp: &str,
) -> Result<FinalisedBlock> {
    let _guard = BLOCK_LOCK.lock().await;
    finalise_block_for_tx_locked(db, http, tx_id, kind, doc_hash, signer, timestamp).await
}

/// Same as `finalise_block_for_tx` but the caller already holds
/// `BLOCK_LOCK`. Use when you need to know the real `effective_index`
/// BEFORE the block is built (e.g. lead capture signs the TX over it).
pub async fn finalise_block_for_tx_locked(
    db: &Database,
    http: &reqwest::Client,
    tx_id: &str,
    kind: &str,
    doc_hash: &str,
    signer: &str,
    timestamp: &str,
) -> Result<FinalisedBlock> {
    let blocks = db.collection::<Document>("blocks");
    let prev = blocks
        .find_one(doc! {})
        .sort(doc! {"index": -1})
        .projection(doc! {"_id": 0, "block_hash": 1, "index": 1})
        .await?;
    let (prev_hash, effective_index) = match prev {
        Some(p) => {
            let h = p.get_str("block_hash").unwrap_or(&"0".repeat(128)).to_string();
            let i = p.get_i64("index").unwrap_or_else(|_| p.get_i32("index").unwrap_or(0) as i64);
            (h, i + 1)
        }
        None => ("0".repeat(128), 1),
    };

    let built = build_signed_block(
        effective_index,
        timestamp,
        &prev_hash,
        &[TxLeaf {
            tx_id: tx_id.to_string(),
            kind: kind.to_string(),
            doc_hash: doc_hash.to_string(),
            signer: signer.to_string(),
            timestamp: timestamp.to_string(),
        }],
    );

    let finalised = qbft_finalise(db, http, built).await?;
    let doc = bson::to_document(&finalised)?;
    blocks.insert_one(doc).await?;
    Ok(finalised)
}

/// Read-only peek at the index the next block will get. Caller MUST
/// hold `BLOCK_LOCK` for this to be race-free.
pub async fn peek_next_block_index(db: &Database) -> Result<i64> {
    let prev = db.collection::<Document>("blocks")
        .find_one(doc! {})
        .sort(doc! {"index": -1})
        .projection(doc! {"_id": 0, "index": 1})
        .await?;
    Ok(prev
        .as_ref()
        .map(|p| {
            p.get_i64("index").ok()
                .or_else(|| p.get_i32("index").ok().map(|v| v as i64))
                .unwrap_or(0)
                + 1
        })
        .unwrap_or(1))
}

/// Like `finalise_block_for_tx_locked` but packs multiple TXs into a
/// single block (used by bulk admin operations / seed-demo).
pub async fn finalise_batch_block_locked(
    db: &Database,
    http: &reqwest::Client,
    transactions: Vec<TxLeaf>,
) -> Result<FinalisedBlock> {
    if transactions.is_empty() {
        return Err(anyhow!("transactions list cannot be empty"));
    }
    let blocks = db.collection::<Document>("blocks");
    let prev = blocks
        .find_one(doc! {})
        .sort(doc! {"index": -1})
        .projection(doc! {"_id": 0, "block_hash": 1, "index": 1})
        .await?;
    let (prev_hash, effective_index) = match prev {
        Some(p) => {
            let h = p.get_str("block_hash").unwrap_or(&"0".repeat(128)).to_string();
            let i = p.get_i64("index").unwrap_or_else(|_| p.get_i32("index").unwrap_or(0) as i64);
            (h, i + 1)
        }
        None => ("0".repeat(128), 1),
    };
    let ts = transactions
        .first()
        .map(|t| t.timestamp.clone())
        .unwrap_or_else(utc_iso);
    let built = build_signed_block(effective_index, &ts, &prev_hash, &transactions);
    let finalised = qbft_finalise(db, http, built).await?;
    let doc = bson::to_document(&finalised)?;
    blocks.insert_one(doc).await?;
    Ok(finalised)
}
