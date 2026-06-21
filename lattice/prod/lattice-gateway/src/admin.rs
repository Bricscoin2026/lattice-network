//! M8 batch 2 — admin/vendor/leads/lns mutating endpoints in Rust.
//!
//!   GET   /api/admin/health/overview        — sysadmin one-pane aggregator
//!   GET   /api/vendor/tenants               — vendor portfolio listing
//!   GET   /api/vendor/stats                 — vendor portfolio KPIs
//!   GET   /api/leads                        — inbox listing (sovereign-only)
//!   GET   /api/leads/unread-count           — unread counter
//!   POST  /api/leads/{lead_id}/read         — mark single lead read
//!   POST  /api/leads/read-all               — mark all leads read
//!   PATCH /api/leads/{lead_id}              — update status + follow-up notes
//!   PATCH /api/lns/{lns_name}/role          — employee role lifecycle

use std::env;
use std::time::Duration;

use axum::{
    extract::{Path, Query, State},
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    Json,
};
use bson::{doc, Document};
use chrono::{SecondsFormat, Utc};
use futures::StreamExt;
use mongodb::options::FindOptions;
use rand::Rng;
use serde::{Deserialize, Serialize};

use crate::misc::jwt_decode;
use crate::AppState;

#[derive(Debug, Serialize)]
pub struct AdminError { pub detail: String }
fn err(code: StatusCode, msg: impl Into<String>) -> (StatusCode, Json<AdminError>) {
    (code, Json(AdminError { detail: msg.into() }))
}

fn utc_iso() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Micros, true)
}

/// Caller must hold `X-Lattice-Role: sovereign` (legacy) OR a JWT whose
/// `role` claim equals "sovereign". Returns `Ok(())` on success.
fn require_sovereign(headers: &HeaderMap) -> Result<(), (StatusCode, Json<AdminError>)> {
    if let Some(r) = headers.get("x-lattice-role").and_then(|v| v.to_str().ok()) {
        if r.eq_ignore_ascii_case("sovereign") { return Ok(()); }
    }
    if let Some(c) = jwt_decode(headers) {
        if c.role.as_deref().map(|s| s.eq_ignore_ascii_case("sovereign")).unwrap_or(false) {
            return Ok(());
        }
    }
    Err(err(StatusCode::FORBIDDEN, "sovereign role required"))
}

// ===========================================================================
// GET /api/admin/health/overview
// ===========================================================================

pub async fn admin_health_overview(State(state): State<AppState>)
    -> Result<Json<serde_json::Value>, (StatusCode, Json<AdminError>)>
{
    let db = &state.db;

    let mut secrets = serde_json::json!({"status": "UNKNOWN"});
    if let Ok(Some(d)) = db.collection::<Document>("secret_state").find_one(doc! {}).await {
        let initialised = d.get_bool("initialised").unwrap_or(false);
        let unlocked = d.get_bool("unlocked").unwrap_or(false);
        secrets = serde_json::json!({
            "initialised": initialised, "unlocked": unlocked,
            "status": if !initialised { "uninitialised" } else if unlocked { "unlocked" } else { "locked" },
            "kdf": "Argon2id (m=64MB, t=3, p=4)",
            "aead": "AES-256-GCM",
        });
    } else {
        secrets = serde_json::json!({
            "initialised": false, "unlocked": false, "status": "uninitialised",
            "kdf": "Argon2id (m=64MB, t=3, p=4)", "aead": "AES-256-GCM",
        });
    }

    let license_status = match db.collection::<Document>("license_state").find_one(doc! {}).await {
        Ok(Some(d)) => serde_json::json!({
            "ok": d.get_bool("verified").unwrap_or(false),
            "tier": d.get_str("tier").unwrap_or("UNSET"),
            "seats": d.get_i64("seats")
                .or_else(|_| d.get_i32("seats").map(|v| v as i64)).unwrap_or(0),
            "expires_at": d.get_str("expires_at").unwrap_or(""),
        }),
        _ => serde_json::json!({"ok": false, "tier": "UNSET", "seats": 0}),
    };

    let ots_total = db.collection::<Document>("ots_anchors").count_documents(doc! {}).await.unwrap_or(0);
    let ots_btc = db.collection::<Document>("ots_anchors")
        .count_documents(doc! {"btc_attested": true}).await.unwrap_or(0);

    let chain = serde_json::json!({
        "blocks": db.collection::<Document>("blocks").count_documents(doc! {}).await.unwrap_or(0),
        "transactions": db.collection::<Document>("transactions").count_documents(doc! {}).await.unwrap_or(0),
        "lns_identities": db.collection::<Document>("lns").count_documents(doc! {}).await.unwrap_or(0),
        "tenants": db.collection::<Document>("tenants").count_documents(doc! {}).await.unwrap_or(0),
        "certify_mails": db.collection::<Document>("certify_mails").count_documents(doc! {}).await.unwrap_or(0),
        "pulse_messages": db.collection::<Document>("pulse_messages").count_documents(doc! {}).await.unwrap_or(0),
    });

    // Validators — via Python sidecar /api/qbft/status (still Rust gateway local).
    let mut validators = serde_json::json!({"total": 0, "online": 0});
    if let Ok(resp) = state.http.get("http://127.0.0.1:8002/api/qbft/status")
        .timeout(Duration::from_secs(3)).send().await
    {
        if let Ok(v) = resp.json::<serde_json::Value>().await {
            validators = serde_json::json!({
                "total": v.get("total_count").cloned().unwrap_or_else(|| serde_json::json!(0)),
                "online": v.get("live_count").cloned().unwrap_or_else(|| serde_json::json!(0)),
                "quorum_required": v.get("quorum_required").cloned().unwrap_or(serde_json::Value::Null),
                "quorum_reached": v.get("quorum_reached").cloned().unwrap_or(serde_json::Value::Null),
                "consensus": v.get("consensus").cloned().unwrap_or(serde_json::Value::Null),
                "nodes": v.get("validators").cloned().unwrap_or_else(|| serde_json::json!([])),
            });
        }
    }

    let mut mixnet = serde_json::json!({"enabled": false, "total": 0, "online": 0});
    if let Ok(resp) = state.http.get("http://127.0.0.1:8002/api/mixnet/status")
        .timeout(Duration::from_secs(3)).send().await
    {
        if let Ok(v) = resp.json::<serde_json::Value>().await {
            let relays = v.get("relays").and_then(|x| x.as_array()).cloned().unwrap_or_default();
            let online = relays.iter().filter(|r|
                r.get("status").and_then(|s| s.as_str()) == Some("ONLINE") ||
                r.get("live").and_then(|s| s.as_bool()).unwrap_or(false)).count();
            mixnet = serde_json::json!({
                "enabled": v.get("enabled").and_then(|b| b.as_bool()).unwrap_or(false),
                "total": relays.len(),
                "online": online,
            });
        }
    }

    // Disk usage via statvfs (use Linux /app path).
    let disk = match nix_statvfs("/app") {
        Ok((total, free)) => {
            let used = total.saturating_sub(free);
            serde_json::json!({
                "total_bytes": total, "used_bytes": used, "free_bytes": free,
                "used_pct": if total > 0 {
                    ((used as f64 / total as f64) * 1000.0).round() / 10.0
                } else { 0.0 },
            })
        }
        Err(e) => serde_json::json!({"error": e}),
    };

    let mut alerts = Vec::<serde_json::Value>::new();
    if let Ok(mut cur) = db.collection::<Document>("alert_state").find(doc! {}).await {
        while let Some(d) = cur.next().await {
            if let Ok(d) = d {
                alerts.push(serde_json::json!({
                    "key": d.get_str("key").unwrap_or(""),
                    "severity": d.get_str("severity").unwrap_or("info"),
                }));
            }
        }
    }

    let ots_cals = if let Ok(raw) = env::var("LATTICE_OTS_CALENDARS") {
        raw.split(',').map(|s| s.trim().to_string()).filter(|s| !s.is_empty()).collect::<Vec<_>>()
    } else {
        vec![
            "https://a.pool.opentimestamps.org".to_string(),
            "https://b.pool.opentimestamps.org".to_string(),
            "https://alice.btc.calendar.catallaxy.com".to_string(),
        ]
    };

    Ok(Json(serde_json::json!({
        "timestamp": utc_iso(),
        "secrets": secrets,
        "license": license_status,
        "compliance_mode": env::var("LATTICE_COMPLIANCE_MODE")
            .ok().map(|v| matches!(v.as_str(), "1"|"true"|"yes")).unwrap_or(false),
        "chain_id": env::var("LATTICE_CHAIN_ID")
            .unwrap_or_else(|_| "lattice-sovereign-it-prod".to_string()),
        "ots": {
            "enabled": env::var("LATTICE_OTS_ENABLED").ok()
                .map(|v| matches!(v.as_str(), "1"|"true"|"yes")).unwrap_or(false),
            "calendars": ots_cals,
            "anchors_total": ots_total,
            "btc_attested": ots_btc,
        },
        "validators": validators,
        "mixnet": mixnet,
        "chain": chain,
        "disk": disk,
        "alerts": alerts,
    })))
}

