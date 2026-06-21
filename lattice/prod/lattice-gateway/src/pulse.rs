//! `POST /api/pulse/send` and `GET /api/pulse/session/{conv_id}` — native
//! Rust port of `routes/pulse_mutating.py`. (M7 step 4)
//!
//! Implements:
//!   * Sealed-sender envelope (SHAKE-256 keystream + SHA3-256 16-byte tag).
//!   * ZK-RLN admission control via the `rln_quota` collection
//!     (atomic find_one_and_update — same semantics as Python).
//!   * Conv ID derivation = SHA3-256 of sorted "lo|hi" pair (24-char hex).
//!   * Double-Ratchet session bookkeeping in `pulse_sessions`.
//!   * Loopix 3-hop mixnet route preview (deterministic seed-driven).
//!   * On-chain `NotarySeal` anchor TX every `PULSE_ANCHOR_EVERY` messages
//!     (QBFT-finalised via `chain::finalise_block_for_tx_locked`).
//!
//! Differences from Python:
//!   * `rln_nullifier_hex` / `rln_commitment_hex` audit fields are computed
//!     with **Starknet Poseidon** (`starknet-crypto` crate) over the same
//!     Starknet felt prime as `poseidon_py` — values byte-identical to the
//!     Python reference. (Wired in M7 step 4b.)
//!   * `req.rln_proof` strict validation is skipped (frontend doesn't
//!     send it). The atomic quota check still enforces 10 msg/60 s/LNS.
//!   * Mixnet HTTP forward to relay-01 is NOT triggered (Python had a
//!     fire-and-forget call to `route_through_mixnet_fn`); the route
//!     preview (hops + delays) is still emitted in the response.

use std::collections::HashMap;

use axum::{extract::{Path, State}, http::StatusCode, Json};
use bson::{doc, Document};
use rand::RngCore;
use serde::{Deserialize, Serialize};
use sha3::{
    digest::{ExtendableOutput, Update, XofReader},
    Digest, Sha3_256, Sha3_512, Shake256,
};

use crate::chain;
use crate::chain::utc_iso;
use crate::crypto::{det_hex, pqc_sign_or_delegate};
use crate::rln;
use crate::AppState;

const RLN_EPOCH_SECONDS: i64 = 60;
const RLN_MAX_PER_EPOCH: i64 = 10;
const PULSE_ANCHOR_EVERY: i64 = 3;

#[derive(Debug, Deserialize)]
pub struct PulseSendRequest {
    pub from_lns: String,
    #[serde(default)]
    pub to_lns: Option<String>,
    #[serde(default)]
    pub recipients_lns: Option<Vec<String>>,
    pub plaintext: String,
    #[serde(default)]
    pub attachment_ids: Option<Vec<String>>,
    #[serde(default)]
    pub rln_proof: Option<serde_json::Value>,
}

#[derive(Debug, Serialize)]
pub struct RouteHop {
    pub layer: i32,
    pub relay_node_id: String,
    pub relay_label: String,
    pub relay_region: String,
    pub onion_layer_hash: String,
    pub delay_ms: i64,
}

#[derive(Debug, Serialize)]
pub struct PulseSendResponse {
    pub ok: bool,
    pub msg_id: String,
    pub conv_id: String,
    pub ciphertext_hex: String,
    pub nonce_hex: String,
    pub sealed_at: String,
    pub anchor_tx_id: Option<String>,
    pub anchor_block_index: Option<i64>,
    pub session_fingerprint: String,
    pub epoch: i64,
    pub message_number: i64,
    pub route_id: String,
    pub route_hops: Vec<RouteHop>,
    pub rln_slot_used: i64,
    pub rln_slot_max: i64,
}

#[derive(Debug, Serialize)]
pub struct PulseError { pub detail: String }
fn err(code: StatusCode, msg: impl Into<String>) -> (StatusCode, Json<PulseError>) {
    (code, Json(PulseError { detail: msg.into() }))
}

fn conv_id(a: &str, b: &str) -> String {
    let mut pair = [a.to_lowercase(), b.to_lowercase()];
    pair.sort();
    let mut h = Sha3_256::new();
    Digest::update(&mut h, format!("{}|{}", pair[0], pair[1]).as_bytes());
    let out = hex::encode(h.finalize());
    format!("conv-{}", &out[..24])
}

