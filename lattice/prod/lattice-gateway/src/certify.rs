//! `POST /api/certify/send` — native Rust port of
//! `routes/certify_mutating.py::certify_send`.
//!
//! M7 step 1 — supports:
//!   * single + multi recipient (TO + CC)
//!   * client-provided E2E envelope (body_e2e_envelope set)
//!   * server-side body persistence in clear (when no envelope provided)
//!   * SHA3-512 doc hash + ML-DSA-65 TX signature + QBFT-finalised block
//!
//! Not yet ported (delegated to Python sidecar if needed):
//!   * attachments
//!   * server-side body envelope encryption with the runtime master key
//!   * cross-tenant policy enforcement requiring JWT context
//!
//! These will land in M7B/M7C.

use axum::{extract::State, http::StatusCode, Json};
use bson::{doc, Document};
use serde::{Deserialize, Serialize};
use sha3::{Digest, Sha3_512};

use crate::chain;
use crate::chain::utc_iso;
use crate::crypto::{det_hex, pqc_sign};
use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct CertifyComposeRequest {
    pub sender_lns: String,
    #[serde(default)]
    pub recipient_lns: Option<String>,
    #[serde(default)]
    pub recipients_lns: Option<Vec<String>>,
    #[serde(default)]
    pub cc_lns: Option<Vec<String>>,
    pub subject: String,
    #[serde(default)]
    pub body: Option<String>,
    #[serde(default = "default_class")]
    pub classification: String,
    #[serde(default)]
    pub body_e2e_envelope: Option<serde_json::Value>,
}

fn default_class() -> String { "INTERNAL".into() }

#[derive(Debug, Serialize)]
pub struct CertifyComposeResponse {
    pub ok: bool,
    pub mail_id: String,
    pub mail_ids: Vec<String>,
    pub tx_id: String,
    pub block_index: i64,
    pub doc_hash: String,
    pub recipients_count: usize,
    pub sealed_at: String,
}

#[derive(Debug, Serialize)]
pub struct CertifyError {
    pub detail: String,
}

fn err(code: StatusCode, msg: impl Into<String>) -> (StatusCode, Json<CertifyError>) {
    (code, Json(CertifyError { detail: msg.into() }))
}