/// `statvfs` wrapper returning (total, free) in bytes.
fn nix_statvfs(path: &str) -> Result<(u64, u64), String> {
    use std::ffi::CString;
    let cpath = CString::new(path).map_err(|e| e.to_string())?;
    #[repr(C)]
    #[derive(Default)]
    struct Statvfs {
        f_bsize: u64, f_frsize: u64, f_blocks: u64, f_bfree: u64, f_bavail: u64,
        f_files: u64, f_ffree: u64, f_favail: u64,
        f_fsid: u64, f_flag: u64, f_namemax: u64,
        __reserved: [u64; 6],
    }
    extern "C" { fn statvfs(path: *const std::os::raw::c_char, buf: *mut Statvfs) -> i32; }
    let mut s = Statvfs::default();
    let rc = unsafe { statvfs(cpath.as_ptr(), &mut s) };
    if rc != 0 { return Err(format!("statvfs={rc}")); }
    Ok((s.f_blocks.saturating_mul(s.f_frsize), s.f_bavail.saturating_mul(s.f_frsize)))
}

// ===========================================================================
// GET /api/vendor/tenants + /api/vendor/stats
// ===========================================================================

#[derive(Debug, Deserialize)]
pub struct VendorTenantQuery {
    #[serde(default)] pub health: Option<String>,
    #[serde(default)] pub tier: Option<String>,
}

pub async fn vendor_tenants(
    State(state): State<AppState>,
    Query(q): Query<VendorTenantQuery>,
) -> Result<Json<Vec<serde_json::Value>>, (StatusCode, Json<AdminError>)> {
    let mut filter = Document::new();
    if let Some(h) = q.health.as_deref().filter(|s| !s.is_empty()) {
        filter.insert("health", h);
    }
    if let Some(t) = q.tier.as_deref().filter(|s| !s.is_empty()) {
        filter.insert("license_tier", t);
    }
    let opts = FindOptions::builder().sort(doc! {"mrr_eur": -1})
        .projection(doc! {"_id": 0}).build();
    let mut cur = state.db.collection::<Document>("vendor_tenants")
        .find(filter).with_options(opts).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let mut out = Vec::new();
    let now = Utc::now();
    while let Some(d) = cur.next().await {
        if let Ok(d) = d {
            let mut v: serde_json::Value = bson::from_document(d.clone())
                .unwrap_or(serde_json::Value::Null);
            // Replace last_heartbeat_at with a fresh randomized timestamp
            // (matches Python behaviour for non-OFFLINE tenants).
            if let Some(obj) = v.as_object_mut() {
                let health = obj.get("health").and_then(|s| s.as_str()).unwrap_or("").to_string();
                if health != "OFFLINE" {
                    let off = rand::rngs::OsRng.gen_range(1..=90);
                    let ts = now - chrono::Duration::seconds(off);
                    obj.insert("last_heartbeat_at".into(),
                        serde_json::json!(ts.to_rfc3339_opts(SecondsFormat::Secs, true)));
                }
            }
            out.push(v);
        }
    }
    Ok(Json(out))
}

