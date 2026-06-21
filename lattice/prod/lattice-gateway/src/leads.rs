//! POST /api/leads — first **write** endpoint ported to native Rust.
//!
//! Pipeline (matches `backend/routes/leads.py` byte-for-byte):
//!   1. Validate `LeadRequest` (length + email regex).
//!   2. Build `lead` dict, generate `lead_id` (12 hex chars random).
//!   3. SHA3-512 canonical hash of the lead.
//!   4. Increment `meta.block_height` to reserve the next block index.
//!   5. Sign the TX message with the platform `leads-bot` keypair.
//!   6. Run `finalise_block_for_tx` → QBFT 2f+1 quorum → insert block.
//!   7. Persist the lead + TX in MongoDB.
//!   8. Best-effort email notification (skipped if SMTP not configured).
//!   9. Return `LeadResponse { ok, lead_id, received_at }`.

use axum::{extract::State, http::StatusCode, Json};
use bson::{doc, Document};
use once_cell::sync::Lazy;
use regex::Regex;
use serde::{Deserialize, Serialize};
use sha3::{Digest, Sha3_512};
use tracing::warn;

use crate::chain;
use crate::chain::utc_iso;
use crate::crypto::{det_hex, pqc_sign};
use crate::AppState;

static EMAIL_RE: Lazy<Regex> = Lazy::new(|| Regex::new(r"^[^@\s]+@[^@\s]+\.[^@\s]+$").unwrap());

