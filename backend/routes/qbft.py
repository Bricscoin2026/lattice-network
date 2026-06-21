"""
Lattice Network — /api/qbft/* read-only routes (Iter_33)
=========================================================

Validator health, status and alerting endpoints. All read-only — they
probe each `/qbft/<id>/health` endpoint live and reconcile against the
`db.qbft_nodes` collection.

The mutating side of QBFT (block proposal / vote collection /
finalisation) lives in `qbft_node.py` (each validator is a separate
uvicorn process) and is exercised via internal HTTP — NOT exposed as
a public REST API. So nothing else needs to move into this module.

Two functions defined here are reused by admin_health.py and by server
startup → they are `await`-able as module-level coroutines:
    `qbft_status(db)`
    `qbft_alerts(db)`
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, List

import httpx
from fastapi import APIRouter

import core
from models import QbftNode

router = APIRouter(prefix="/qbft", tags=["qbft"])


async def qbft_status(db: Any, *, quorum_required: int) -> dict:
    """Validator status — used by /api/qbft/status AND by /admin/health."""
    validators = await core.qbft_known_validators()

    async def _ping(v: dict) -> dict:
        url = f"{v['endpoint']}/health"
        info = dict(v)
        try:
            async with httpx.AsyncClient(timeout=1.5) as cx:
                r = await cx.get(url)
                if r.status_code == 200:
                    body = r.json()
                    info["live"] = True
                    info["signed_total"] = body.get("signed_total", 0)
                else:
                    info["live"] = False
        except Exception:
            info["live"] = False
        return info

    enriched = await asyncio.gather(*[_ping(v) for v in validators]) if validators else []
    live = [v for v in enriched if v.get("live")]
    return {
        "validators": list(enriched),
        "live_count": len(live),
        "total_count": len(enriched),
        "quorum_required": quorum_required,
        "quorum_reached": len(live) >= quorum_required,
        "consensus": "QBFT · ML-DSA-65 votes · n=4 f=1",
        "implementation": "4 independent uvicorn processes on 127.0.0.1:9001-9004",
    }


async def qbft_nodes(db: Any) -> List[QbftNode]:
    """Live validator process status — reconciles DB + live ping."""
    cursor = db.qbft_nodes.find({}, {"_id": 0}).sort("label", 1)
    base_nodes = [doc async for doc in cursor]
    validators = await core.qbft_known_validators()
    by_label = {v["validator_id"]: v for v in validators}

    async def _ping(v):
        try:
            async with httpx.AsyncClient(timeout=2.0) as cx:
                r = await cx.get(f"{v['endpoint']}/health")
                if r.status_code == 200:
                    return r.json()
        except Exception:
            pass
        return None

    statuses = await asyncio.gather(*[_ping(v) for v in validators]) if validators else []
    by_id = {}
    for v, s in zip(validators, statuses):
        if s:
            by_id[v["validator_id"]] = s

    out: List[QbftNode] = []
    now_iso = core.utc_iso()
    for n in base_nodes:
        label = n["label"]
        live = by_id.get(label)
        if live:
            n["status"] = "ONLINE"
            n["blocks_proposed"] = int(live.get("signed_total", 0))
            n["last_seen"] = now_iso
            n["cpu_pct"] = 0.0
            n["mem_pct"] = 0.0
        elif label in by_label:
            n["status"] = "DEGRADED"
        else:
            n["status"] = "OFFLINE"
        await db.qbft_nodes.update_one(
            {"node_id": n["node_id"]},
            {"$set": {
                "status": n["status"],
                "blocks_proposed": n["blocks_proposed"],
                "last_seen": n["last_seen"],
                "cpu_pct": n["cpu_pct"],
                "mem_pct": n["mem_pct"],
            }},
        )
        out.append(QbftNode(**n))
    return out


async def qbft_alerts(db: Any) -> dict:
    """Health alerts for validators + mixnet relays."""
    validators = await core.qbft_known_validators()
    relays: List[dict] = []
    try:
        async for r in db.mixnet_topology.find({}, {"_id": 0}):
            relays.append(r)
    except Exception:
        relays = []

    async def _probe(url: str):
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=1.5) as cx:
                r = await cx.get(url + "/health")
                if r.status_code == 200:
                    return "ONLINE", (time.monotonic() - t0) * 1000, None
                return "DEGRADED", None, f"HTTP {r.status_code}"
        except Exception as e:
            return "OFFLINE", None, str(e)[:80]

    v_results = await asyncio.gather(*[_probe(v["endpoint"]) for v in validators]) if validators else []
    r_results = await asyncio.gather(*[_probe(r["endpoint"]) for r in relays]) if relays else []

    val_out, alerts = [], []
    online_count = 0
    for v, (st, lat, err) in zip(validators, v_results):
        val_out.append({
            "label": v["validator_id"], "endpoint": v["endpoint"],
            "status": st, "latency_ms": round(lat, 1) if lat else None,
            "last_error": err,
        })
        if st == "ONLINE":
            online_count += 1
        else:
            alerts.append({
                "severity": "critical", "kind": "validator_unreachable",
                "subject": v["validator_id"],
                "detail": f"{v['validator_id']} at {v['endpoint']} → {st} ({err or 'no response'})",
            })

    mix_out = []
    for relay, (st, lat, err) in zip(relays, r_results):
        mix_out.append({
            "label": relay.get("relay_id"), "endpoint": relay.get("endpoint"),
            "status": st, "latency_ms": round(lat, 1) if lat else None,
        })
        if st != "ONLINE":
            alerts.append({
                "severity": "warning", "kind": "mixnet_relay_unreachable",
                "subject": relay.get("relay_id"),
                "detail": f"{relay.get('relay_id')} at {relay.get('endpoint')} → {st} ({err or 'no response'})",
            })

    required_quorum = (len(validators) // 3) * 2 + 1 if validators else 1
    quorum_ok = online_count >= required_quorum
    if not quorum_ok and validators:
        alerts.insert(0, {
            "severity": "critical", "kind": "qbft_quorum_lost",
            "subject": "qbft",
            "detail": (
                f"only {online_count}/{len(validators)} validators ONLINE — "
                f"need {required_quorum} for BFT quorum. NO new blocks can be finalised."
            ),
        })

    return {
        "quorum_ok": quorum_ok,
        "validators_online": online_count,
        "validators_total": len(validators),
        "required_quorum": required_quorum,
        "validators": val_out,
        "mixnet": mix_out,
        "alerts": alerts,
        "checked_at": core.utc_iso(),
    }


def register(api: APIRouter, *, db: Any, quorum_required: int) -> None:
    @router.get("/status")
    async def _qbft_status() -> dict:
        return await qbft_status(db, quorum_required=quorum_required)

    @router.get("/nodes", response_model=List[QbftNode])
    async def _qbft_nodes() -> List[QbftNode]:
        return await qbft_nodes(db)

    @router.get("/alerts")
    async def _qbft_alerts() -> dict:
        return await qbft_alerts(db)

    api.include_router(router)