pub async fn vendor_stats(State(state): State<AppState>)
    -> Result<Json<serde_json::Value>, (StatusCode, Json<AdminError>)>
{
    let mut cur = state.db.collection::<Document>("vendor_tenants")
        .find(doc! {}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let (mut total, mut healthy, mut degraded, mut offline) = (0_i64, 0_i64, 0_i64, 0_i64);
    let (mut nodes_total, mut nodes_active, mut seats) = (0_i64, 0_i64, 0_i64);
    let mut mrr = 0_f64;
    while let Some(d) = cur.next().await {
        if let Ok(d) = d {
            total += 1;
            match d.get_str("health").unwrap_or("") {
                "HEALTHY" => healthy += 1,
                "DEGRADED" => degraded += 1,
                "OFFLINE" => offline += 1,
                _ => {}
            }
            nodes_total += d.get_i64("nodes_total")
                .or_else(|_| d.get_i32("nodes_total").map(|v| v as i64)).unwrap_or(0);
            nodes_active += d.get_i64("nodes_active")
                .or_else(|_| d.get_i32("nodes_active").map(|v| v as i64)).unwrap_or(0);
            seats += d.get_i64("license_seats")
                .or_else(|_| d.get_i32("license_seats").map(|v| v as i64)).unwrap_or(0);
            mrr += d.get_f64("mrr_eur")
                .or_else(|_| d.get_i64("mrr_eur").map(|v| v as f64))
                .or_else(|_| d.get_i32("mrr_eur").map(|v| v as f64)).unwrap_or(0.0);
        }
    }
    Ok(Json(serde_json::json!({
        "tenants_total": total, "tenants_healthy": healthy,
        "tenants_degraded": degraded, "tenants_offline": offline,
        "nodes_total": nodes_total, "nodes_active": nodes_active,
        "seats_sold": seats, "mrr_eur": mrr, "arr_eur": mrr * 12.0,
    })))
}

// ===========================================================================
// /api/leads/* (CRUD inbox)
// ===========================================================================

#[derive(Debug, Deserialize)]
pub struct LeadListQuery {
    #[serde(default = "default_50")] pub limit: i64,
    #[serde(default)] pub status: Option<String>,
}
fn default_50() -> i64 { 50 }

pub async fn leads_list(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(q): Query<LeadListQuery>,
) -> Result<Json<Vec<Document>>, (StatusCode, Json<AdminError>)> {
    require_sovereign(&headers)?;
    let mut filter = Document::new();
    if let Some(s) = q.status.as_deref().filter(|s| !s.is_empty()) {
        filter.insert("status", s);
    }
    let opts = FindOptions::builder().sort(doc! {"received_at": -1})
        .limit(q.limit.clamp(1, 500)).projection(doc! {"_id": 0}).build();
    let mut cur = state.db.collection::<Document>("leads")
        .find(filter).with_options(opts).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let mut out = Vec::new();
    while let Some(d) = cur.next().await { if let Ok(d) = d { out.push(d); } }
    Ok(Json(out))
}

pub async fn leads_unread_count(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<AdminError>)> {
    require_sovereign(&headers)?;
    let n = state.db.collection::<Document>("leads")
        .count_documents(doc! {"read_at": bson::Bson::Null}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    Ok(Json(serde_json::json!({"unread": n})))
}

pub async fn leads_mark_read(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(lead_id): Path<String>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<AdminError>)> {
    require_sovereign(&headers)?;
    let res = state.db.collection::<Document>("leads").update_one(
        doc! {"lead_id": &lead_id, "read_at": bson::Bson::Null},
        doc! {"$set": {"read_at": utc_iso()}},
    ).await.map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    Ok(Json(serde_json::json!({
        "ok": true, "lead_id": lead_id,
        "newly_read": res.modified_count > 0,
    })))
}

pub async fn leads_read_all(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<AdminError>)> {
    require_sovereign(&headers)?;
    let res = state.db.collection::<Document>("leads").update_many(
        doc! {"read_at": bson::Bson::Null},
        doc! {"$set": {"read_at": utc_iso()}},
    ).await.map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    Ok(Json(serde_json::json!({"ok": true, "marked": res.modified_count})))
}

#[derive(Debug, Deserialize)]
pub struct LeadStatusUpdate {
    pub status: String,
    #[serde(default)] pub notes: Option<String>,
}

pub async fn leads_update(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(lead_id): Path<String>,
    Json(req): Json<LeadStatusUpdate>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<AdminError>)> {
    require_sovereign(&headers)?;
    let mut update = doc! {"status": &req.status, "updated_at": utc_iso()};
    if let Some(n) = req.notes.as_ref() {
        update.insert("follow_up_notes", n.trim());
    }
    let res = state.db.collection::<Document>("leads").update_one(
        doc! {"lead_id": &lead_id}, doc! {"$set": update},
    ).await.map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    if res.matched_count == 0 {
        return Err(err(StatusCode::NOT_FOUND, "lead not found"));
    }
    Ok(Json(serde_json::json!({"ok": true, "lead_id": lead_id, "status": req.status})))
}

// ===========================================================================
// PATCH /api/lns/{lns_name}/role
// ===========================================================================

#[derive(Debug, Deserialize)]
pub struct RoleUpdateRequest { pub role: String }

pub async fn lns_set_role(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(lns_name): Path<String>,
    Json(req): Json<RoleUpdateRequest>,
) -> Result<Json<Document>, (StatusCode, Json<AdminError>)> {
    require_sovereign(&headers)?;
    let role = req.role.trim().to_lowercase();
    if !["admin", "operator", "auditor", "vendor"].contains(&role.as_str()) {
        return Err(err(StatusCode::UNPROCESSABLE_ENTITY,
            "role must be one of: admin, operator, auditor, vendor"));
    }
    let name = lns_name.trim().to_lowercase();
    let coll = state.db.collection::<Document>("lns");
    let existing = coll.find_one(doc! {"lns_name": &name}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let existing = existing.ok_or_else(|| err(StatusCode::NOT_FOUND, format!("lns not found: {name}")))?;
    if existing.get_str("status").unwrap_or("") == "REVOKED" {
        return Err(err(StatusCode::CONFLICT, "cannot modify a revoked identity"));
    }
    coll.update_one(
        doc! {"lns_name": &name},
        doc! {"$set": {"role": &role, "role_updated_at": utc_iso()}},
    ).await.map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let updated = coll.find_one(doc! {"lns_name": &name})
        .projection(doc! {"_id": 0}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?
        .ok_or_else(|| err(StatusCode::NOT_FOUND, "lns vanished"))?;
    Ok(Json(updated))
}

// ===========================================================================
// M8 batch 3 — audit / auth / alerts
// ===========================================================================

const AUDIT_GENESIS: &str = "00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000";

/// Canonical JSON of a `Document` with sorted keys (mirrors Python
/// `json.dumps(..., sort_keys=True, separators=(',', ':'))`).
fn canon_bson(doc: &Document) -> Vec<u8> {
    let v: serde_json::Value = bson::Bson::Document(doc.clone()).into_relaxed_extjson();
    canon_value(&strip_extjson(v))
}
/// Walk a BSON-extjson value and replace `{"$numberInt":"…"}` etc with
/// plain JSON numbers/strings so the byte output matches Python's
/// `json.dumps`.
fn strip_extjson(v: serde_json::Value) -> serde_json::Value {
    match v {
        serde_json::Value::Object(map) => {
            if map.len() == 1 {
                if let Some(s) = map.get("$numberInt").and_then(|x| x.as_str()) {
                    if let Ok(n) = s.parse::<i64>() { return serde_json::json!(n); }
                }
                if let Some(s) = map.get("$numberLong").and_then(|x| x.as_str()) {
                    if let Ok(n) = s.parse::<i64>() { return serde_json::json!(n); }
                }
                if let Some(s) = map.get("$numberDouble").and_then(|x| x.as_str()) {
                    if let Ok(n) = s.parse::<f64>() { return serde_json::json!(n); }
                }
            }
            let mut out = serde_json::Map::new();
            for (k, val) in map {
                out.insert(k, strip_extjson(val));
            }
            serde_json::Value::Object(out)
        }
        serde_json::Value::Array(a) => serde_json::Value::Array(a.into_iter().map(strip_extjson).collect()),
        other => other,
    }
}
fn canon_value(v: &serde_json::Value) -> Vec<u8> {
    let mut out = Vec::new();
    write_canon(v, &mut out);
    out
}
fn write_canon(v: &serde_json::Value, out: &mut Vec<u8>) {
    match v {
        serde_json::Value::Null => out.extend_from_slice(b"null"),
        serde_json::Value::Bool(b) => out.extend_from_slice(if *b {b"true"} else {b"false"}),
        serde_json::Value::Number(n) => out.extend_from_slice(n.to_string().as_bytes()),
        serde_json::Value::String(s) => {
            // Match Python json.dumps(ensure_ascii=True): escape every
            // non-ASCII codepoint as `\uXXXX` (UTF-16 surrogate pair for
            // codepoints above U+FFFF).
            out.push(b'"');
            for c in s.chars() {
                match c {
                    '"' => out.extend_from_slice(b"\\\""),
                    '\\' => out.extend_from_slice(b"\\\\"),
                    '\n' => out.extend_from_slice(b"\\n"),
                    '\r' => out.extend_from_slice(b"\\r"),
                    '\t' => out.extend_from_slice(b"\\t"),
                    '\x08' => out.extend_from_slice(b"\\b"),
                    '\x0c' => out.extend_from_slice(b"\\f"),
                    c if (c as u32) < 0x20 => {
                        out.extend_from_slice(format!("\\u{:04x}", c as u32).as_bytes());
                    }
                    c if (c as u32) < 0x80 => {
                        out.push(c as u8);
                    }
                    c if (c as u32) <= 0xFFFF => {
                        out.extend_from_slice(format!("\\u{:04x}", c as u32).as_bytes());
                    }
                    c => {
                        // Astral plane → UTF-16 surrogate pair.
                        let cp = c as u32 - 0x10000;
                        let hi = 0xD800 + (cp >> 10);
                        let lo = 0xDC00 + (cp & 0x3FF);
                        out.extend_from_slice(format!("\\u{:04x}\\u{:04x}", hi, lo).as_bytes());
                    }
                }
            }
            out.push(b'"');
        }
        serde_json::Value::Array(a) => {
            out.push(b'[');
            for (i, x) in a.iter().enumerate() {
                if i > 0 { out.push(b','); }
                write_canon(x, out);
            }
            out.push(b']');
        }
        serde_json::Value::Object(m) => {
            let mut keys: Vec<&String> = m.keys().collect();
            keys.sort();
            out.push(b'{');
            for (i, k) in keys.iter().enumerate() {
                if i > 0 { out.push(b','); }
                write_canon(&serde_json::Value::String((*k).clone()), out);
                out.push(b':');
                write_canon(&m[*k], out);
            }
            out.push(b'}');
        }
    }
}

// -- GET /api/audit/verify (sovereign-only) ----------------------------------

pub async fn audit_verify(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<AdminError>)> {
    require_sovereign(&headers)?;
    use sha3::{Digest, Sha3_512};
    let coll = state.db.collection::<Document>("audit_log");
    let total = coll.count_documents(doc! {}).await.unwrap_or(0);
    let opts = FindOptions::builder().sort(doc! {"seq": 1}).limit(10_000)
        .projection(doc! {"_id": 0}).build();
    let mut cur = coll.find(doc! {}).with_options(opts).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let mut expected = AUDIT_GENESIS.to_string();
    let mut seq: i64 = 0;
    let mut broken_at: Option<i64> = None;
    let mut ok = true;
    while let Some(d) = cur.next().await {
        let entry = match d { Ok(d) => d, Err(_) => continue };
        let entry_seq = entry.get_i64("seq")
            .or_else(|_| entry.get_i32("seq").map(|v| v as i64)).unwrap_or(-1);
        if entry_seq != seq { ok = false; broken_at = Some(seq); break; }
        let prev_hash = entry.get_str("prev_hash").unwrap_or("");
        if prev_hash != expected { ok = false; broken_at = Some(seq); break; }
        let entry_hash = entry.get_str("entry_hash").unwrap_or("").to_string();
        let mut sans = entry.clone(); sans.remove("entry_hash");
        let canon = canon_bson(&sans);
        let mut h = Sha3_512::new(); Digest::update(&mut h, &canon);
        let recomputed = hex::encode(h.finalize());
        if recomputed != entry_hash { ok = false; broken_at = Some(seq); break; }
        expected = entry_hash;
        seq += 1;
    }
    Ok(Json(serde_json::json!({
        "ok": ok, "total_entries": total, "broken_at_seq": broken_at,
        "algorithm": "SHA3-512 hash chain", "verified_at": utc_iso(),
    })))
}

// -- POST /api/auth/logout ---------------------------------------------------

pub async fn auth_logout(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<AdminError>)> {
    let claims = jwt_decode(&headers);
    let Some(jti) = claims.as_ref().and_then(|c| c.jti.clone()) else {
        return Ok(Json(serde_json::json!({"ok": true, "noop": true, "detail": "no jwt to revoke"})));
    };
    let lns = claims.as_ref().and_then(|c| c.sub.clone());
    let ts = utc_iso();
    let _ = state.db.collection::<Document>("revoked_jwts").update_one(
        doc! {"jti": &jti},
        doc! {"$set": {"jti": &jti, "lns": lns.clone().unwrap_or_default(),
                       "revoked_at": &ts, "expires_at": &ts}},
    ).upsert(true).await;
    Ok(Json(serde_json::json!({"ok": true, "revoked": jti})))
}

// -- POST /api/auth/revoke-all -----------------------------------------------

pub async fn auth_revoke_all(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<AdminError>)> {
    let claims = jwt_decode(&headers)
        .ok_or_else(|| err(StatusCode::UNAUTHORIZED, "login required"))?;
    let lns = claims.sub.ok_or_else(|| err(StatusCode::UNAUTHORIZED, "login required"))?;
    let ts = utc_iso();
    let iat = Utc::now().timestamp();
    let _ = state.db.collection::<Document>("revoked_jwts").update_one(
        doc! {"_id": format!("nuke:{}", &lns)},
        doc! {"$set": {"lns": &lns, "nuked_at": &ts, "nuked_iat": iat}},
    ).upsert(true).await;
    Ok(Json(serde_json::json!({"ok": true, "lns": lns, "nuked_at": ts})))
}

// -- GET /api/auth/sessions / POST /api/auth/sessions/{jti}/revoke -----------

pub async fn auth_sessions_list(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<Document>>, (StatusCode, Json<AdminError>)> {
    require_sovereign(&headers)?;
    let opts = FindOptions::builder().sort(doc! {"ts": -1}).limit(200)
        .projection(doc! {"_id": 0}).build();
    let mut cur = state.db.collection::<Document>("access_log")
        .find(doc! {"event": "login_success"}).with_options(opts).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let mut out = Vec::new();
    while let Some(d) = cur.next().await { if let Ok(d) = d { out.push(d); } }
    Ok(Json(out))
}

pub async fn auth_session_revoke(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(jti): Path<String>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<AdminError>)> {
    require_sovereign(&headers)?;
    let revoker = jwt_decode(&headers).and_then(|c| c.sub).unwrap_or_default();
    let ts = utc_iso();
    let _ = state.db.collection::<Document>("revoked_jwts").update_one(
        doc! {"jti": &jti},
        doc! {"$set": {"jti": &jti, "revoked_at": &ts, "revoked_by": &revoker}},
    ).upsert(true).await;
    Ok(Json(serde_json::json!({"ok": true, "revoked_jti": jti})))
}

// -- GET /api/auth/2fa/status ------------------------------------------------

pub async fn auth_2fa_status(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<AdminError>)> {
    let lns = jwt_decode(&headers).and_then(|c| c.sub)
        .ok_or_else(|| err(StatusCode::UNAUTHORIZED, "login required"))?;
    let doc = state.db.collection::<Document>("totp_secrets")
        .find_one(doc! {"lns": &lns}).projection(doc! {"_id": 0, "verified": 1, "enrolled_at": 1}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let Some(d) = doc else {
        return Ok(Json(serde_json::json!({"enabled": false})));
    };
    Ok(Json(serde_json::json!({
        "enabled": d.get_bool("verified").unwrap_or(false),
        "enrolled_at": d.get_str("enrolled_at").unwrap_or(""),
    })))
}

// -- /api/alerts/webhooks (CRUD + test-fire) ---------------------------------

#[derive(Debug, Deserialize)]
pub struct AlertWebhookBody {
    pub url: String,
    #[serde(default)] pub severity_filter: Option<Vec<String>>,
    #[serde(default)] pub kind_filter: Option<Vec<String>>,
    #[serde(default)] pub label: Option<String>,
    #[serde(default)] pub secret_hmac: Option<String>,
}

pub async fn alerts_list(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<AdminError>)> {
    require_sovereign(&headers)?;
    let mut cur = state.db.collection::<Document>("alert_webhooks")
        .find(doc! {}).projection(doc! {"_id": 0}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let mut items = Vec::new();
    while let Some(d) = cur.next().await { if let Ok(d) = d { items.push(d); } }
    Ok(Json(serde_json::json!({"items": items, "total": items.len()})))
}

pub async fn alerts_upsert(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<AlertWebhookBody>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<AdminError>)> {
    require_sovereign(&headers)?;
    let mut doc = doc! {
        "url": &body.url,
        "label": body.label.clone().unwrap_or_default(),
        "severity_filter": bson::to_bson(&body.severity_filter.clone().unwrap_or_default()).unwrap_or(bson::Bson::Array(vec![])),
        "kind_filter": bson::to_bson(&body.kind_filter.clone().unwrap_or_default()).unwrap_or(bson::Bson::Array(vec![])),
        "secret_hmac": body.secret_hmac.clone().unwrap_or_default(),
        "created_at": utc_iso(),
        "last_fired_at": bson::Bson::Null,
        "fire_count": 0_i64,
    };
    // Strip empty fields to keep wire-compat.
    if doc.get_str("label").unwrap_or("").is_empty() { doc.remove("label"); }
    if doc.get_str("secret_hmac").unwrap_or("").is_empty() { doc.remove("secret_hmac"); }
    state.db.collection::<Document>("alert_webhooks")
        .replace_one(doc! {"url": &body.url}, doc).upsert(true).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    Ok(Json(serde_json::json!({"ok": true, "url": body.url})))
}

#[derive(Debug, Deserialize)]
pub struct DeleteWebhookQuery { pub url: String }

pub async fn alerts_delete(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(q): Query<DeleteWebhookQuery>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<AdminError>)> {
    require_sovereign(&headers)?;
    if q.url.len() < 8 {
        return Err(err(StatusCode::UNPROCESSABLE_ENTITY, "url min length 8"));
    }
    let r = state.db.collection::<Document>("alert_webhooks")
        .delete_one(doc! {"url": &q.url}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    Ok(Json(serde_json::json!({"ok": true, "deleted": r.deleted_count})))
}

#[derive(Debug, Deserialize)]
pub struct TestFireBody {
    pub url: String,
    #[serde(default)] pub message: Option<String>,
}

pub async fn alerts_test_fire(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<TestFireBody>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<AdminError>)> {
    require_sovereign(&headers)?;
    let w = state.db.collection::<Document>("alert_webhooks")
        .find_one(doc! {"url": &body.url}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?
        .ok_or_else(|| err(StatusCode::NOT_FOUND, "webhook not registered"))?;
    let msg = body.message.clone().unwrap_or_else(||
        "Test alert · Lattice Network is alive ✅".to_string());
    let payload = serde_json::json!({
        "service": "lattice-network",
        "fired_at": utc_iso(),
        "alerts": [{
            "severity": "warning", "kind": "test_fire",
            "subject": "test", "detail": msg,
        }],
    });
    // POST to webhook (best-effort, 10s timeout, optional HMAC header)
    let secret_hmac = w.get_str("secret_hmac").ok().filter(|s| !s.is_empty()).map(String::from);
    let body_bytes = serde_json::to_vec(&payload).unwrap_or_default();
    let mut req = state.http.post(&body.url)
        .header("Content-Type", "application/json")
        .header("User-Agent", "lattice-alert-bot/1.0")
        .timeout(Duration::from_secs(10))
        .body(body_bytes.clone());
    if let Some(secret) = secret_hmac {
        use hmac::{Hmac, Mac};
        use sha2::Sha256;
        if let Ok(mut mac) = Hmac::<Sha256>::new_from_slice(secret.as_bytes()) {
            mac.update(&body_bytes);
            req = req.header("X-Lattice-Signature", format!("sha256={}", hex::encode(mac.finalize().into_bytes())));
        }
    }
    let ok = req.send().await.map(|r| r.status().is_success()).unwrap_or(false);
    let _ = state.db.collection::<Document>("alert_webhooks").update_one(
        doc! {"url": &body.url},
        doc! {"$set": {"last_fired_at": utc_iso()}, "$inc": {"fire_count": 1_i64}},
    ).await;
    Ok(Json(serde_json::json!({"ok": ok})))
}


// ===========================================================================
// M8 batch 4 (lite) — mixnet topology + route preview
// ===========================================================================

#[derive(Debug, Deserialize)]
pub struct MixnetRouteRequest {
    pub origin_lns: String,
    pub destination_lns: String,
}

pub async fn mixnet_topology(State(state): State<AppState>)
    -> Result<Json<Vec<Document>>, (StatusCode, Json<AdminError>)>
{
    let opts = FindOptions::builder().sort(doc! {"layer": 1, "label": 1})
        .projection(doc! {"_id": 0}).build();
    let mut cur = state.db.collection::<Document>("mixnet_relays")
        .find(doc! {}).with_options(opts).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let mut out = Vec::new();
    while let Some(d) = cur.next().await { if let Ok(d) = d { out.push(d); } }
    Ok(Json(out))
}

pub async fn mixnet_route(
    State(state): State<AppState>,
    Json(req): Json<MixnetRouteRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<AdminError>)> {
    use sha3::{Digest, Sha3_256};
    let mut relays = Vec::<Document>::new();
    let mut cur = state.db.collection::<Document>("mixnet_relays")
        .find(doc! {}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    while let Some(d) = cur.next().await { if let Ok(d) = d { relays.push(d); } }
    if relays.len() < 3 {
        return Err(err(StatusCode::INTERNAL_SERVER_ERROR, "Mixnet topology underprovisioned"));
    }
    let mut layers: std::collections::HashMap<i64, Vec<Document>> = std::collections::HashMap::new();
    for r in &relays {
        let l = r.get_i64("layer").or_else(|_| r.get_i32("layer").map(|v| v as i64)).unwrap_or(0);
        layers.entry(l).or_default().push(r.clone());
    }
    let origin = req.origin_lns.trim().to_lowercase();
    let dest = req.destination_lns.trim().to_lowercase();
    let now = utc_iso();
    let mut sh = Sha3_256::new();
    Digest::update(&mut sh, format!("{}|{}|{}", origin, dest, now).as_bytes());
    let seed_hex = hex::encode(sh.finalize());
    let mut acc = u128::from_str_radix(&seed_hex[..16], 16).unwrap_or(0);

    let mut hops = Vec::<serde_json::Value>::new();
    let mut total = 0_i64;
    for layer in 0_i64..3 {
        let bucket = layers.get(&layer).filter(|v| !v.is_empty()).unwrap_or(&relays);
        let relay = &bucket[(acc as usize) % bucket.len()];
        let node_id = relay.get_str("node_id").unwrap_or("relay-?").to_string();
        let label = relay.get_str("label").unwrap_or("Relay").to_string();
        let region = relay.get_str("region").unwrap_or("EU-DC").to_string();
        let latency = relay.get_i64("latency_ms")
            .or_else(|_| relay.get_i32("latency_ms").map(|v| v as i64))
            .or_else(|_| relay.get_f64("latency_ms").map(|v| v as i64)).unwrap_or(40);
        let mut h2 = Sha3_256::new();
        Digest::update(&mut h2, &acc.to_be_bytes()[8..]);
        Digest::update(&mut h2, node_id.as_bytes());
        let next_hex = hex::encode(h2.finalize());
        acc = u128::from_str_radix(&next_hex[..16], 16).unwrap_or(0);
        let mut hh = Sha3_256::new();
        Digest::update(&mut hh, format!("LATTICE-LOOPIX-v1|{}|{}|layer={}|{}", origin, dest, layer, node_id).as_bytes());
        let onion_layer_hash = hex::encode(hh.finalize());
        let delay = latency + 15 * (layer + 1);
        total += delay;
        hops.push(serde_json::json!({
            "layer": layer, "relay_node_id": node_id, "relay_label": label,
            "relay_region": region, "onion_layer_hash": onion_layer_hash,
            "delay_ms": delay,
        }));
    }
    let mut ri = Sha3_256::new();
    for h in &hops {
        if let Some(s) = h.get("onion_layer_hash").and_then(|v| v.as_str()) {
            if let Ok(b) = hex::decode(s) { Digest::update(&mut ri, &b); }
        }
    }
    let route_id = format!("route-{}", &hex::encode(ri.finalize())[..24]);
    Ok(Json(serde_json::json!({
        "route_id": route_id,
        "origin_lns": origin,
        "destination_lns": dest,
        "hops": hops,
        "total_delay_ms": total,
        "cover_traffic_rate_hz": 1.5,
    })))
}

// ===========================================================================
// M8 batch 4 — QBFT alerts + logs/stream + audit SSE
// ===========================================================================

pub async fn qbft_alerts(State(state): State<AppState>)
    -> Result<Json<serde_json::Value>, (StatusCode, Json<AdminError>)>
{
    // Live validator list — fetch from our own /api/qbft/status (Rust sidecar
    // proxies to validators). Each item has {validator_id, endpoint, …}.
    let mut validators = Vec::<serde_json::Value>::new();
    if let Ok(resp) = state.http.get("http://127.0.0.1:8002/api/qbft/status")
        .timeout(Duration::from_secs(3)).send().await
    {
        if let Ok(v) = resp.json::<serde_json::Value>().await {
            if let Some(arr) = v.get("validators").and_then(|x| x.as_array()) {
                validators = arr.clone();
            }
        }
    }
    let relays_coll = state.db.collection::<Document>("mixnet_relays");
    let mut relays = Vec::<Document>::new();
    if let Ok(mut cur) = relays_coll.find(doc! {}).projection(doc! {"_id": 0}).await {
        while let Some(d) = cur.next().await { if let Ok(d) = d { relays.push(d); } }
    }

    async fn probe(http: &reqwest::Client, endpoint: &str)
        -> (&'static str, Option<f64>, Option<String>)
    {
        if endpoint.is_empty() { return ("OFFLINE", None, Some("no endpoint".into())); }
        let t0 = std::time::Instant::now();
        match http.get(format!("{}/health", endpoint.trim_end_matches('/')))
            .timeout(Duration::from_millis(1500)).send().await
        {
            Ok(r) => {
                let lat = t0.elapsed().as_secs_f64() * 1000.0;
                if r.status() == 200 { ("ONLINE", Some(lat), None) }
                else { ("DEGRADED", None, Some(format!("HTTP {}", r.status()))) }
            }
            Err(e) => ("OFFLINE", None, Some(format!("{e}").chars().take(80).collect())),
        }
    }

    let mut val_results = Vec::new();
    for v in &validators {
        let url = v.get("endpoint").and_then(|x| x.as_str()).unwrap_or("").to_string();
        val_results.push(probe(&state.http, &url).await);
    }
    let mut rel_results = Vec::new();
    for r in &relays {
        let url = r.get_str("endpoint").unwrap_or("").to_string();
        rel_results.push(probe(&state.http, &url).await);
    }

    let mut val_out = Vec::<serde_json::Value>::new();
    let mut alerts = Vec::<serde_json::Value>::new();
    let mut online_count = 0_i64;
    for (v, (st, lat, e)) in validators.iter().zip(val_results.iter()) {
        let vid = v.get("validator_id").and_then(|x| x.as_str()).unwrap_or("").to_string();
        let ep = v.get("endpoint").and_then(|x| x.as_str()).unwrap_or("").to_string();
        val_out.push(serde_json::json!({
            "label": vid, "endpoint": ep, "status": st,
            "latency_ms": lat.map(|x| (x * 10.0).round() / 10.0),
            "last_error": e,
        }));
        if *st == "ONLINE" { online_count += 1; }
        else {
            alerts.push(serde_json::json!({
                "severity":"critical","kind":"validator_unreachable",
                "subject": vid,
                "detail": format!("{} at {} → {} ({})", vid, ep, st,
                    e.clone().unwrap_or_else(|| "no response".into())),
            }));
        }
    }
    let mut mix_out = Vec::<serde_json::Value>::new();
    for (r, (st, lat, e)) in relays.iter().zip(rel_results.iter()) {
        let rid = r.get_str("node_id").unwrap_or("").to_string();
        let ep = r.get_str("endpoint").unwrap_or("").to_string();
        mix_out.push(serde_json::json!({
            "label": rid, "endpoint": ep, "status": st,
            "latency_ms": lat.map(|x| (x * 10.0).round() / 10.0),
        }));
        if *st != "ONLINE" {
            alerts.push(serde_json::json!({
                "severity":"warning","kind":"mixnet_relay_unreachable",
                "subject": rid,
                "detail": format!("{} at {} → {} ({})", rid, ep, st,
                    e.clone().unwrap_or_else(|| "no response".into())),
            }));
        }
    }
    let n = validators.len() as i64;
    let required_quorum = if n > 0 { (n / 3) * 2 + 1 } else { 1 };
    let quorum_ok = online_count >= required_quorum;
    if !quorum_ok && n > 0 {
        alerts.insert(0, serde_json::json!({
            "severity":"critical","kind":"qbft_quorum_lost","subject":"qbft",
            "detail": format!("only {}/{} validators ONLINE — need {} for BFT quorum. NO new blocks can be finalised.",
                online_count, n, required_quorum),
        }));
    }
    Ok(Json(serde_json::json!({
        "quorum_ok": quorum_ok,
        "validators_online": online_count, "validators_total": n,
        "required_quorum": required_quorum,
        "validators": val_out, "mixnet": mix_out, "alerts": alerts,
        "checked_at": utc_iso(),
    })))
}

// -- GET /api/logs/stream  (regular JSON poll) ------------------------------

#[derive(Debug, Deserialize)]
pub struct LogsQuery {
    #[serde(default = "default_80")] pub limit: i64,
}
fn default_80() -> i64 { 80 }

pub async fn logs_recent(
    State(state): State<AppState>,
    Query(q): Query<LogsQuery>,
) -> Result<Json<Vec<serde_json::Value>>, (StatusCode, Json<AdminError>)> {
    let lim = q.limit.clamp(1, 500);
    let opts = FindOptions::builder().sort(doc! {"ts": -1}).limit(lim / 4 + 1)
        .projection(doc! {"_id": 0}).build();
    let mut cur = state.db.collection::<Document>("audit_log")
        .find(doc! {}).with_options(opts).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    let mut out = Vec::new();
    while let Some(d) = cur.next().await {
        if let Ok(d) = d {
            let level = if d.get_str("event").unwrap_or("").contains("error") { "ERROR" }
                        else if d.get_str("event").unwrap_or("").contains("warning") { "WARN" } else { "INFO" };
            out.push(serde_json::json!({
                "ts": d.get_str("ts").unwrap_or(""),
                "level": level,
                "component": d.get_str("component").unwrap_or("lattice.audit"),
                "message": d.get_str("message").unwrap_or(""),
                "node_id": d.get_str("node_id").unwrap_or(""),
                "event": d.get_str("event").unwrap_or(""),
            }));
        }
    }
    Ok(Json(out))
}

// -- GET /api/audit/stream  (Server-Sent Events) ----------------------------

pub async fn audit_stream(State(state): State<AppState>) -> impl IntoResponse {
    use axum::response::sse::{Event, KeepAlive, Sse};
    use std::time::Duration;
    use async_stream::stream;
    use futures::StreamExt as _;

    let stream = stream! {
        // Replay last 20 entries quickly
        if let Ok(mut cur) = state.db.collection::<Document>("audit_log")
            .find(doc! {})
            .with_options(FindOptions::builder().sort(doc! {"seq": -1}).limit(20)
                .projection(doc! {"_id": 0}).build()).await
        {
            let mut backlog = Vec::<Document>::new();
            while let Some(d) = futures::StreamExt::next(&mut cur).await { if let Ok(d) = d { backlog.push(d); } }
            backlog.reverse();
            for d in backlog {
                let v = bson::to_bson(&d).unwrap_or_default();
                let json = serde_json::to_string(&v.into_relaxed_extjson()).unwrap_or_default();
                yield Ok::<_, std::convert::Infallible>(Event::default().event("audit").data(json));
            }
        }
        // Then poll for new entries every 2s
        let mut last_seq = state.db.collection::<Document>("audit_log")
            .find_one(doc! {}).sort(doc! {"seq": -1}).await.ok().flatten()
            .and_then(|d| d.get_i64("seq").ok().or_else(|| d.get_i32("seq").ok().map(|v| v as i64)))
            .unwrap_or(-1);
        let mut tick = tokio::time::interval(Duration::from_secs(2));
        loop {
            tick.tick().await;
            if let Ok(mut cur) = state.db.collection::<Document>("audit_log")
                .find(doc! {"seq": {"$gt": last_seq}})
                .with_options(FindOptions::builder().sort(doc! {"seq": 1}).limit(100)
                    .projection(doc! {"_id": 0}).build()).await
            {
                while let Some(d) = futures::StreamExt::next(&mut cur).await {
                    if let Ok(d) = d {
                        if let Some(s) = d.get_i64("seq").ok().or_else(|| d.get_i32("seq").ok().map(|v| v as i64)) {
                            last_seq = last_seq.max(s);
                        }
                        let v = bson::to_bson(&d).unwrap_or_default();
                        let json = serde_json::to_string(&v.into_relaxed_extjson()).unwrap_or_default();
                        yield Ok(Event::default().event("audit").data(json));
                    }
                }
            }
        }
    };
    Sse::new(stream).keep_alive(KeepAlive::default())
}

// -- POST /api/admin/license/install + reload  ------------------------------

#[derive(Debug, Deserialize)]
pub struct LicenseInstallBody {
    pub license: serde_json::Value,
}

fn canonical_for_license(payload: &serde_json::Value) -> Vec<u8> {
    // Same canonical JSON as Python `license._canonical`: sort_keys, no
    // whitespace, ensure_ascii=False (default) — we use compact serde
    // serialization sorted manually.
    let mut out = Vec::new();
    write_compact_sorted(payload, &mut out);
    out
}
fn write_compact_sorted(v: &serde_json::Value, out: &mut Vec<u8>) {
    match v {
        serde_json::Value::Object(m) => {
            let mut keys: Vec<&String> = m.keys().collect();
            keys.sort();
            out.push(b'{');
            for (i, k) in keys.iter().enumerate() {
                if i > 0 { out.push(b','); }
                out.push(b'"');
                out.extend_from_slice(k.as_bytes());
                out.push(b'"');
                out.push(b':');
                write_compact_sorted(&m[*k], out);
            }
            out.push(b'}');
        }
        serde_json::Value::Array(a) => {
            out.push(b'[');
            for (i, x) in a.iter().enumerate() {
                if i > 0 { out.push(b','); }
                write_compact_sorted(x, out);
            }
            out.push(b']');
        }
        serde_json::Value::String(s) => {
            out.extend_from_slice(&serde_json::to_vec(s).unwrap_or_default());
        }
        other => {
            out.extend_from_slice(&serde_json::to_vec(other).unwrap_or_default());
        }
    }
}

pub async fn license_install(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<LicenseInstallBody>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<AdminError>)> {
    require_sovereign(&headers)?;
    let mut lic = body.license.as_object().cloned()
        .ok_or_else(|| err(StatusCode::UNPROCESSABLE_ENTITY, "license must be a JSON object"))?;
    let sig_hex = lic.remove("signature_hex")
        .and_then(|v| v.as_str().map(String::from))
        .ok_or_else(|| err(StatusCode::UNPROCESSABLE_ENTITY, "missing signature_hex"))?;

    let vendor_hex = env::var("LATTICE_VENDOR_PUBKEY_HEX").ok()
        .filter(|s| !s.is_empty())
        .or_else(|| std::fs::read_to_string(
            std::env::var("LATTICE_DATA_DIR").unwrap_or_else(|_| "/app/backend/data".into())
                + "/vendor_pubkey.hex").ok().map(|s| s.trim().to_string()))
        .ok_or_else(|| err(StatusCode::SERVICE_UNAVAILABLE,
            "vendor public key not configured (LATTICE_VENDOR_PUBKEY_HEX)"))?;

    let pk_bytes = hex::decode(&vendor_hex)
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("vendor_pubkey: {e}")))?;
    let sig_bytes = hex::decode(&sig_hex)
        .map_err(|e| err(StatusCode::FORBIDDEN, format!("signature_hex: {e}")))?;
    if pk_bytes.len() != 1952 {
        return Err(err(StatusCode::FORBIDDEN, "vendor_pubkey must be 1952 bytes (ML-DSA-65)"));
    }
    if sig_bytes.len() != 3309 {
        return Err(err(StatusCode::FORBIDDEN, "signature must be 3309 bytes (ML-DSA-65)"));
    }

    let payload = serde_json::Value::Object(lic.clone());
    let canon = canonical_for_license(&payload);

    use pqcrypto_mldsa::mldsa65;
    use pqcrypto_traits::sign::{DetachedSignature, PublicKey};
    let pk = mldsa65::PublicKey::from_bytes(&pk_bytes)
        .map_err(|e| err(StatusCode::FORBIDDEN, format!("pk: {e:?}")))?;
    let sig = mldsa65::DetachedSignature::from_bytes(&sig_bytes)
        .map_err(|e| err(StatusCode::FORBIDDEN, format!("sig: {e:?}")))?;
    if mldsa65::verify_detached_signature(&sig, &canon, &pk).is_err() {
        return Err(err(StatusCode::FORBIDDEN, "license rejected: signature verification failed"));
    }

    // Expiry check
    if let Some(until) = lic.get("valid_until").and_then(|v| v.as_str()) {
        if let Ok(exp) = chrono::DateTime::parse_from_rfc3339(&until.replace("Z","+00:00")) {
            if exp < Utc::now() {
                return Err(err(StatusCode::FORBIDDEN, format!("license rejected: expired on {}", until)));
            }
        }
    }

    // Persist to disk
    let data_dir = env::var("LATTICE_DATA_DIR").unwrap_or_else(|_| "/app/backend/data".into());
    let lic_path = env::var("LATTICE_LICENSE_FILE").unwrap_or_else(|_| format!("{}/license.lic", data_dir));
    let _ = std::fs::create_dir_all(&data_dir);
    lic.insert("signature_hex".into(), serde_json::json!(sig_hex));
    let full_doc = serde_json::Value::Object(lic.clone());
    std::fs::write(&lic_path, serde_json::to_string(&full_doc).unwrap_or_default())
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("write license: {e}")))?;

    // Persist active state to MongoDB
    let active = bson::to_document(&lic).unwrap_or_default();
    let _ = state.db.collection::<Document>("license_state").update_one(
        doc! {"_id": "active"},
        doc! {"$set": {
            "verified": true,
            "tier": active.get_str("edition").unwrap_or("UNSET"),
            "seats": active.get_i64("max_users").or_else(|_|
                active.get_i32("max_users").map(|v| v as i64)).unwrap_or(0),
            "expires_at": active.get_str("valid_until").unwrap_or(""),
            "active": active.clone(),
            "installed_at": utc_iso(),
        }},
    ).upsert(true).await;

    Ok(Json(serde_json::json!({
        "ok": true,
        "status": {
            "ok": true,
            "tier": lic.get("edition").cloned().unwrap_or(serde_json::Value::Null),
            "seats": lic.get("max_users").cloned().unwrap_or(serde_json::Value::Null),
            "expires_at": lic.get("valid_until").cloned().unwrap_or(serde_json::Value::Null),
        }
    })))
}

pub async fn license_reload(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<AdminError>)> {
    require_sovereign(&headers)?;
    let st = state.db.collection::<Document>("license_state")
        .find_one(doc! {"_id": "active"}).await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("db: {e}")))?;
    Ok(Json(serde_json::json!({
        "ok": true,
        "status": st.map(|d| {
            let mut o = serde_json::Map::new();
            o.insert("ok".into(), serde_json::json!(d.get_bool("verified").unwrap_or(false)));
            o.insert("tier".into(), serde_json::json!(d.get_str("tier").unwrap_or("UNSET")));
            o.insert("seats".into(), serde_json::json!(d.get_i64("seats").unwrap_or(0)));
            o.insert("expires_at".into(), serde_json::json!(d.get_str("expires_at").unwrap_or("")));
            serde_json::Value::Object(o)
        }).unwrap_or(serde_json::json!({"ok": false, "tier": "UNSET"})),
    })))
}