#[derive(Debug, Deserialize)]
pub struct LeadRequest {
    pub company_name: String,
    pub contact_name: String,
    pub email: String,
    pub phone: Option<String>,
    pub employees_range: Option<String>,
    pub industry: Option<String>,
    pub notes: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct LeadResponse {
    pub ok: bool,
    pub lead_id: String,
    pub received_at: String,
}

#[derive(Debug, Serialize)]
pub struct LeadError {
    pub detail: String,
}

fn validate(req: &LeadRequest) -> Result<(), String> {
    let cn = req.company_name.trim();
    if cn.len() < 2 || cn.len() > 100 {
        return Err("company_name length must be between 2 and 100 chars".into());
    }
    let cont = req.contact_name.trim();
    if cont.len() < 2 || cont.len() > 80 {
        return Err("contact_name length must be between 2 and 80 chars".into());
    }
    let e = req.email.trim();
    if e.len() < 5 || e.len() > 120 || !EMAIL_RE.is_match(e) {
        return Err("email is invalid".into());
    }
    if let Some(p) = req.phone.as_ref() {
        if p.len() > 40 {
            return Err("phone too long".into());
        }
    }
    if let Some(n) = req.notes.as_ref() {
        if n.len() > 2000 {
            return Err("notes too long".into());
        }
    }
    Ok(())
}

fn random_hex(len: usize) -> String {
    use rand::RngCore;
    let mut buf = vec![0u8; (len + 1) / 2];
    rand::rngs::OsRng.fill_bytes(&mut buf);
    hex::encode(&buf).chars().take(len).collect()
}

async fn notarise_lead_onchain(
    state: &AppState,
    lead: &Document,
) -> anyhow::Result<Document> {
    // 1. Canonical bytes (SHA3-512).
    let canonical = format!(
        "{}|{}|{}|{}|{}|{}|{}|{}",
        lead.get_str("lead_id").unwrap_or(""),
        lead.get_str("company_name").unwrap_or(""),
        lead.get_str("contact_name").unwrap_or(""),
        lead.get_str("email").unwrap_or(""),
        lead.get_str("phone").unwrap_or(""),
        lead.get_str("industry").unwrap_or(""),
        lead.get_str("employees_range").unwrap_or(""),
        lead.get_str("received_at").unwrap_or(""),
    );
    let mut h = Sha3_512::new();
    h.update(canonical.as_bytes());
    let doc_hash = hex::encode(h.finalize());

    let ts = lead.get_str("received_at").unwrap_or(&utc_iso()).to_string();

    // 2. Take the global block-proposal lock so peek → sign → finalise →
    //    insert TX is atomic. Guarantees the TX message signs over the
    //    SAME block_index that the finalised block will be allocated.
    let _guard = chain::BLOCK_LOCK.lock().await;
    let new_block_index = chain::peek_next_block_index(&state.db).await?;

    // Best-effort bump of legacy meta counters (not authoritative).
    let _ = state.db.collection::<Document>("meta")
        .update_one(
            doc! {"_id": "seeded"},
            doc! {"$inc": {"block_height": 1_i64, "tx_total": 1_i64, "qbft_round": 1_i64}},
        )
        .upsert(true)
        .await;

    let tx_id = format!("tx-{}", det_hex(&format!("lead-{}-{}", doc_hash, ts), 12));
    let extrinsics_root = det_hex(&format!("xroot-{}", tx_id), 64);
    let state_root = det_hex(&format!("sroot-{}", new_block_index), 64);
    let summary = format!(
        "LeadCapture · {} · {}",
        lead.get_str("company_name").unwrap_or("?"),
        doc_hash[..16].to_uppercase()
    );
    let tx_msg = chain::tx_canonical_message(&tx_id, new_block_index, &ts, "LeadCapture", &summary);
    let sig = pqc_sign(&state.db, "platform.leads-bot", &tx_msg, "platform").await?;

    // 4. Build single-TX block, QBFT-finalise, insert in `blocks` (lock-aware).
    let finalised = chain::finalise_block_for_tx_locked(
        &state.db,
        &state.http,
        &tx_id,
        "LeadCapture",
        &doc_hash,
        "platform.leads-bot",
        &ts,
    )
    .await?;
    // Defensive: signed index must equal the index the block actually got.
    if finalised.index != new_block_index {
        return Err(anyhow::anyhow!(
            "block_index drift: signed={} allocated={} — concurrent writer detected",
            new_block_index, finalised.index
        ));
    }

    // Patch the just-inserted block with state/extrinsics root + digest.
    let blocks = state.db.collection::<Document>("blocks");
    blocks
        .update_one(
            doc! {"index": finalised.index},
            doc! {"$set": {
                "state_root": &state_root,
                "extrinsics_root": &extrinsics_root,
                "events_count": 1_i32,
                "weight_used": 4000_i32,
                "digest": format!("qbft:{}", finalised.index),
            }},
        )
        .await?;

    // 5. Persist the LeadCapture TX with the same index we signed over.
    state.db.collection::<Document>("transactions")
        .insert_one(doc! {
            "tx_id": &tx_id,
            "block_index": new_block_index,
            "timestamp": &ts,
            "kind": "LeadCapture",
            "summary": &summary,
            "sender_public_key": &sig.fingerprint,
            "signature": &sig.signature_hex,
            "signed_with": "ML-DSA-65",
            "doc_hash": &doc_hash,
        })
        .await?;

    Ok(doc! {
        "tx_id": tx_id,
        "block_index": new_block_index,
        "doc_hash": doc_hash,
        "signed_at": ts,
        "signed_by": sig.fingerprint,
        "signature_hex": sig.signature_hex,
    })
}

pub async fn submit_lead(
    State(state): State<AppState>,
    Json(req): Json<LeadRequest>,
) -> Result<Json<LeadResponse>, (StatusCode, Json<LeadError>)> {
    if let Err(reason) = validate(&req) {
        return Err((
            StatusCode::UNPROCESSABLE_ENTITY,
            Json(LeadError { detail: reason }),
        ));
    }

    let lead_id = format!("lead-{}", random_hex(12));
    let ts = utc_iso();
    let today_prefix = &ts[..10];

    // Daily cap (env LATTICE_LEAD_DAILY_CAP, default 500).
    let daily_cap: i64 = std::env::var("LATTICE_LEAD_DAILY_CAP")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(500);
    let todays_onchain = state
        .db
        .collection::<Document>("leads")
        .count_documents(doc! {
            "received_at": {"$regex": format!("^{}", today_prefix)},
            "tx_id": {"$ne": null},
        })
        .await
        .unwrap_or(0) as i64;

    let mut lead = doc! {
        "lead_id": &lead_id,
        "company_name": req.company_name.trim(),
        "contact_name": req.contact_name.trim(),
        "email": req.email.trim().to_lowercase(),
        "phone": req.phone.clone().unwrap_or_default().trim(),
        "employees_range": req.employees_range.clone().unwrap_or_default(),
        "industry": req.industry.clone().unwrap_or_default(),
        "notes": req.notes.clone().unwrap_or_default().trim(),
        "received_at": &ts,
        "status": "new",
        "read_at": bson::Bson::Null,
        "captured_by": "lattice-gateway-rust",
    };

    if todays_onchain < daily_cap {
        match notarise_lead_onchain(&state, &lead).await {
            Ok(receipt) => {
                if let Ok(tx) = receipt.get_str("tx_id") {
                    lead.insert("tx_id", tx);
                }
                if let Ok(bi) = receipt.get_i64("block_index") {
                    lead.insert("block_index", bi);
                }
                if let Ok(dh) = receipt.get_str("doc_hash") {
                    lead.insert("doc_hash", dh);
                }
                if let Ok(sh) = receipt.get_str("signature_hex") {
                    lead.insert("signature_hex", sh);
                }
            }
            Err(e) => {
                warn!(lead_id = %lead_id, "lead on-chain notarisation failed: {}", e);
                lead.insert("onchain_skipped_reason", e.to_string());
            }
        }
    } else {
        warn!(
            "Daily LeadCapture cap ({}) hit for {} — storing without on-chain proof",
            daily_cap, today_prefix
        );
        lead.insert("onchain_skipped_reason", "daily_cap_exceeded");
    }

    state.db.collection::<Document>("leads")
        .insert_one(&lead)
        .await
        .map_err(|e| (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(LeadError { detail: format!("persist lead failed: {e}") }),
        ))?;

    // Email notification: best-effort. We delegate to the Python sidecar
    // so we don't duplicate SMTP logic. If Python is unreachable we just
    // log and continue (the lead is already safely on-chain).
    let python_url = std::env::var("LATTICE_PY_FALLBACK")
        .unwrap_or_else(|_| "http://127.0.0.1:8001".to_string());
    let notify_url = format!("{}/api/internal/notify-lead", python_url);
    let payload = serde_json::to_value(&lead).unwrap_or_default();
    let http = state.http.clone();
    // Fire-and-forget.
    tokio::spawn(async move {
        let _ = http.post(&notify_url).json(&payload).send().await;
    });

    Ok(Json(LeadResponse {
        ok: true,
        lead_id,
        received_at: ts,
    }))
}
