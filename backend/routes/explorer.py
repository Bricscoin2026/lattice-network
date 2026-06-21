"""Public Block Explorer — /api/explorer/* (Iter_41)
Endpoint pubblici (no auth) per verifica indipendente trasparente.
"""
from __future__ import annotations
from typing import Any, Callable
import re
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/explorer", tags=["explorer"])


def register(api: APIRouter, *, db: Any, pqc_verify_fn: Callable,
             tx_canonical_message_fn: Callable, pqc_algorithm: str) -> None:

    @router.get("/stats")
    async def explorer_stats():
        """Statistiche pubbliche della blockchain + ultimi 10 blocchi + ultime 10 tx."""
        last_block = await db.blocks.find_one({}, {"_id": 0}, sort=[("index", -1)])
        block_height = (last_block["index"] if last_block else 0)
        tx_total = await db.transactions.count_documents({})
        lns_total = await db.lns.count_documents({})
        mails_total = await db.certify_mails.count_documents({})
        try:
            pulses_total = await db.pulse_messages.count_documents({})
        except Exception:
            pulses_total = 0
        recent_blocks = await db.blocks.find(
            {},
            {"_id": 0, "proposer_signature": 0, "qbft_votes": 0},
        ).sort("index", -1).limit(10).to_list(None)
        recent_txs = await db.transactions.find(
            {},
            {"_id": 0, "signature": 0},
        ).sort("block_index", -1).limit(10).to_list(None)
        return {
            "chain_id": "lattice-sovereign-it-prod",
            "algorithm": pqc_algorithm,
            "block_height": block_height,
            "total_transactions": tx_total,
            "total_lns": lns_total,
            "total_mails": mails_total,
            "total_pulses": pulses_total,
            "last_block_hash": last_block["block_hash"] if last_block else "",
            "last_block_at": last_block["timestamp"] if last_block else "",
            "recent_blocks": recent_blocks,
            "recent_transactions": recent_txs,
        }

    @router.get("/search")
    async def explorer_search(q: str = Query(..., min_length=3, max_length=200)):
        """Ricerca universale: indovina il tipo dell'input e restituisce
        il record corrispondente. Supporta: tx_id, doc_hash, block_index,
        lns_name, fingerprint di chiave pubblica."""
        q = q.strip()
        # 1. tx_id prefix
        if q.startswith("tx-"):
            tx = await db.transactions.find_one({"tx_id": q}, {"_id": 0})
            if tx:
                return {"type": "transaction", "result": tx}
        # 2. block_index (numero puro)
        if q.isdigit():
            blk = await db.blocks.find_one({"index": int(q)}, {"_id": 0})
            if blk:
                return {"type": "block", "result": blk}
        # 3. doc_hash (esadecimale lungo)
        if re.fullmatch(r"[0-9a-fA-F]{32,256}", q):
            tx = await db.transactions.find_one({"doc_hash": q.lower()}, {"_id": 0})
            if tx:
                return {"type": "transaction", "result": tx, "matched_by": "doc_hash"}
            # Try as mail_id prefix doc_hash
            mail = await db.certify_mails.find_one({"doc_hash": q.lower()}, {"_id": 0})
            if mail:
                return {"type": "mail", "result": mail}
        # 4. mail_id
        if q.startswith("mail-"):
            mail = await db.certify_mails.find_one({"mail_id": q}, {"_id": 0})
            if mail:
                tx = await db.transactions.find_one({"tx_id": mail.get("tx_id")}, {"_id": 0})
                return {"type": "mail", "result": mail, "anchor_tx": tx}
        # 5. LNS name
        if "." in q or q.startswith("VAL-") or q.startswith("OBS-"):
            lns = await db.lns.find_one({"lns_name": q.lower()}, {"_id": 0})
            if lns:
                ks = await db.keystore.find_one({"entity": q.lower()}, {"_id": 0})
                return {"type": "lns", "result": lns, "keystore": ks}
            ks = await db.keystore.find_one({"entity": q}, {"_id": 0})
            if ks:
                return {"type": "keystore", "result": ks}
        raise HTTPException(status_code=404, detail=f"Nessuna corrispondenza per '{q}'")

    @router.get("/tx/{tx_id}")
    async def explorer_tx(tx_id: str):
        """Dettaglio transazione + verifica matematica della firma."""
        tx = await db.transactions.find_one({"tx_id": tx_id}, {"_id": 0})
        if not tx:
            raise HTTPException(status_code=404, detail="transaction not found")
        block = await db.blocks.find_one({"index": tx.get("block_index")}, {"_id": 0})
        # Verifica firma
        signer = tx.get("signer_entity")
        verified = None
        verify_detail = ""
        if signer and tx.get("signed_with") == pqc_algorithm:
            try:
                msg = tx_canonical_message_fn(tx)
                verified = await pqc_verify_fn(signer, msg, tx.get("signature", ""))
                verify_detail = "Firma ML-DSA-65 verificata matematicamente contro la chiave pubblica del firmatario." if verified else "Firma NON valida — bytes manomessi o chiave ruotata."
            except Exception as e:
                verified = False
                verify_detail = f"Errore di verifica: {type(e).__name__}"
        else:
            verify_detail = "Transazione legacy (seed) — non firmata con ML-DSA-65 reale."
        return {
            "transaction": tx, "block": block,
            "verified": verified, "verify_detail": verify_detail,
            "algorithm": pqc_algorithm,
        }

    @router.get("/block/{block_index}")
    async def explorer_block(block_index: int):
        """Dettaglio blocco + lista transazioni + firme validatori."""
        block = await db.blocks.find_one({"index": block_index}, {"_id": 0})
        if not block:
            raise HTTPException(status_code=404, detail="block not found")
        txs = await db.transactions.find({"block_index": block_index}, {"_id": 0}).to_list(None)
        prev_block = await db.blocks.find_one({"index": block_index - 1}, {"_id": 0, "block_hash": 1, "index": 1})
        next_block = await db.blocks.find_one({"index": block_index + 1}, {"_id": 0, "block_hash": 1, "index": 1})
        return {"block": block, "transactions": txs, "prev": prev_block, "next": next_block}

    @router.get("/lns/{lns_name}")
    async def explorer_lns(lns_name: str):
        """Dettaglio LNS + chiave pubblica + ultime transazioni firmate."""
        name = lns_name.strip().lower()
        lns = await db.lns.find_one({"lns_name": name}, {"_id": 0})
        if not lns:
            raise HTTPException(status_code=404, detail="lns not found")
        keystore = await db.keystore.find_one({"entity": name}, {"_id": 0})
        txs = await db.transactions.find({"signer_entity": name}, {"_id": 0}).sort("block_index", -1).limit(20).to_list(None)
        return {"lns": lns, "keystore": keystore, "recent_transactions": txs}

    api.include_router(router)