pub async fn certify_send(
    State(state): State<AppState>,
    Json(req): Json<CertifyComposeRequest>,
) -> Result<Json<CertifyComposeResponse>, (StatusCode, Json<CertifyError>)> {
    let sender = req.sender_lns.trim().to_lowercase();
    if sender.is_empty() {
        return Err(err(StatusCode::UNPROCESSABLE_ENTITY, "sender_lns required"));
    }

    // Recipient consolidation.
    let primary = req.recipient_lns.clone().map(|s| s.trim().to_lowercase()).filter(|s| !s.is_empty());
    let multi: Vec<String> = req.recipients_lns.clone().unwrap_or_default()
        .into_iter().map(|s| s.trim().to_lowercase()).filter(|s| !s.is_empty()).collect();
    let cc: Vec<String> = req.cc_lns.clone().unwrap_or_default()
        .into_iter().map(|s| s.trim().to_lowercase()).filter(|s| !s.is_empty()).collect();

    let mut seen = std::collections::HashSet::<String>::new();
    let mut to_list: Vec<String> = Vec::new();
    if let Some(p) = primary { if seen.insert(p.clone()) { to_list.push(p); } }
    for r in multi { if seen.insert(r.clone()) { to_list.push(r); } }
    let cc_final: Vec<String> = cc.into_iter().filter(|r| seen.insert(r.clone())).collect();
    if to_list.is_empty() {
        return Err(err(StatusCode::UNPROCESSABLE_ENTITY, "At least one recipient is required"));
    }

    // Sender must be a registered active LNS.
    let lns_doc = state.db.collection::<Document>("lns")
        .find_one(doc! {"lns_name": &sender, "status": "ACTIVE"})
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    if lns_doc.is_none() {
        return Err(err(StatusCode::FORBIDDEN, format!("sender not active: {}", sender)));
    }

    let all_recipients: Vec<String> = to_list.iter().chain(cc_final.iter()).cloned().collect();
    let cc_header = if cc_final.is_empty() { String::new() } else { format!("Cc: {}\n", cc_final.join(", ")) };
    let raw = format!(
        "From: {}\nTo: {}\n{}Subject: {}\nX-Lattice-Class: {}\n\n{}",
        sender,
        to_list.join(", "),
        cc_header,
        req.subject,
        req.classification,
        req.body.clone().unwrap_or_default(),
    );
    let raw_bytes = raw.as_bytes();
    let bytes_len = raw_bytes.len() as i64;
    let mut h = Sha3_512::new();
    h.update(raw_bytes);
    let doc_hash = hex::encode(h.finalize());

    let ts = utc_iso();

    // -- atomic on-chain notarisation -------------------------------------------
    let _guard = chain::BLOCK_LOCK.lock().await;
    let new_block_index = chain::peek_next_block_index(&state.db).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("peek: {e}")))?;
    let _ = state.db.collection::<Document>("meta")
        .update_one(
            doc! {"_id": "seeded"},
            doc! {"$inc": {"block_height": 1_i64, "tx_total": 1_i64, "qbft_round": 1_i64}},
        )
        .upsert(true).await;

    let tx_id = format!("tx-{}", det_hex(&format!("certify-{}-{}", doc_hash, ts), 12));
    let primary_mail_id = format!("mail-{}", det_hex(&format!("mail-{}-{}", doc_hash, ts), 10));
    let summary = format!(
        "Certify · {} → {} recipients · {}",
        sender, all_recipients.len(), &doc_hash[..16].to_uppercase()
    );
    let tx_msg = chain::tx_canonical_message(&tx_id, new_block_index, &ts, "NotarySeal", &summary);
    let sig = pqc_sign(&state.db, &sender, &tx_msg, "operator").await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("pqc_sign: {e}")))?;

    // -- one mail row per recipient leg -----------------------------------------
    let mut mail_ids: Vec<String> = Vec::with_capacity(all_recipients.len());
    let total = all_recipients.len();
    let to_count = to_list.len();
    let body_for_storage: bson::Bson = match &req.body_e2e_envelope {
        Some(_) => bson::Bson::Null,           // body lives only inside the envelope
        None => bson::Bson::String(req.body.clone().unwrap_or_default()),
    };
    let envelope_bson: bson::Bson = match &req.body_e2e_envelope {
        Some(v) => bson::to_bson(v).unwrap_or(bson::Bson::Null),
        None => bson::Bson::Null,
    };
    let is_e2e = req.body_e2e_envelope.is_some();

    let mut rows: Vec<Document> = Vec::with_capacity(total);
    for (i, recipient) in all_recipients.iter().enumerate() {
        let mid = if i == 0 {
            primary_mail_id.clone()
        } else {
            format!("mail-{}", det_hex(&format!("mail-{}-{}-{}", doc_hash, ts, i), 10))
        };
        mail_ids.push(mid.clone());
        let leg = if i < to_count { "TO" } else { "CC" };
        let subject_redacted = if total > 1 {
            format!("[REDACTED · CLASS-{}] · {}({}/{})", req.classification, leg, i + 1, total)
        } else {
            format!("[REDACTED · CLASS-{}]", req.classification)
        };
        rows.push(doc! {
            "mail_id": &mid,
            "sender_lns": &sender,
            "recipient_lns": recipient,
            "subject_redacted": &subject_redacted,
            "doc_hash": &doc_hash,
            "sealed_at": &ts,
            "bytes": bytes_len,
            "subject": &req.subject,
            "body": body_for_storage.clone(),
            "body_e2e_envelope": envelope_bson.clone(),
            "is_e2e_encrypted": is_e2e,
            "classification": &req.classification,
            "tx_id": &tx_id,
            "block_index": new_block_index,
            "via": "lattice-gateway-rust",
        });
    }
    state.db.collection::<Document>("certify_mails")
        .insert_many(rows)
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("insert mails: {e}")))?;

    // -- finalise block --------------------------------------------------------
    let finalised = chain::finalise_block_for_tx_locked(
        &state.db, &state.http, &tx_id, "NotarySeal", &doc_hash, &sender, &ts,
    ).await
    .map_err(|e| err(StatusCode::SERVICE_UNAVAILABLE, format!("qbft: {e}")))?;
    if finalised.index != new_block_index {
        return Err(err(StatusCode::INTERNAL_SERVER_ERROR,
            format!("block drift: signed={} alloc={}", new_block_index, finalised.index)));
    }

    state.db.collection::<Document>("transactions")
        .insert_one(doc! {
            "tx_id": &tx_id,
            "block_index": new_block_index,
            "timestamp": &ts,
            "kind": "NotarySeal",
            "summary": &summary,
            "sender_public_key": &sig.fingerprint,
            "signature": &sig.signature_hex,
            "signed_with": "ML-DSA-65",
            "doc_hash": &doc_hash,
        })
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("insert tx: {e}")))?;

    Ok(Json(CertifyComposeResponse {
        ok: true,
        mail_id: primary_mail_id,
        mail_ids,
        tx_id,
        block_index: new_block_index,
        doc_hash,
        recipients_count: total,
        sealed_at: ts,
    }))
}

