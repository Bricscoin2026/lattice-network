"""
Lattice Network — /api/admin/health/* routes (Iter_30)
=======================================================

Single-pane operational overview for the SysAdmin. Aggregates:
    - validators (QBFT), mixnet, chain metrics
    - secrets + license status, OTS Bitcoin anchor summary
    - disk usage, active alerts
"""
from __future__ import annotations

import shutil
from typing import Any, Callable, Dict

from fastapi import APIRouter

import secret_manager
import license as licmod
import ots_anchor

router = APIRouter(prefix="/admin/health", tags=["admin-health"])


def register(
    api: APIRouter,
    *,
    db: Any,
    utc_iso: Callable,
    qbft_status_fn: Callable,
    mixnet_status_fn: Callable,
    alert_state: Dict[str, str],
    compliance_mode: bool,
    chain_id: str,
) -> None:
    @router.get("/overview")
    async def health_overview() -> dict:
        """SysAdmin one-pane: validators+mixnet+chain+disk+secrets+license+ots+alerts."""
        out: Dict[str, Any] = {
            "timestamp": utc_iso(),
            "secrets": secret_manager.status(),
            "license": licmod.status(),
            "compliance_mode": compliance_mode,
            "chain_id": chain_id,
            "ots": {
                "enabled": ots_anchor.is_enabled(),
                "calendars": ots_anchor._calendars(),  # noqa: SLF001 — read-only
                "anchors_total": await db.ots_anchors.count_documents({}),
                "btc_attested": await db.ots_anchors.count_documents({"btc_attested": True}),
            },
        }

        try:
            qbft = await qbft_status_fn()
            out["validators"] = {
                "total": qbft.get("total_count", 0),
                "online": qbft.get("live_count", 0),
                "quorum_required": qbft.get("quorum_required"),
                "quorum_reached": qbft.get("quorum_reached"),
                "consensus": qbft.get("consensus"),
                "nodes": qbft.get("validators") or [],
            }
        except Exception as e:
            out["validators"] = {"error": str(e)}

        try:
            mix = await mixnet_status_fn()
            relays = mix.get("relays") or []
            out["mixnet"] = {
                "enabled": mix.get("enabled", False),
                "total": len(relays),
                "online": sum(1 for r in relays if r.get("status") == "ONLINE" or r.get("live")),
            }
        except Exception as e:
            out["mixnet"] = {"error": str(e)}

        try:
            out["chain"] = {
                "blocks": await db.blocks.count_documents({}),
                "transactions": await db.transactions.count_documents({}),
                "lns_identities": await db.lns.count_documents({}),
                "tenants": await db.tenants.count_documents({}),
                "certify_mails": await db.certify_mails.count_documents({}),
                "pulse_messages": await db.pulse_messages.count_documents({}),
            }
        except Exception as e:
            out["chain"] = {"error": str(e)}

        try:
            du = shutil.disk_usage("/app/backend")
            out["disk"] = {
                "total_bytes": du.total,
                "used_bytes": du.used,
                "free_bytes": du.free,
                "used_pct": round((du.used / du.total) * 100, 1) if du.total else 0,
            }
        except Exception as e:
            out["disk"] = {"error": str(e)}

        out["alerts"] = [{"key": k, "severity": v} for k, v in alert_state.items()]
        return out

    api.include_router(router)
