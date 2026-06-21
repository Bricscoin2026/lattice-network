//! POST /api/tenants/register — native Rust port of
//! `backend/routes/tenants.py::do_register_tenant`.
//!
//! Onboard a new enterprise on the network: reserve its DNS-like
//! domain (`prefix.lns`) and bootstrap its founder admin LNS in one
//! atomic block.

use axum::{extract::State, http::StatusCode, Json};
use bson::{doc, Document};
use rand::RngCore;
use serde::{Deserialize, Serialize};

use crate::chain::utc_iso;
use crate::lns::{register_lns, LnsRegisterRequest};
use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct TenantRegisterRequest {
    pub name: String,
    pub domain_prefix: String,
    pub admin_lns_prefix: String,
    pub admin_display_name: String,
}

#[derive(Debug, Serialize)]
pub struct TenantRegisterResponse {
    pub ok: bool,
    pub tenant_id: String,
    pub name: String,
    pub domain: String,
    pub admin_lns: String,
    pub admin_did: String,
    pub admin_tx_id: String,
    pub block_index: i64,
    pub created_at: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub admin_keypair_json: Option<serde_json::Value>,
}

#[derive(Debug, Serialize)]
pub struct TenantError {
    pub detail: String,
}

fn err(code: StatusCode, msg: impl Into<String>) -> (StatusCode, Json<TenantError>) {
    (code, Json(TenantError { detail: msg.into() }))
}

fn random_id() -> String {
    let mut buf = [0u8; 6];
    rand::rngs::OsRng.fill_bytes(&mut buf);
    format!("tnt-{}", hex::encode(buf))
}

pub async fn register_tenant(
    State(state): State<AppState>,
    Json(req): Json<TenantRegisterRequest>,
) -> Result<Json<TenantRegisterResponse>, (StatusCode, Json<TenantError>)> {
    let prefix = req.domain_prefix.trim().to_lowercase();
    let domain = format!("{}.lns", prefix);
    let name = req.name.trim();
    if name.is_empty() {
        return Err(err(StatusCode::UNPROCESSABLE_ENTITY, "name required"));
    }

    if let Some(_existing) = state.db.collection::<Document>("tenants")
        .find_one(doc! {"domain": &domain})
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?
    {
        return Err(err(StatusCode::CONFLICT, format!("domain already taken: {}", domain)));
    }

    let tenant_id = random_id();
    let admin_lns_prefix = req.admin_lns_prefix.trim().to_lowercase();
    let admin_full_lns = format!("{}.{}", admin_lns_prefix, domain);

    if let Some(_existing) = state.db.collection::<Document>("lns")
        .find_one(doc! {"lns_name": &admin_full_lns})
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?
    {
        return Err(err(StatusCode::CONFLICT,
            format!("admin lns already exists: {}", admin_full_lns)));
    }

    let created_at = utc_iso();

    // 1. Reserve the tenant slot.
    state.db.collection::<Document>("tenants")
        .insert_one(doc! {
            "tenant_id": &tenant_id,
            "name": name,
            "domain": &domain,
            "admin_lns": &admin_full_lns,
            "created_at": &created_at,
            "employees_count": 0_i64,
        })
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("insert tenant: {e}")))?;

    // 2. Delegate to LNS register for the founder admin.
    let sub_req = LnsRegisterRequest {
        lns_name: admin_full_lns.clone(),
        department: Some("Direzione".into()),
        admin: Some(req.admin_display_name.clone()),
        display_name: Some(req.admin_display_name.clone()),
        tenant_id: Some(tenant_id.clone()),
        role: "admin".into(),
        public_key_hex: None,
        enc_public_key_hex: None,
    };
    let sub_resp = match register_lns(State(state.clone()), Json(sub_req)).await {
        Ok(Json(r)) => r,
        Err((sc, Json(e))) => {
            // Roll back the tenant insert to keep things atomic.
            let _ = state.db.collection::<Document>("tenants")
                .delete_one(doc! {"tenant_id": &tenant_id}).await;
            return Err(err(sc, format!("register admin LNS: {}", e.detail)));
        }
    };

    let keypair_json = if let (Some(pk), Some(sk)) = (sub_resp.public_key_hex.clone(), sub_resp.secret_key_hex.clone()) {
        Some(serde_json::json!({
            "version": 1,
            "algorithm": "ML-DSA-65",
            "lns_name": admin_full_lns,
            "tenant_id": tenant_id,
            "did": sub_resp.did,
            "public_key_hex": pk,
            "secret_key_hex": sk,
            "created_at": created_at,
        }))
    } else {
        None
    };

    Ok(Json(TenantRegisterResponse {
        ok: true,
        tenant_id,
        name: name.to_string(),
        domain,
        admin_lns: admin_full_lns,
        admin_did: sub_resp.did,
        admin_tx_id: sub_resp.tx_id,
        block_index: sub_resp.block_index,
        created_at,
        admin_keypair_json: keypair_json,
    }))
}