// ===========================================================================
// M7 step 2 — read / restore / delete
// ===========================================================================
//
// Note: until JWT middleware lands in Rust, the caller passes the acting
// identity in `as_lns` (server still cross-checks recipient_lns vs as_lns
// for read, sender_lns vs as_lns for delete). Wire-compatible with the
// Python `current_user_dep` flow.

use axum::extract::Path;
use crate::crypto::pqc_verify;

#[derive(Debug, Deserialize)]
pub struct ReadRequest {
    pub as_lns: String,
    #[serde(default)]
    pub signature_hex: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct ReadResponse {
    pub ok: bool,
    pub read_at: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub delivery_receipt: Option<serde_json::Value>,
}

pub async fn certify_mark_read(
    State(state): State<AppState>,
    Path(mail_id): Path<String>,
    Json(req): Json<ReadRequest>,
) -> Result<Json<ReadResponse>, (StatusCode, Json<CertifyError>)> {
    let me = req.as_lns.trim().to_lowercase();
    let coll = state.db.collection::<Document>("certify_mails");
    let mail = coll.find_one(doc! {"mail_id": &mail_id}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?
        .ok_or_else(|| err(StatusCode::NOT_FOUND, "mail not found"))?;

    if mail.get_str("recipient_lns").unwrap_or("") != me {
        return Ok(Json(ReadResponse { ok: true, read_at: None, delivery_receipt: None }));
    }

    let already_signed = mail.get("delivery_receipt").map(|b| !matches!(b, bson::Bson::Null)).unwrap_or(false);
    let ts = utc_iso();
    let mut updates = doc! {};
    if mail.get_str("read_at").is_err() {
        updates.insert("read_at", &ts);
    }

    let mut receipt_json: Option<serde_json::Value> = None;

    if let (Some(sig_hex), false) = (req.signature_hex.as_ref(), already_signed) {
        let sealed_at = mail.get_str("sealed_at").unwrap_or("");
        let sender = mail.get_str("sender_lns").unwrap_or("");
        let doc_hash = mail.get_str("doc_hash").unwrap_or("");
        let canonical = format!("{}|{}|{}|{}|{}", mail_id, sealed_at, sender, me, doc_hash);
        if !pqc_verify(&state.db, &me, canonical.as_bytes(), sig_hex).await {
            return Err(err(StatusCode::UNPROCESSABLE_ENTITY, "invalid delivery signature"));
        }

        // Notarise DeliveryReceipt on-chain.
        let _guard = chain::BLOCK_LOCK.lock().await;
        let block_idx = chain::peek_next_block_index(&state.db).await
            .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("peek: {e}")))?;
        let tx_id = format!("tx-{}", det_hex(&format!("dr-{}-{}", mail_id, ts), 12));
        let summary = format!("DeliveryReceipt · {} · {}", mail_id, me);
        let tx_msg = chain::tx_canonical_message(&tx_id, block_idx, &ts, "DeliveryReceipt", &summary);
        let dr_sig = pqc_sign(&state.db, &me, &tx_msg, "operator").await
            .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("pqc_sign: {e}")))?;
        let finalised = chain::finalise_block_for_tx_locked(
            &state.db, &state.http, &tx_id, "DeliveryReceipt", doc_hash, &me, &ts,
        ).await
        .map_err(|e| err(StatusCode::SERVICE_UNAVAILABLE, format!("qbft: {e}")))?;
        if finalised.index != block_idx {
            return Err(err(StatusCode::INTERNAL_SERVER_ERROR, "block drift on DR"));
        }
        state.db.collection::<Document>("transactions").insert_one(doc! {
            "tx_id": &tx_id,
            "block_index": block_idx,
            "timestamp": &ts,
            "kind": "DeliveryReceipt",
            "summary": &summary,
            "mail_id": &mail_id,
            "recipient": &me,
            "sender": sender,
            "signature": sig_hex,
            "sender_public_key": &dr_sig.fingerprint,
            "signed_with": "ML-DSA-65",
            "doc_hash": doc_hash,
        }).await.map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("insert tx: {e}")))?;

        let pre = {
            use sha3::{Digest, Sha3_512};
            let mut h = Sha3_512::new();
            h.update(canonical.as_bytes());
            hex::encode(h.finalize())
        };
        let receipt = serde_json::json!({
            "signature_hex": sig_hex,
            "signed_at": &ts,
            "tx_id": &tx_id,
            "block_index": block_idx,
            "signed_by": &me,
            "canonical_preimage_sha3_512": pre,
        });
        let receipt_bson = bson::to_bson(&receipt).unwrap_or(bson::Bson::Null);
        updates.insert("delivery_receipt", receipt_bson);
        receipt_json = Some(receipt);
    }

    if !updates.is_empty() {
        coll.update_one(doc! {"mail_id": &mail_id}, doc! {"$set": updates.clone()}).await
            .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("update: {e}")))?;
    }

    Ok(Json(ReadResponse {
        ok: true,
        read_at: updates.get_str("read_at").ok().map(String::from)
            .or_else(|| mail.get_str("read_at").ok().map(String::from)),
        delivery_receipt: receipt_json,
    }))
}

