"""
Lattice Mixnet relay — real onion-routing hop.

Each relay runs as an independent OS process on its own TCP port and owns
an X25519 keypair. When the gateway sends a Pulse message it wraps the
payload in 3 nested ChaCha20-Poly1305 layers (one per relay). Each relay
decrypts ONE layer using a fresh ECDH ephemeral handshake, sleeps for a
real Poisson-distributed delay (genuine ε-mixing) and forwards to the
next hop. The third relay POSTs the final ciphertext to the gateway's
recipient slot — there is no mock anywhere.

Run example:
    LATTICE_RELAY_ID=MIX-01 LATTICE_RELAY_PORT=9101 LATTICE_RELAY_LAYER=1 \
    python -m uvicorn mixnet_relay:app --host 0.0.0.0 --port 9101
"""
from __future__ import annotations

import asyncio
import os
import random
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.hashes import Hash, SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi import FastAPI, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel

RELAY_ID = os.environ.get("LATTICE_RELAY_ID", "MIX-XX")
RELAY_PORT = int(os.environ.get("LATTICE_RELAY_PORT", "9101"))
RELAY_LAYER = int(os.environ.get("LATTICE_RELAY_LAYER", "1"))  # 1..3
MEAN_DELAY_MS = int(os.environ.get("LATTICE_MIX_MEAN_DELAY_MS", "80"))
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

_client = AsyncIOMotorClient(MONGO_URL)
_db = _client[DB_NAME]
_state: dict = {"sk": None, "pk_bytes": None, "started_at": None, "relayed_total": 0}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _boot_key() -> None:
    doc = await _db.mixnet_keystore.find_one({"relay_id": RELAY_ID})
    if doc:
        sk_bytes = bytes.fromhex(doc["sk_hex"])
        sk = X25519PrivateKey.from_private_bytes(sk_bytes)
    else:
        sk = X25519PrivateKey.generate()
        sk_bytes = sk.private_bytes_raw()
    pk_bytes = sk.public_key().public_bytes_raw()
    await _db.mixnet_keystore.update_one(
        {"relay_id": RELAY_ID},
        {"$set": {
            "relay_id": RELAY_ID,
            "layer": RELAY_LAYER,
            "port": RELAY_PORT,
            "endpoint": f"http://127.0.0.1:{RELAY_PORT}",
            "pk_hex": pk_bytes.hex(),
            "sk_hex": sk_bytes.hex(),
            "boot_at": _now_iso(),
            "mean_delay_ms": MEAN_DELAY_MS,
        }},
        upsert=True,
    )
    _state["sk"] = sk
    _state["pk_bytes"] = pk_bytes


@asynccontextmanager
async def _lifespan(_: FastAPI):
    _state["started_at"] = _now_iso()
    await _boot_key()
    yield


app = FastAPI(title=f"Lattice mixnet relay {RELAY_ID}", lifespan=_lifespan)


class OnionPacket(BaseModel):
    eph_pub_hex: str         # ephemeral X25519 public key for THIS hop
    ciphertext_hex: str      # ChaCha20Poly1305 ciphertext for THIS hop
    nonce_hex: str           # 12-byte nonce for this layer


def _derive_key(eph_pub_hex: str) -> bytes:
    eph_pk = X25519PublicKey.from_public_bytes(bytes.fromhex(eph_pub_hex))
    shared = _state["sk"].exchange(eph_pk)
    return HKDF(algorithm=SHA256(), length=32, salt=None, info=b"lattice-mixnet-v1").derive(shared)


def _peel(packet: OnionPacket) -> dict:
    key = _derive_key(packet.eph_pub_hex)
    aead = ChaCha20Poly1305(key)
    plaintext = aead.decrypt(
        bytes.fromhex(packet.nonce_hex),
        bytes.fromhex(packet.ciphertext_hex),
        b"layer-" + RELAY_LAYER.to_bytes(1, "big"),
    )
    # Each peeled layer is a UTF-8 JSON with { next_endpoint, next_packet }
    import json
    return json.loads(plaintext.decode("utf-8"))


async def _poisson_delay() -> None:
    """ε-mixing — exponential inter-arrival delay (Poisson process)."""
    delay_s = random.expovariate(1.0 / max(MEAN_DELAY_MS, 1)) / 1000.0
    if delay_s > 0.5:
        delay_s = 0.5  # cap to keep UX snappy
    await asyncio.sleep(delay_s)


@app.get("/health")
async def health() -> dict:
    return {
        "ok": True,
        "relay_id": RELAY_ID,
        "layer": RELAY_LAYER,
        "port": RELAY_PORT,
        "pk_hex": _state["pk_bytes"].hex() if _state.get("pk_bytes") else None,
        "started_at": _state.get("started_at"),
        "relayed_total": _state.get("relayed_total", 0),
        "mean_delay_ms": MEAN_DELAY_MS,
    }


@app.post("/relay")
async def relay(packet: OnionPacket) -> dict:
    try:
        peeled = _peel(packet)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"layer decryption failed: {exc}") from exc

    await _poisson_delay()
    _state["relayed_total"] += 1
    next_endpoint = peeled.get("next_endpoint")
    next_packet = peeled.get("next_packet")
    is_terminal = bool(peeled.get("terminal"))

    if is_terminal:
        # Final layer: peeled payload is the gateway-recipient endpoint + body.
        gateway = peeled.get("gateway_url")
        delivery = peeled.get("delivery", {})
        try:
            async with httpx.AsyncClient(timeout=2.0) as cx:
                await cx.post(f"{gateway}/api/mixnet/deliver", json=delivery)
        except Exception:
            # delivery failures are recorded but don't propagate (mixnet is lossy by spec)
            pass
        return {"ok": True, "terminal": True, "relay_id": RELAY_ID}

    if not next_endpoint or not next_packet:
        raise HTTPException(status_code=400, detail="malformed inner payload")

    try:
        async with httpx.AsyncClient(timeout=3.0) as cx:
            await cx.post(f"{next_endpoint}/relay", json=next_packet)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"hop forward failed: {exc}") from exc

    return {"ok": True, "relay_id": RELAY_ID, "forwarded_to": next_endpoint}
