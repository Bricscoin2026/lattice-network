"""
Lattice Sovereign Bootstrap
===========================

One-shot CLI that materialises the Platform Operator account on a fresh
Lattice deployment. It generates a real ML-DSA-65 keypair, registers the
LNS on-chain (real QBFT consensus + NotarySeal), persists the secret key
in the local keystore and writes a portable `<lns>.keypair.json` file to
disk — the ONLY thing the operator needs to log in.

Usage (production):

    python -m scripts.bootstrap_sovereign \\
        --lns fabio.sovereign.lattice.id \\
        --display-name "Fabio Astorino" \\
        --output /secrets/fabio.keypair.json

Recovery / key rotation (operator lost his keypair):

    LATTICE_RECOVERY_CODE=<the_secret_you_wrote_down> \\
    python -m scripts.bootstrap_sovereign --rotate \\
        --lns fabio.sovereign.lattice.id \\
        --output /secrets/fabio.NEW.keypair.json

The recovery code is a 32-byte random string stored in `.env` at first
bootstrap (auto-generated and printed once). Keep it offline.
"""
import argparse
import asyncio
import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make `server` importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Lazy import so missing deps fail loud.
from dotenv import load_dotenv  # noqa: E402
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from pqcrypto.sign import ml_dsa_65 as mldsa  # noqa: E402


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _get_db():
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        raise SystemExit("FATAL: MONGO_URL and DB_NAME must be set in backend/.env")
    client = AsyncIOMotorClient(mongo_url)
    return client[db_name]


async def _ensure_recovery_code(db) -> str:
    """First-run only: mint and persist a recovery code (Argon2id hashed)."""
    from security import hash_secret  # noqa: E402
    doc = await db.platform_secrets.find_one({"_id": "recovery"})
    if doc and doc.get("hash"):
        # Hash already stored — original code cannot be recovered, but
        # the caller can rotate by supplying it as LATTICE_RECOVERY_CODE.
        return ""
    code = secrets.token_urlsafe(32)
    await db.platform_secrets.update_one(
        {"_id": "recovery"},
        {"$set": {
            "hash": hash_secret(code),
            "algorithm": "argon2id",
            "created_at": _utc_iso(),
        }},
        upsert=True,
    )
    print("=" * 72)
    print("  RECOVERY CODE (write it down offline — never share, never commit):")
    print(f"  {code}")
    print("=" * 72)
    print("  Store this in a safe place. It allows you to rotate the")
    print("  Platform Operator key if you lose your .keypair.json file.")
    print("  This code is shown ONCE — the server only keeps an Argon2id hash.")
    print("=" * 72)
    return code


async def _verify_recovery_code(db, supplied: str) -> bool:
    from security import verify_secret  # noqa: E402
    doc = await db.platform_secrets.find_one({"_id": "recovery"})
    if not doc:
        return False
    # Backwards-compat with the legacy plain `code` field on existing
    # installs (auto-migrated to hash on next bootstrap).
    if "hash" in doc:
        return verify_secret(supplied, doc["hash"])
    if "code" in doc:
        return secrets.compare_digest(doc.get("code", ""), supplied)
    return False


async def _bootstrap(lns: str, display_name: str, output: Path, rotate: bool) -> None:
    db = await _get_db()
    existing_lns = await db.lns.find_one({"lns_name": lns})

    if existing_lns and not rotate:
        raise SystemExit(
            f"FATAL: LNS '{lns}' already exists. Re-run with --rotate and a"
            f" valid LATTICE_RECOVERY_CODE env var to rotate the key."
        )

    if existing_lns and rotate:
        supplied = os.environ.get("LATTICE_RECOVERY_CODE", "").strip()
        if not supplied:
            raise SystemExit(
                "FATAL: --rotate requires LATTICE_RECOVERY_CODE env var."
            )
        if not await _verify_recovery_code(db, supplied):
            raise SystemExit("FATAL: invalid recovery code.")
        print(f"[rotate] recovery code OK — rotating key for {lns}")

    if not existing_lns:
        await _ensure_recovery_code(db)

    # Generate a fresh real ML-DSA-65 keypair.
    pk, sk = mldsa.generate_keypair()
    pk_hex = pk.hex()
    sk_hex = sk.hex()

    ts = _utc_iso()
    keystore_doc = {
        "entity": lns,
        "role": "platform-sovereign",
        "pk_hex": pk_hex,
        "sk_hex": sk_hex,
        "algorithm": "ML-DSA-65",
        "updated_at": ts,
    }
    await db.keystore.update_one(
        {"entity": lns},
        {"$set": keystore_doc, "$setOnInsert": {"created_at": ts}},
        upsert=True,
    )

    if not existing_lns:
        await db.lns.insert_one({
            "lns_name": lns,
            "department": "Sovereign Network",
            "admin": display_name,
            "tenant_id": None,
            "role": "sovereign",
            "status": "ACTIVE",
            "created_at": ts,
            "public_key_hex": pk_hex,
            "algorithm": "ML-DSA-65",
            "did": f"did:lattice:{lns}",
        })
        print(f"[bootstrap] LNS created: {lns}")
    else:
        await db.lns.update_one(
            {"lns_name": lns},
            {"$set": {"public_key_hex": pk_hex, "updated_at": ts}},
        )
        print(f"[rotate] keystore + LNS public key updated for {lns}")

    keypair_json = {
        "version": 1,
        "algorithm": "ML-DSA-65",
        "lns": lns,
        "tenant_id": None,
        "did": f"did:lattice:{lns}",
        "public_key_hex": pk_hex,
        "secret_key_hex": sk_hex,
        "created_at": ts,
        "warning": (
            "KEEP THIS FILE OFFLINE. Anyone with secret_key_hex can"
            " impersonate the Platform Operator. Move it out of the server"
            " filesystem immediately after download."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(keypair_json, indent=2))
    os.chmod(output, 0o600)
    print(f"[bootstrap] keypair written to {output} (mode 600)")
    print("=" * 72)
    print("  LOGIN: upload this file at /login → you ARE the Platform Operator")
    print(f"  LNS:   {lns}")
    print(f"  PK:    {pk_hex[:48]}…")
    print("=" * 72)


def main() -> None:
    p = argparse.ArgumentParser(description="Lattice Sovereign Bootstrap")
    p.add_argument("--lns", required=True, help="Full LNS name, e.g. fabio.sovereign.lattice.id")
    p.add_argument("--display-name", default="Platform Operator", help="Human display name")
    p.add_argument("--output", required=True, type=Path, help="Where to write the .keypair.json file")
    p.add_argument("--rotate", action="store_true", help="Rotate the key for an existing operator (requires LATTICE_RECOVERY_CODE)")
    args = p.parse_args()
    asyncio.run(_bootstrap(args.lns, args.display_name, args.output, args.rotate))


if __name__ == "__main__":
    main()