// -- POST /api/certify/{mail_id}/restore ------------------------------------

#[derive(Debug, Deserialize)]
pub struct ActorRequest {
    pub as_lns: String,
}

pub async fn certify_restore(
    State(state): State<AppState>,
    Path(mail_id): Path<String>,
    Json(req): Json<ActorRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<CertifyError>)> {
    let me = req.as_lns.trim().to_lowercase();
    let coll = state.db.collection::<Document>("certify_mails");
    let mail = coll.find_one(doc! {"mail_id": &mail_id}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?
        .ok_or_else(|| err(StatusCode::NOT_FOUND, "mail not found"))?;
    // Either party (sender or recipient) can restore their own copy.
    if mail.get_str("recipient_lns").unwrap_or("") != me && mail.get_str("sender_lns").unwrap_or("") != me {
        return Err(err(StatusCode::FORBIDDEN, "not authorised"));
    }
    let mut deleted_by: Vec<String> = mail.get_array("deleted_by")
        .map(|a| a.iter().filter_map(|b| b.as_str().map(|s| s.to_string())).collect())
        .unwrap_or_default();
    if !deleted_by.iter().any(|s| s == &me) {
        return Ok(Json(serde_json::json!({"ok": true, "noop": true})));
    }
    deleted_by.retain(|s| s != &me);
    let bson_arr: Vec<bson::Bson> = deleted_by.iter().map(|s| bson::Bson::String(s.clone())).collect();
    coll.update_one(
        doc! {"mail_id": &mail_id},
        doc! {"$set": {"deleted_by": bson_arr}},
    ).await.map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("update: {e}")))?;
    Ok(Json(serde_json::json!({"ok": true, "restored": true})))
}

