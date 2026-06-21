#!/usr/bin/env python3
"""
Lattice Network — vendor license issuance tool
================================================

Usage:
    # First time: generate the vendor master keypair (KEEP THE PRIVATE KEY OFFLINE)
    python -m scripts.issue_license keygen --out /app/backend/data/vendor_keypair.json

    # Issue a license
    python -m scripts.issue_license sign \\
        --priv /app/backend/data/vendor_keypair.json \\
        --edition banking \\
        --tenant "Banca Test SpA" \\
        --valid-until 2027-12-31T23:59:59Z \\
        --max-tenants 1 --max-users 200 \\
        --feature pulse --feature certify --feature mixnet --feature banking_audit \\
        --out /app/backend/data/license.lic

The private key MUST be moved to an air-gapped machine in production.
Public key (`vendor_pubkey.hex`) ships in the Docker image.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running as `python scripts/issue_license.py` from any cwd
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pqcrypto.sign import ml_dsa_65 as mldsa  # noqa: E402

import license as licmod  # noqa: E402  — alias to avoid shadowing


def cmd_keygen(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pk, sk = mldsa.generate_keypair()
    doc = {
        "algorithm": "ML-DSA-65",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "public_key_hex": pk.hex(),
        "secret_key_hex": sk.hex(),
        "fingerprint": licmod._pk_fingerprint(pk),
    }
    out.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    # Also drop the public key alongside for the server to load.
    pub_path = out.parent / "vendor_pubkey.hex"
    pub_path.write_text(pk.hex(), encoding="utf-8")
    print(f"Vendor keypair written to {out}")
    print(f"Vendor pubkey       to {pub_path}  (fingerprint={doc['fingerprint']})")
    print("KEEP THE SECRET KEY OFFLINE — anyone with it can mint licenses.")
    return 0


def cmd_sign(args: argparse.Namespace) -> int:
    priv = json.loads(Path(args.priv).read_text(encoding="utf-8"))
    license_doc = licmod.issue(
        priv["secret_key_hex"],
        edition=args.edition,
        tenant_name=args.tenant,
        valid_until_iso=args.valid_until,
        max_tenants=args.max_tenants,
        max_users=args.max_users,
        features=list(args.feature or []),
        license_id=args.license_id,
    )
    # Sanity verify before writing
    ok, reason = licmod.verify(license_doc, priv["public_key_hex"])
    if not ok:
        print(f"INTERNAL ERROR: license fails self-verify: {reason}", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(license_doc, indent=2, sort_keys=True), encoding="utf-8")
    print(f"License written to {out}")
    print(f"  id        = {license_doc['license_id']}")
    print(f"  edition   = {license_doc['edition']}")
    print(f"  tenant    = {license_doc['tenant_name']}")
    print(f"  valid     = {license_doc['valid_from']} → {license_doc['valid_until']}")
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="issue_license")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("keygen", help="generate vendor master keypair")
    g.add_argument("--out", required=True)
    g.set_defaults(func=cmd_keygen)

    s = sub.add_parser("sign", help="issue a signed license file")
    s.add_argument("--priv", required=True, help="vendor keypair JSON file")
    s.add_argument("--edition", required=True, choices=sorted(licmod.EDITIONS))
    s.add_argument("--tenant", required=True)
    s.add_argument("--valid-until", required=True, help="ISO-8601 expiry timestamp")
    s.add_argument("--max-tenants", type=int, default=None)
    s.add_argument("--max-users", type=int, default=None)
    s.add_argument("--feature", action="append", help="repeat for each feature flag")
    s.add_argument("--license-id", default=None)
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_sign)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
