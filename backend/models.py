"""
Lattice Network — Pydantic wire-format models
==============================================

Extracted from server.py (Iter_32) to break the circular import chain
that blocked the lns/certify/pulse route extractions.

This module is **side-effect free**: no db handle, no logger, no env
var reads. It only declares the JSON shape contracts.

Smaller request/response models that are used by a single endpoint are
intentionally left inline next to their handler in server.py — extracting
them too aggressively just creates noise.
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Ledger / Chain
# ---------------------------------------------------------------------------


class LedgerStats(BaseModel):
    block_height: int
    total_transactions: int
    pending_transactions: int
    finality_ms: int
    chain_id: str
    last_block_hash: str
    last_block_at: str
    qbft_round: int


class Block(BaseModel):
    model_config = ConfigDict(extra="ignore")
    index: int
    timestamp: str
    transactions_count: int
    previous_hash: str
    block_hash: str
    proposer: str
    state_root: str = "0" * 128
    extrinsics_root: str = "0" * 128
    events_count: int = 0
    weight_used: int = 0
    digest: str = ""
    signed_with: Optional[str] = None
    qbft_quorum: Optional[int] = None
    qbft_total_validators: Optional[int] = None
    qbft_votes: Optional[List[dict]] = None
    proposer_pk_fingerprint: Optional[str] = None
    chain_id: Optional[str] = None
    merkle_root: Optional[str] = None
    tx_ids: Optional[List[str]] = None


class Transaction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tx_id: str
    block_index: int
    timestamp: str
    kind: Literal[
        "IdentityRegister", "NotarySeal", "IdentityRevoke", "IdentityDelete",
        "DeliveryReceipt", "LeadCapture", "KeyShareEnroll", "KeyShareRecover",
        "PulseAnchor", "EncPkRotate",
    ]
    summary: str
    sender_public_key: str
    signature: str
    nonce: int = 0
    weight: int = 10_000


# ---------------------------------------------------------------------------
# QBFT
# ---------------------------------------------------------------------------


class QbftNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    node_id: str
    label: str
    region: str
    role: Literal["proposer", "validator", "observer"]
    status: Literal["ONLINE", "DEGRADED", "OFFLINE"]
    voting_power: int
    blocks_proposed: int
    last_seen: str
    cpu_pct: float
    mem_pct: float
    version: str


# ---------------------------------------------------------------------------
# LNS
# ---------------------------------------------------------------------------


class LnsRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    lns_name: str
    did: str
    public_key_fingerprint: str
    registered_at: str
    status: Literal["ACTIVE", "REVOKED"]
    department: str
    display_name: Optional[str] = None
    revoked_at: Optional[str] = None
    tenant_id: Optional[str] = None
    role: Optional[str] = None
    enc_pk_hex: Optional[str] = None


class RevokeRequest(BaseModel):
    lns_name: str
    reason: str = "Administrative revocation"
    admin: str = "console.admin"


class RevokeResponse(BaseModel):
    ok: bool
    tx_id: str
    block_index: int
    lns_name: str
    timestamp: str


class RegisterRequest(BaseModel):
    lns_name: str = Field(..., min_length=3, max_length=128)
    department: str = "Operations"
    admin: str = "console.admin"
    display_name: Optional[str] = Field(default=None, max_length=128)
    tenant_id: Optional[str] = None
    role: Literal["admin", "operator", "auditor", "vendor"] = "operator"
    public_key_hex: Optional[str] = Field(default=None, min_length=3904, max_length=3904)
    enc_public_key_hex: Optional[str] = Field(default=None, min_length=64, max_length=64)


class RegisterResponse(BaseModel):
    ok: bool
    tx_id: str
    block_index: int
    lns_name: str
    did: str
    public_key_fingerprint: str
    timestamp: str
    role: str = "operator"
    tenant_id: Optional[str] = None
    public_key_hex: Optional[str] = None
    secret_key_hex: Optional[str] = None
    keypair_filename: Optional[str] = None


class LnsCheckResponse(BaseModel):
    lns_name: str
    normalized: str
    available: bool
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Tenants
# ---------------------------------------------------------------------------


class TenantRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=64)
    domain_prefix: str = Field(
        ..., min_length=2, max_length=32,
        pattern=r"^[a-z][a-z0-9-]{1,30}[a-z0-9]$",
        description="lowercase slug; final domain is <prefix>.lns",
    )
    admin_lns_prefix: str = Field(
        ..., min_length=2, max_length=32,
        pattern=r"^[a-z][a-z0-9.-]{1,30}[a-z0-9]$",
        description="lowercase slug for the first admin employee",
    )
    admin_display_name: str = Field(..., min_length=2, max_length=64)


class TenantRegisterResponse(BaseModel):
    ok: bool
    tenant_id: str
    name: str
    domain: str
    admin_lns: str
    admin_did: str
    admin_tx_id: str
    block_index: int
    created_at: str
    admin_keypair_json: Optional[dict] = None


class TenantRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tenant_id: str
    name: str
    domain: str
    admin_lns: str
    created_at: str
    employees_count: int = 0


# ---------------------------------------------------------------------------
# Certify (mail)
# ---------------------------------------------------------------------------


class CertifyStats(BaseModel):
    total_notarized: int
    last_24h: int
    last_7d: int
    bytes_sealed: int
    avg_seal_ms: float


class CertifyMail(BaseModel):
    model_config = ConfigDict(extra="ignore")
    mail_id: str
    sender_lns: str
    recipient_lns: str
    subject_redacted: str
    doc_hash: str
    sealed_at: str
    bytes: int
    subject: Optional[str] = None
    body: Optional[str] = None
    classification: Optional[str] = None
    tx_id: Optional[str] = None
    block_index: Optional[int] = None
    read_at: Optional[str] = None
    attachments: Optional[List[dict]] = None
    delivery_receipt: Optional[dict] = None


class CertifyComposeRequest(BaseModel):
    sender_lns: str
    recipient_lns: Optional[str] = None
    recipients_lns: Optional[List[str]] = None
    cc_lns: Optional[List[str]] = None
    subject: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=20_000)
    classification: Literal["INTERNAL", "CONFIDENTIAL", "RESTRICTED", "LEGAL-HOLD"] = "INTERNAL"
    attachment_ids: Optional[List[str]] = None
    body_e2e_envelope: Optional[dict] = None


class CertifyComposeResponse(BaseModel):
    ok: bool
    mail_id: str
    tx_id: str
    block_index: int
    doc_hash: str
    sealed_at: str
    fanout: int = 1


# ---------------------------------------------------------------------------
# Pulse (chat)
# ---------------------------------------------------------------------------


class PulseConversation(BaseModel):
    conv_id: str
    participants: List[str]
    message_count: int
    last_message_at: Optional[str] = None
    last_anchor_tx: Optional[str] = None
    last_anchor_block: Optional[int] = None


class PulseMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    msg_id: str
    conv_id: str
    from_lns: str
    to_lns: str
    ciphertext_hex: str
    nonce_hex: str
    sealed_at: str
    anchor_tx_id: Optional[str] = None
    plaintext: Optional[str] = None
    delivered_at: Optional[str] = None
    read_at: Optional[str] = None
    attachments: Optional[List[dict]] = None


class PulseSendRequest(BaseModel):
    from_lns: str
    to_lns: Optional[str] = None
    recipients_lns: Optional[List[str]] = None
    plaintext: str = Field(default="", max_length=8_000)
    rln_proof: Optional[dict] = None
    attachment_ids: Optional[List[str]] = None


class PulseSendResponse(BaseModel):
    ok: bool
    msg_id: str
    conv_id: str
    ciphertext_hex: str
    nonce_hex: str
    sealed_at: str
    anchor_tx_id: Optional[str] = None
    anchor_block_index: Optional[int] = None
    session_fingerprint: str
    epoch: int
    message_number: int
    route_id: str
    route_hops: List[dict]
    rln_slot_used: int
    rln_slot_max: int
    fanout: int = 1
    fanout_results: Optional[List[dict]] = None


class PulseSession(BaseModel):
    conv_id: str
    participants: List[str]
    fingerprint: str
    epoch: int
    message_number: int
    root_key_fingerprint: str
    started_at: str
    cipher_suite: str = "PQXDH(ML-KEM-768) + Double-Ratchet · AEAD: AES-256-GCM"


# ---------------------------------------------------------------------------
# Mixnet
# ---------------------------------------------------------------------------


class MixnetRelay(BaseModel):
    node_id: str
    label: str
    region: str
    layer: int
    kem_pk_fingerprint: str
    latency_ms: int


class MixnetHop(BaseModel):
    layer: int
    relay_node_id: str
    relay_label: str
    relay_region: str
    onion_layer_hash: str
    delay_ms: int


class MixnetRoute(BaseModel):
    route_id: str
    origin_lns: str
    destination_lns: str
    hops: List[MixnetHop]
    total_delay_ms: int
    cover_traffic_rate_hz: float


class MixnetRouteRequest(BaseModel):
    origin_lns: str
    destination_lns: str


# ---------------------------------------------------------------------------
# RLN (rate-limit nullifier)
# ---------------------------------------------------------------------------


class RlnQuota(BaseModel):
    lns: str
    epoch: int
    epoch_seconds: int
    used: int
    max_per_epoch: int
    nullifier_seed: str


# ---------------------------------------------------------------------------
# Vendor / Logs
# ---------------------------------------------------------------------------


class LogLine(BaseModel):
    model_config = ConfigDict(extra="ignore")
    ts: str
    node_id: str
    level: Literal["INFO", "WARN", "ERROR", "AUDIT"]
    component: str
    message: str


class VendorTenant(BaseModel):
    tenant_id: str
    name: str
    domain: str
    industry: str
    country: str
    license_tier: Literal["TRIAL", "STANDARD", "ENTERPRISE", "SOVEREIGN"]
    license_seats: int
    license_started_at: str
    license_expires_at: str
    deployment_url: str
    nodes_active: int
    nodes_total: int
    block_height_seen: int
    last_heartbeat_at: str
    health: Literal["HEALTHY", "DEGRADED", "OFFLINE"]
    mrr_eur: int


class VendorStats(BaseModel):
    tenants_total: int
    tenants_healthy: int
    tenants_degraded: int
    tenants_offline: int
    nodes_total: int
    nodes_active: int
    seats_sold: int
    mrr_eur: int
    arr_eur: int
    data_residency: str = (
        "Sovereign — all message bodies, LNS keys and Pulse ciphertext "
        "live ONLY on each tenant's on-premise cluster. The vendor "
        "operations console persists ONLY operational metadata "
        "(license tier, node count, heartbeat). NO customer payload is "
        "ever transmitted to or stored by the vendor."
    )


# ---------------------------------------------------------------------------
# Alert webhooks
# ---------------------------------------------------------------------------


class AlertWebhook(BaseModel):
    url: str = Field(..., min_length=8, max_length=512)
    label: str = Field(..., min_length=1, max_length=64)
    kind: Literal["slack", "telegram", "generic"] = "generic"
    extra: Optional[dict] = None
    severity_filter: Literal["all", "critical_only"] = "all"
    enabled: bool = True


__all__ = [
    "LedgerStats", "Block", "Transaction",
    "QbftNode",
    "LnsRecord", "RevokeRequest", "RevokeResponse",
    "RegisterRequest", "RegisterResponse", "LnsCheckResponse",
    "TenantRegisterRequest", "TenantRegisterResponse", "TenantRecord",
    "CertifyStats", "CertifyMail", "CertifyComposeRequest", "CertifyComposeResponse",
    "PulseConversation", "PulseMessage", "PulseSendRequest", "PulseSendResponse", "PulseSession",
    "MixnetRelay", "MixnetHop", "MixnetRoute", "MixnetRouteRequest",
    "RlnQuota",
    "LogLine",
    "VendorTenant", "VendorStats",
    "AlertWebhook",
]