// -- DELETE /api/certify/{mail_id} (soft delete with hard-delete on both sides) ----

pub async fn certify_delete(
    State(state): State<AppState>,
    Path(mail_id): Path<String>,
    Json(req): Json<ActorRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<CertifyError>)> {
    let me = req.as_lns.trim().to_lowercase();
    if me.is_empty() {
        return Err(err(StatusCode::UNAUTHORIZED, "login required to delete mail"));
    }
    let coll = state.db.collection::<Document>("certify_mails");
    let mail = coll.find_one(doc! {"mail_id": &mail_id}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?
        .ok_or_else(|| err(StatusCode::NOT_FOUND, "mail not found"))?;
    let sender = mail.get_str("sender_lns").unwrap_or("").to_string();
    let recipient = mail.get_str("recipient_lns").unwrap_or("").to_string();
    if me != sender && me != recipient {
        return Err(err(StatusCode::FORBIDDEN, "you can only delete mails you sent or received"));
    }
    let mut deleted_by: Vec<String> = mail.get_array("deleted_by")
        .map(|a| a.iter().filter_map(|b| b.as_str().map(|s| s.to_string())).collect())
        .unwrap_or_default();
    if deleted_by.iter().any(|s| s == &me) {
        return Ok(Json(serde_json::json!({"ok": true, "already_deleted": true})));
    }
    deleted_by.push(me.clone());
    let other = if me == recipient { &sender } else { &recipient };
    if !other.is_empty() && deleted_by.iter().any(|s| s == other) {
        coll.delete_one(doc! {"mail_id": &mail_id}).await
            .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("delete: {e}")))?;
        return Ok(Json(serde_json::json!({"ok": true, "hard_deleted": true})));
    }
    let bson_arr: Vec<bson::Bson> = deleted_by.iter().map(|s| bson::Bson::String(s.clone())).collect();
    coll.update_one(
        doc! {"mail_id": &mail_id},
        doc! {"$set": {"deleted_by": bson_arr}},
    ).await.map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("update: {e}")))?;
    Ok(Json(serde_json::json!({"ok": true, "soft_deleted": true})))
}

// ===========================================================================
// M7 step 3 — GET /api/certify/{mail_id}/receipt.pdf
// ===========================================================================
//
// Generates a cryptographically attested PDF "Ricevuta di consegna" using the
// `printpdf` crate. Layout mirrors the Python ReportLab original
// (routes/certify_mutating.py::certify_receipt_pdf) so existing recipients see
// an identical document whether the PDF is rendered by Python or Rust.
//
// The endpoint is read-only: it does not modify on-chain state — it just
// re-binds the existing `delivery_receipt` field on the mail into a portable
// PDF.

use axum::body::Bytes;
use axum::http::header;
use axum::response::{IntoResponse, Response};
use printpdf::*;

const GOLD: (f32, f32, f32) = (0.831, 0.686, 0.216);
const DARK: (f32, f32, f32) = (0.04, 0.06, 0.12);
const MUTED: (f32, f32, f32) = (0.42, 0.42, 0.42);

fn set_fill(layer: &PdfLayerReference, c: (f32, f32, f32)) {
    layer.set_fill_color(Color::Rgb(Rgb::new(c.0, c.1, c.2, None)));
}
fn set_stroke(layer: &PdfLayerReference, c: (f32, f32, f32)) {
    layer.set_outline_color(Color::Rgb(Rgb::new(c.0, c.1, c.2, None)));
}

#[derive(Debug, Deserialize)]
pub struct ReceiptQuery {
    /// Caller's LNS identity. JWT path TBD in M7C — until then the recipient
    /// passes its own LNS as a query string to assert authorisation.
    #[serde(default)]
    pub as_lns: Option<String>,
}

