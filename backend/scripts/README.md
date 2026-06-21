# Lattice Sovereign Bootstrap

This folder contains operational scripts for a Lattice Network deployment.

## `bootstrap_sovereign.py`

One-shot CLI that materialises the **Platform Operator** account on a
fresh Lattice deployment. Without this account, you cannot manage the
network: no onboarding, no lead inbox, no validator monitoring.

### First-time bootstrap

```bash
cd /app/backend
python -m scripts.bootstrap_sovereign \
    --lns fabio.sovereign.lattice.id \
    --display-name "Fabio Astorino" \
    --output /secrets/fabio.keypair.json
```

What it does:

1. Generates a fresh real **ML-DSA-65** keypair (NIST FIPS 204).
2. Persists the secret key in the local keystore (Mongo) — never leaves
   the deployment.
3. Registers `fabio.sovereign.lattice.id` as an `ACTIVE` LNS with role
   `sovereign` and `tenant_id=null` (= Platform Operator).
4. Writes a portable `.keypair.json` file with the public + secret hex.
5. Prints a one-time **recovery code** (32-byte URL-safe random string).
   Write it down offline — paper, password manager, hardware token. It
   is the ONLY way to rotate the operator key if you lose the keypair.

### Login

Go to `/login` in the browser, drag the `.keypair.json` onto the upload
zone. The frontend signs a challenge nonce with ML-DSA-65 and obtains a
JWT bound to the LNS. You are now Platform Operator.

### Key rotation (lost or compromised keypair)

```bash
cd /app/backend
LATTICE_RECOVERY_CODE='<the_recovery_code_you_wrote_down>' \
python -m scripts.bootstrap_sovereign \
    --lns fabio.sovereign.lattice.id \
    --rotate \
    --output /secrets/fabio.NEW.keypair.json
```

The script:

- Verifies the recovery code against the on-server hashed copy.
- Generates a brand-new ML-DSA-65 keypair.
- Overwrites the keystore entry — the old keypair STOPS working
  immediately (any login attempt with the old secret returns 401).
- Writes the new `.keypair.json` to disk (mode 600).

### Security checklist (production)

- [ ] Move the `.keypair.json` OUT of the server filesystem after
      download. Anyone with the file = Platform Operator.
- [ ] Store the recovery code offline. If both the keypair AND the
      recovery code are lost, the operator account is permanently
      unrecoverable (by design — no email backdoor).
- [ ] Set `LATTICE_STRICT_AUTH=1` in `backend/.env` to disable the
      legacy `X-Lattice-Role` header fallback. Once strict, every
      mutating endpoint requires a real PQC-signed JWT.
- [ ] Backup `db.keystore` and `db.platform_secrets` regularly. These
      collections hold the operator secret key + recovery hash.

### What this script does NOT touch

- It does NOT change anything related to tenants. Tenants are created
  later by the Platform Operator from `/onboarding` in the UI.
- It does NOT seed any mock data. The chain stays at whatever state it
  was when you ran the script.