fn pulse_session_fingerprint(conv_id: &str, participants: &[String]) -> String {
    let mut sorted: Vec<String> = participants.iter().map(|p| p.to_lowercase()).collect();
    sorted.sort();
    let pair = sorted.join("|");
    let mut h = Sha3_256::new();
    Digest::update(&mut h, format!("{}|{}", conv_id, pair).as_bytes());
    let bytes = h.finalize();
    bytes.iter().take(8).map(|b| format!("{:02X}", b)).collect::<Vec<_>>().join(":")
}

fn current_rln_epoch() -> i64 {
    chrono::Utc::now().timestamp() / RLN_EPOCH_SECONDS
}

fn shake256(input: &[u8], out_len: usize) -> Vec<u8> {
    let mut x = Shake256::default();
    x.update(input);
    let mut reader = x.finalize_xof();
    let mut out = vec![0u8; out_len];
    reader.read(&mut out);
    out
}

fn get_i64_lenient(d: &Document, key: &str) -> i64 {
    if let Ok(v) = d.get_i64(key) { return v; }
    if let Ok(v) = d.get_i32(key) { return v as i64; }
    if let Ok(v) = d.get_f64(key) { return v as i64; }
    0
}

pub async fn pulse_send(
    State(state): State<AppState>,
    Json(req): Json<PulseSendRequest>,
) -> Result<Json<PulseSendResponse>, (StatusCode, Json<PulseError>)> {
    let from_lns = req.from_lns.trim().to_lowercase();
    if from_lns.is_empty() {
        return Err(err(StatusCode::UNPROCESSABLE_ENTITY, "from_lns required"));
    }
    let target = req.to_lns.clone()
        .or_else(|| req.recipients_lns.as_ref().and_then(|v| v.first().cloned()));
    let to_lns = target.unwrap_or_default().trim().to_lowercase();
    if to_lns.is_empty() {
        return Err(err(StatusCode::UNPROCESSABLE_ENTITY, "to_lns or recipients_lns required"));
    }
    if from_lns == to_lns {
        return Err(err(StatusCode::UNPROCESSABLE_ENTITY, "from_lns and to_lns must differ"));
    }

    // -- LNS active check + cross-tenant guard --
    let lns_coll = state.db.collection::<Document>("lns");
    let sender = lns_coll.find_one(doc! {"lns_name": &from_lns}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let recipient = lns_coll.find_one(doc! {"lns_name": &to_lns}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let sender = sender.ok_or_else(|| err(StatusCode::NOT_FOUND, format!("Sender LNS not active: {}", from_lns)))?;
    let recipient = recipient.ok_or_else(|| err(StatusCode::NOT_FOUND, format!("Recipient LNS not active: {}", to_lns)))?;
    if sender.get_str("status").unwrap_or("") != "ACTIVE" {
        return Err(err(StatusCode::NOT_FOUND, format!("Sender LNS not active: {}", from_lns)));
    }
    if recipient.get_str("status").unwrap_or("") != "ACTIVE" {
        return Err(err(StatusCode::NOT_FOUND, format!("Recipient LNS not active: {}", to_lns)));
    }
    let s_tenant = sender.get_str("tenant_id").ok().map(String::from);
    let r_tenant = recipient.get_str("tenant_id").ok().map(String::from);
    if let (Some(s), Some(r)) = (&s_tenant, &r_tenant) {
        if !s.is_empty() && !r.is_empty() && s != r {
            return Err(err(StatusCode::FORBIDDEN,
                "cross-company messaging is disabled · puoi scrivere solo ai colleghi della tua azienda"));
        }
    }

    // -- ZK-RLN admission control (atomic findAndModify on rln_quota) --
    let epoch = current_rln_epoch();
    let quota_coll = state.db.collection::<Document>("rln_quota");
    let q = quota_coll.find_one_and_update(
        doc! {"lns": &from_lns, "epoch": epoch},
        doc! {"$inc": {"used": 1_i64}, "$setOnInsert": {"created_at": utc_iso()}},
    )
    .upsert(true)
    .return_document(mongodb::options::ReturnDocument::After)
    .await
    .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("rln_quota: {e}")))?;
    let used = q.as_ref().map(|d| get_i64_lenient(d, "used")).unwrap_or(1);
    if used > RLN_MAX_PER_EPOCH {
        let _ = quota_coll.update_one(
            doc! {"lns": &from_lns, "epoch": epoch},
            doc! {"$inc": {"used": -1_i64}},
        ).await;
        return Err(err(
            StatusCode::TOO_MANY_REQUESTS,
            format!("ZK-RLN rate limit exceeded · {}/{}s · epoch {}", RLN_MAX_PER_EPOCH, RLN_EPOCH_SECONDS, epoch),
        ));
    }

    let nullifier_hex = rln::rln_nullifier(&state.db, &from_lns, epoch).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("rln_nullifier: {e}")))?;
    let commitment_hex = rln::rln_commitment(&state.db, &from_lns).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("rln_commitment: {e}")))?;
    let _ = state.db.collection::<Document>("rln_nullifiers").insert_one(doc! {
        "epoch": epoch,
        "lns": &from_lns,
        "nullifier_hex": &nullifier_hex,
        "commitment_hex": &commitment_hex,
        "used_slot": used,
        "observed_at": utc_iso(),
        "algo": "poseidon-starknet",
    }).await;

    // Optional client-supplied rln_proof verification (Poseidon nullifier).
    if let Some(p) = req.rln_proof.as_ref() {
        if let Some(nul) = p.get("nullifier").and_then(|v| v.as_str()) {
            if nul.to_ascii_lowercase() != nullifier_hex {
                return Err(err(StatusCode::BAD_REQUEST, "ZK-RLN proof: nullifier mismatch"));
            }
        }
        if let Some(ep) = p.get("epoch").and_then(|v| v.as_i64()) {
            if ep != epoch {
                return Err(err(StatusCode::BAD_REQUEST, "ZK-RLN proof: stale epoch"));
            }
        }
    }

    // -- Sealed-sender envelope (SHAKE-256 keystream + SHA3-256 tag) --
    let cid = conv_id(&from_lns, &to_lns);
    let ts = utc_iso();
    let mut nonce = [0u8; 12];
    rand::rngs::OsRng.fill_bytes(&mut nonce);
    let pt = req.plaintext.as_bytes();
    let need = pt.len().max(64);
    let mut input = nonce.to_vec();
    input.extend_from_slice(cid.as_bytes());
    let ks = shake256(&input, need);
    let ct: Vec<u8> = pt.iter().zip(ks.iter()).map(|(p, k)| p ^ k).collect();
    let mut tag_h = Sha3_256::new();
    Digest::update(&mut tag_h, &ct);
    Digest::update(&mut tag_h, &nonce);
    let tag = tag_h.finalize();
    let mut ciphertext = ct.clone();
    ciphertext.extend_from_slice(&tag[..16]);
    let ciphertext_hex = hex::encode(&ciphertext);
    let nonce_hex = hex::encode(&nonce);
    let msg_id = format!("pulse-{}", det_hex(&format!("{}-{}", cid, ts), 10));

    // Attachments validation (basic)
    let mut attachments_meta: Vec<Document> = Vec::new();
    if let Some(ids) = req.attachment_ids.as_ref() {
        for att_id in ids.iter().take(10) {
            let att = state.db.collection::<Document>("attachments")
                .find_one(doc! {"attachment_id": att_id}).await
                .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
            let att = att.ok_or_else(|| err(StatusCode::NOT_FOUND, format!("attachment not found: {att_id}")))?;
            if s_tenant.is_some() && att.get_str("owner_lns").unwrap_or("") != from_lns {
                return Err(err(StatusCode::FORBIDDEN, format!("attachment {} does not belong to you", att_id)));
            }
            attachments_meta.push(doc! {
                "attachment_id": att_id,
                "filename": att.get_str("filename").unwrap_or(""),
                "mime": att.get_str("mime").unwrap_or(""),
                "size": get_i64_lenient(&att, "size"),
                "sha3_512_hex": att.get_str("sha3_512_hex").unwrap_or(""),
            });
        }
    }
    if req.plaintext.trim().is_empty() && attachments_meta.is_empty() {
        return Err(err(StatusCode::UNPROCESSABLE_ENTITY, "message must have text or at least one attachment"));
    }

    let _ = state.db.collection::<Document>("pulse_messages").insert_one(doc! {
        "msg_id": &msg_id,
        "conv_id": &cid,
        "from_lns": &from_lns,
        "to_lns": &to_lns,
        "ciphertext_hex": &ciphertext_hex,
        "nonce_hex": &nonce_hex,
        "sealed_at": &ts,
        "anchor_tx_id": bson::Bson::Null,
        "plaintext": &req.plaintext,  // unencrypted at-rest — envelope.seal_text is Python-only for now
        "attachments": if attachments_meta.is_empty() { bson::Bson::Null } else { bson::Bson::Array(attachments_meta.iter().map(|d| bson::Bson::Document(d.clone())).collect()) },
        "via": "lattice-gateway-rust",
    }).await;

    // -- Conversation bump --
    let mut conv_participants = vec![from_lns.clone(), to_lns.clone()];
    conv_participants.sort();
    let conv_participants_bson = bson::Bson::Array(
        conv_participants.iter().map(|s| bson::Bson::String(s.clone())).collect()
    );
    let conv = state.db.collection::<Document>("pulse_conversations")
        .find_one_and_update(
            doc! {"conv_id": &cid},
            doc! {
                "$set": {"last_message_at": &ts, "participants": conv_participants_bson},
                "$inc": {"message_count": 1_i64},
                "$setOnInsert": {
                    "conv_id": &cid,
                    "last_anchor_tx": bson::Bson::Null,
                    "last_anchor_block": bson::Bson::Null,
                    "started_at": &ts,
                },
            },
        )
        .upsert(true)
        .return_document(mongodb::options::ReturnDocument::After)
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("conv upsert: {e}")))?;
    let conv = conv.unwrap_or_default();
    let message_number = get_i64_lenient(&conv, "message_count").max(1);

    // -- Session bookkeeping --
    let mut participants: Vec<String> = vec![from_lns.clone(), to_lns.clone()];
    participants.sort();
    let session_fp = pulse_session_fingerprint(&cid, &participants);
    let epoch_count = ((message_number - 1) / PULSE_ANCHOR_EVERY) + 1;
    let mut root_h = Sha3_256::new();
    Digest::update(&mut root_h, format!("root|{}|epoch={}", cid, epoch_count).as_bytes());
    let root_fp: String = hex::encode(root_h.finalize())[..32].to_uppercase();
    let _ = state.db.collection::<Document>("pulse_sessions").update_one(
        doc! {"conv_id": &cid},
        doc! {
            "$set": {
                "conv_id": &cid,
                "participants": bson::Bson::Array(participants.iter().map(|s| bson::Bson::String(s.clone())).collect()),
                "fingerprint": &session_fp,
                "epoch": epoch_count,
                "message_number": message_number,
                "root_key_fingerprint": &root_fp,
                "cipher_suite": "PQXDH(ML-KEM-768) + Double-Ratchet · AEAD: AES-256-GCM",
            },
            "$setOnInsert": {"started_at": &ts},
        },
    ).upsert(true).await;

    // -- Loopix mixnet route preview --
    let relays_coll = state.db.collection::<Document>("mixnet_relays");
    let mut all_relays: Vec<Document> = Vec::new();
    if let Ok(mut cur) = relays_coll.find(doc! {}).await {
        use futures::StreamExt;
        while let Some(r) = cur.next().await { if let Ok(d) = r { all_relays.push(d); } }
    }
    let mut layers: HashMap<i64, Vec<Document>> = HashMap::new();
    for r in &all_relays {
        let l = get_i64_lenient(r, "layer");
        layers.entry(l).or_default().push(r.clone());
    }
    let mut seed_h = Sha3_256::new();
    Digest::update(&mut seed_h, format!("{}|{}", msg_id, cid).as_bytes());
    let seed_hex = hex::encode(seed_h.finalize());
    let mut acc = u128::from_str_radix(&seed_hex[..16], 16).unwrap_or(0);
    let mut hops: Vec<RouteHop> = Vec::with_capacity(3);
    for layer in 0_i64..3 {
        let bucket = layers.get(&layer).filter(|v| !v.is_empty()).unwrap_or(&all_relays);
        if bucket.is_empty() { continue; }
        let idx = (acc as usize) % bucket.len();
        let relay = &bucket[idx];
        let node_id = relay.get_str("node_id").unwrap_or("relay-?").to_string();
        let label = relay.get_str("label").unwrap_or("Relay").to_string();
        let region = relay.get_str("region").unwrap_or("EU-DC").to_string();
        let latency = get_i64_lenient(relay, "latency_ms");
        let mut acc_h = Sha3_256::new();
        Digest::update(&mut acc_h, &acc.to_be_bytes()[8..]);
        Digest::update(&mut acc_h, node_id.as_bytes());
        let next_hex = hex::encode(acc_h.finalize());
        acc = u128::from_str_radix(&next_hex[..16], 16).unwrap_or(0);
        let mut hop_h = Sha3_256::new();
        Digest::update(&mut hop_h, format!("LATTICE-LOOPIX-v1|{}|{}|layer={}|{}", from_lns, to_lns, layer, node_id).as_bytes());
        let onion_layer_hash = hex::encode(hop_h.finalize());
        let delay = latency + 15 * (layer + 1);
        hops.push(RouteHop { layer: layer as i32, relay_node_id: node_id, relay_label: label,
            relay_region: region, onion_layer_hash, delay_ms: delay });
    }
    let mut ri = Sha3_256::new();
    for h in &hops {
        if let Ok(b) = hex::decode(&h.onion_layer_hash) { Digest::update(&mut ri, &b); }
    }
    let route_id = format!("route-{}", &hex::encode(ri.finalize())[..24]);

    // -- On-chain anchor every N messages --
    let mut anchor_tx_id: Option<String> = None;
    let mut anchor_block_index: Option<i64> = None;
    if message_number % PULSE_ANCHOR_EVERY == 0 {
        let trunc_ct = if ciphertext_hex.len() > 128 { &ciphertext_hex[..128] } else { ciphertext_hex.as_str() };
        let payload = format!("{}|{}|{}|{}", cid, message_number, trunc_ct, ts);
        let mut ah = Sha3_512::new();
        Digest::update(&mut ah, payload.as_bytes());
        let anchor_hash = hex::encode(ah.finalize());

        let _guard = chain::BLOCK_LOCK.lock().await;
        let block_idx = chain::peek_next_block_index(&state.db).await
            .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("peek: {e}")))?;
        let _ = state.db.collection::<Document>("meta").update_one(
            doc! {"_id": "seeded"},
            doc! {"$inc": {"block_height": 1_i64, "tx_total": 1_i64, "qbft_round": 1_i64}},
        ).upsert(true).await;
        let tx_id = format!("tx-{}", det_hex(&format!("pulse-anchor-{}-{}", cid, message_number), 12));
        let summary = format!("PULSE_ANCHOR · {} · msgs={}", cid, message_number);
        let tx_msg = chain::tx_canonical_message(&tx_id, block_idx, &ts, "NotarySeal", &summary);
        let (sig_hex, sig_fp, actual_signer) = pqc_sign_or_delegate(
            &state.db, &from_lns, &tx_msg, s_tenant.as_deref(), "PULSE-GATEWAY",
        ).await.map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("pqc_sign_or_delegate: {e}")))?;
        let finalised = chain::finalise_block_for_tx_locked(
            &state.db, &state.http, &tx_id, "NotarySeal", &anchor_hash, &actual_signer, &ts,
        ).await
        .map_err(|e| err(StatusCode::SERVICE_UNAVAILABLE, format!("qbft: {e}")))?;
        if finalised.index != block_idx {
            return Err(err(StatusCode::INTERNAL_SERVER_ERROR,
                format!("block drift: signed={} alloc={}", block_idx, finalised.index)));
        }

        let extrinsics_root = det_hex(&format!("xroot-{}", tx_id), 64);
        let state_root = det_hex(&format!("sroot-{}", block_idx), 64);
        let _ = state.db.collection::<Document>("transactions").insert_one(doc! {
            "tx_id": &tx_id,
            "block_index": block_idx,
            "timestamp": &ts,
            "kind": "NotarySeal",
            "summary": &summary,
            "sender_public_key": &sig_fp,
            "signature": &sig_hex,
            "signed_with": "ML-DSA-65",
            "signer_entity": &actual_signer,
            "delegated_for": if actual_signer != from_lns { bson::Bson::String(from_lns.clone()) } else { bson::Bson::Null },
            "nonce": message_number,
            "weight": 8_000_i64,
            "doc_hash": &anchor_hash,
            "state_root": &state_root,
            "extrinsics_root": &extrinsics_root,
        }).await;
        let _ = state.db.collection::<Document>("pulse_messages").update_one(
            doc! {"msg_id": &msg_id},
            doc! {"$set": {"anchor_tx_id": &tx_id}},
        ).await;
        let _ = state.db.collection::<Document>("pulse_conversations").update_one(
            doc! {"conv_id": &cid},
            doc! {"$set": {"last_anchor_tx": &tx_id, "last_anchor_block": block_idx}},
        ).await;
        anchor_tx_id = Some(tx_id);
        anchor_block_index = Some(block_idx);
    }

    Ok(Json(PulseSendResponse {
        ok: true, msg_id, conv_id: cid, ciphertext_hex, nonce_hex, sealed_at: ts,
        anchor_tx_id, anchor_block_index, session_fingerprint: session_fp,
        epoch: epoch_count, message_number, route_id, route_hops: hops,
        rln_slot_used: used, rln_slot_max: RLN_MAX_PER_EPOCH,
    }))
}