pub async fn certify_receipt_pdf(
    State(state): State<AppState>,
    Path(mail_id): Path<String>,
    axum::extract::Query(q): axum::extract::Query<ReceiptQuery>,
) -> Result<Response, (StatusCode, Json<CertifyError>)> {
    let coll = state.db.collection::<Document>("certify_mails");
    let mail = coll.find_one(doc! {"mail_id": &mail_id}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?
        .ok_or_else(|| err(StatusCode::NOT_FOUND, "mail not found"))?;

    let sender = mail.get_str("sender_lns").unwrap_or("").to_string();
    let recipient = mail.get_str("recipient_lns").unwrap_or("").to_string();
    if let Some(me) = q.as_lns.as_ref() {
        let me = me.trim().to_lowercase();
        if !me.is_empty() && me != sender && me != recipient {
            return Err(err(StatusCode::FORBIDDEN, "not a party of this mail"));
        }
    }

    // delivery_receipt must exist (recipient must have signed the open event).
    let receipt_doc = match mail.get("delivery_receipt") {
        Some(bson::Bson::Document(d)) => d.clone(),
        _ => {
            return Err(err(
                StatusCode::CONFLICT,
                "no PEC delivery receipt yet — recipient has not signed the open event",
            ));
        }
    };

    let subject = mail.get_str("subject").unwrap_or("—").to_string();
    let classification = mail.get_str("classification").unwrap_or("INTERNAL").to_string();
    let sealed_at = mail.get_str("sealed_at").unwrap_or("").to_string();
    let doc_hash = mail.get_str("doc_hash").unwrap_or("").to_string();

    let signed_by = receipt_doc.get_str("signed_by").unwrap_or("").to_string();
    let signed_at = receipt_doc.get_str("signed_at").unwrap_or("").to_string();
    let preimage = receipt_doc.get_str("canonical_preimage_sha3_512").unwrap_or("").to_string();
    let sig_hex = receipt_doc.get_str("signature_hex").unwrap_or("").to_string();
    let tx_id = receipt_doc.get_str("tx_id").unwrap_or("").to_string();
    let block_index = receipt_doc.get_i64("block_index")
        .or_else(|_| receipt_doc.get_i32("block_index").map(|v| v as i64))
        .unwrap_or(0);

    let pdf_bytes = build_receipt_pdf(BuildArgs {
        mail_id: &mail_id, sender: &sender, recipient: &recipient,
        sealed_at: &sealed_at, classification: &classification, subject: &subject,
        doc_hash: &doc_hash, signed_by: &signed_by, signed_at: &signed_at,
        preimage: &preimage, sig_hex: &sig_hex, tx_id: &tx_id, block_index,
    }).map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("pdf: {e}")))?;

    let mut resp = (StatusCode::OK, Bytes::from(pdf_bytes)).into_response();
    resp.headers_mut().insert(
        header::CONTENT_TYPE,
        "application/pdf".parse().unwrap(),
    );
    resp.headers_mut().insert(
        header::CONTENT_DISPOSITION,
        format!("attachment; filename=\"receipt-{}.pdf\"", mail_id).parse().unwrap(),
    );
    Ok(resp)
}

struct BuildArgs<'a> {
    mail_id: &'a str, sender: &'a str, recipient: &'a str,
    sealed_at: &'a str, classification: &'a str, subject: &'a str,
    doc_hash: &'a str, signed_by: &'a str, signed_at: &'a str,
    preimage: &'a str, sig_hex: &'a str, tx_id: &'a str, block_index: i64,
}

fn wrap_chunks(s: &str, w: usize) -> Vec<String> {
    if s.len() <= w { return vec![s.to_string()]; }
    s.as_bytes().chunks(w)
        .map(|c| String::from_utf8_lossy(c).to_string()).collect()
}

fn build_receipt_pdf(a: BuildArgs<'_>) -> Result<Vec<u8>, String> {
    // A4 = 210 × 297 mm. We mirror the Python layout (M=18mm margins).
    let (doc, page1, layer1) = PdfDocument::new(
        format!("Lattice Receipt {}", a.mail_id),
        Mm(210.0), Mm(297.0), "L1",
    );
    let bold = doc.add_builtin_font(BuiltinFont::HelveticaBold).map_err(|e| e.to_string())?;
    let reg  = doc.add_builtin_font(BuiltinFont::Helvetica).map_err(|e| e.to_string())?;
    let ital = doc.add_builtin_font(BuiltinFont::HelveticaOblique).map_err(|e| e.to_string())?;
    let layer = doc.get_page(page1).get_layer(layer1);

    let margin_mm = 18.0;
    let w_mm = 210.0;
    let h_mm = 297.0;
    let mut y = h_mm - margin_mm;

    // -- Header --
    set_fill(&layer, DARK);
    layer.use_text("LATTICE NETWORK", 18.0, Mm(margin_mm), Mm(y), &bold);
    set_fill(&layer, GOLD);
    layer.use_text(
        "RICEVUTA DI CONSEGNA · PROVA LEGALE OPPONIBILE",
        9.0, Mm(margin_mm), Mm(y - 5.0), &reg,
    );
    set_fill(&layer, MUTED);
    let now = chrono::Utc::now().format("%d/%m/%Y · %H:%M UTC").to_string();
    layer.use_text(&now, 8.0, Mm(w_mm - margin_mm - 38.0), Mm(y), &reg);
    set_stroke(&layer, GOLD);
    layer.set_outline_thickness(1.2);
    let header_rule = Line {
        points: vec![
            (Point::new(Mm(margin_mm), Mm(y - 9.0)), false),
            (Point::new(Mm(w_mm - margin_mm), Mm(y - 9.0)), false),
        ],
        is_closed: false,
    };
    layer.add_line(header_rule);
    y -= 17.0;

    // helper closures.
    let section = |layer: &PdfLayerReference, title: &str, y: f32| -> f32 {
        set_fill(layer, GOLD);
        layer.use_text(&title.to_uppercase(), 8.0, Mm(margin_mm), Mm(y), &bold);
        set_stroke(layer, GOLD);
        layer.set_outline_thickness(0.4);
        let line = Line {
            points: vec![
                (Point::new(Mm(margin_mm), Mm(y - 1.0)), false),
                (Point::new(Mm(w_mm - margin_mm), Mm(y - 1.0)), false),
            ],
            is_closed: false,
        };
        layer.add_line(line);
        set_fill(layer, DARK);
        y - 6.0
    };

    let kv = |layer: &PdfLayerReference, label: &str, value: &str, mut y: f32, wrap: bool| -> f32 {
        set_fill(layer, MUTED);
        layer.use_text(&label.to_uppercase(), 7.5, Mm(margin_mm), Mm(y), &reg);
        set_fill(layer, DARK);
        let v = if value.is_empty() { "—".to_string() } else { value.to_string() };
        if wrap && v.len() > 80 {
            let chunks = wrap_chunks(&v, 80);
            for (i, ch) in chunks.iter().enumerate() {
                layer.use_text(ch, 9.5, Mm(margin_mm), Mm(y - 4.0 - (i as f32) * 4.0), &reg);
            }
            y -= 4.0 + (chunks.len() as f32) * 4.0 + 2.0;
        } else {
            layer.use_text(&v, 9.5, Mm(margin_mm), Mm(y - 4.0), &reg);
            y -= 8.0;
        }
        y
    };

    // -- 1. Identificazione comunicazione --
    y = section(&layer, "1. Identificazione comunicazione", y);
    y = kv(&layer, "Mail ID", a.mail_id, y, false);
    y = kv(&layer, "Mittente", a.sender, y, false);
    y = kv(&layer, "Destinatario", a.recipient, y, false);
    y = kv(&layer, "Data invio", a.sealed_at, y, false);
    y = kv(&layer, "Classificazione", a.classification, y, false);
    y = kv(&layer, "Oggetto", a.subject, y, false);
    let dh_short = if a.doc_hash.len() > 96 { format!("{}…", &a.doc_hash[..96]) } else { a.doc_hash.to_string() };
    y = kv(&layer, "Hash documento (SHA3-512)", &dh_short, y, true);

    y -= 2.0;
    y = section(&layer, "2. Ricevuta di apertura firmata digitalmente", y);
    y = kv(&layer, "Firmata da (LNS destinatario)", a.signed_by, y, false);
    y = kv(&layer, "Data firma", a.signed_at, y, false);
    y = kv(&layer, "Algoritmo", "ML-DSA-65 (NIST FIPS 204 · post-quantum)", y, false);
    y = kv(&layer, "Preimage hash (SHA3-512)", a.preimage, y, true);
    let sig_short = if a.sig_hex.len() > 120 { format!("{}…", &a.sig_hex[..120]) } else { a.sig_hex.to_string() };
    y = kv(&layer, "Firma digitale (ML-DSA-65, 3309 byte)", &sig_short, y, true);

    y -= 2.0;
    y = section(&layer, "3. Notarizzazione blockchain", y);
    y = kv(&layer, "Transaction ID", a.tx_id, y, false);
    y = kv(&layer, "Block index", &format!("#{}", a.block_index), y, false);
    y = kv(&layer, "Consenso", "QBFT · 4 validatori · 3/4 firme ML-DSA-65", y, false);
    y = kv(&layer, "Catena", "lattice-sovereign-it-prod", y, false);

    y -= 2.0;
    y = section(&layer, "4. Come verificare questa ricevuta", y);
    let lines = [
        "1. Ricostruisci il payload canonico:".to_string(),
        "   <mail_id>|<sealed_at>|<sender_lns>|<recipient_lns>|<doc_hash>".to_string(),
        "2. Recupera la chiave pubblica del destinatario dalla catena:".to_string(),
        format!("   GET /api/keystore/{}", a.recipient),
        "3. Verifica la firma digitale ML-DSA-65 con il payload canonico.".to_string(),
        format!("4. Verifica che il blocco #{} contenga il TX {}", a.block_index, a.tx_id),
        "   (immutabile, firmato dai 4 validator).".to_string(),
    ];
    set_fill(&layer, DARK);
    for (i, line) in lines.iter().enumerate() {
        layer.use_text(line, 8.5, Mm(margin_mm), Mm(y - (i as f32) * 4.0), &reg);
    }

    // -- Footer legale --
    set_fill(&layer, MUTED);
    let legal = "Documento generato automaticamente dalla rete Lattice Network. La firma ML-DSA-65 è un primitivo post-quantum standardizzato da NIST (FIPS 204). Il blocco è finalizzato da 4 validatori indipendenti tramite consenso QBFT bizantino. La presente ricevuta è opponibile a terzi e verificabile in modo indipendente per sempre, senza necessità di affidamento a terzi.";
    let words: Vec<&str> = legal.split_whitespace().collect();
    let mut yy = margin_mm + 12.0;
    let mut buf = String::new();
    let max_chars = 110_usize; // approximate at 7.5pt across ~174mm
    for w in &words {
        if buf.len() + w.len() + 1 > max_chars {
            layer.use_text(buf.trim(), 7.5, Mm(margin_mm), Mm(yy), &ital);
            yy -= 3.5;
            buf.clear();
        }
        buf.push(' ');
        buf.push_str(w);
    }
    if !buf.is_empty() {
        layer.use_text(buf.trim(), 7.5, Mm(margin_mm), Mm(yy), &ital);
    }

    set_fill(&layer, GOLD);
    layer.use_text(
        "LATTICE NETWORK · cybersicurezza sovrana · WhatsApp +39 351 961 8068",
        7.0, Mm(margin_mm + 30.0), Mm(margin_mm), &bold,
    );

    doc.save_to_bytes().map_err(|e| e.to_string())
}