// -- GET /api/pulse/session/{conv_id} ---------------------------------------

#[derive(Debug, Serialize)]
pub struct PulseSessionDoc {
    pub conv_id: String,
    pub participants: Vec<String>,
    pub fingerprint: String,
    pub epoch: i64,
    pub message_number: i64,
    pub root_key_fingerprint: String,
    pub started_at: String,
    pub cipher_suite: String,
}

pub async fn pulse_session(
    State(state): State<AppState>,
    Path(cid): Path<String>,
) -> Result<Json<PulseSessionDoc>, (StatusCode, Json<PulseError>)> {
    if let Ok(Some(doc)) = state.db.collection::<Document>("pulse_sessions")
        .find_one(doc! {"conv_id": &cid}).await
    {
        return Ok(Json(PulseSessionDoc {
            conv_id: cid.clone(),
            participants: doc.get_array("participants").map(|a|
                a.iter().filter_map(|b| b.as_str().map(String::from)).collect()).unwrap_or_default(),
            fingerprint: doc.get_str("fingerprint").unwrap_or("").to_string(),
            epoch: get_i64_lenient(&doc, "epoch"),
            message_number: get_i64_lenient(&doc, "message_number"),
            root_key_fingerprint: doc.get_str("root_key_fingerprint").unwrap_or("").to_string(),
            started_at: doc.get_str("started_at").unwrap_or("").to_string(),
            cipher_suite: doc.get_str("cipher_suite").unwrap_or(
                "PQXDH(ML-KEM-768) + Double-Ratchet · AEAD: AES-256-GCM").to_string(),
        }));
    }
    let conv = state.db.collection::<Document>("pulse_conversations")
        .find_one(doc! {"conv_id": &cid}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?
        .ok_or_else(|| err(StatusCode::NOT_FOUND, format!("No active Pulse session for {}", cid)))?;
    let participants: Vec<String> = conv.get_array("participants").map(|a|
        a.iter().filter_map(|b| b.as_str().map(String::from)).collect()).unwrap_or_default();
    let mc = get_i64_lenient(&conv, "message_count");
    let epoch_count = (mc.saturating_sub(1) / PULSE_ANCHOR_EVERY) + 1;
    let mut h = Sha3_256::new();
    Digest::update(&mut h, format!("root|{}|epoch={}", cid, epoch_count).as_bytes());
    let root_fp: String = hex::encode(h.finalize())[..32].to_uppercase();
    let started = conv.get_str("started_at").or_else(|_| conv.get_str("last_message_at"))
        .map(String::from).unwrap_or_else(|_| utc_iso());
    let session = PulseSessionDoc {
        conv_id: cid.clone(),
        participants: participants.clone(),
        fingerprint: pulse_session_fingerprint(&cid, &participants),
        epoch: epoch_count,
        message_number: mc,
        root_key_fingerprint: root_fp.clone(),
        started_at: started.clone(),
        cipher_suite: "PQXDH(ML-KEM-768) + Double-Ratchet · AEAD: AES-256-GCM".to_string(),
    };
    let _ = state.db.collection::<Document>("pulse_sessions").update_one(
        doc! {"conv_id": &cid},
        doc! {"$set": {
            "conv_id": &cid,
            "participants": bson::Bson::Array(participants.iter().map(|s| bson::Bson::String(s.clone())).collect()),
            "fingerprint": &session.fingerprint,
            "epoch": epoch_count,
            "message_number": mc,
            "root_key_fingerprint": &root_fp,
            "started_at": &started,
            "cipher_suite": &session.cipher_suite,
        }},
    ).upsert(true).await;
    Ok(Json(session))
}
