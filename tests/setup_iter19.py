"""Provision tenant + 2 employees, login both, print JSON with session data."""
import os, sys, json, secrets, requests
from pqcrypto.sign.ml_dsa_65 import sign as mldsa_sign

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
SOV = {"X-Lattice-Role": "sovereign"}

def u(p): return f"{BASE}{p}"

def reg_tenant(slug):
    r = requests.post(u("/api/tenants/register"), headers=SOV, json={
        "name": f"TEST_{slug.upper()} SpA",
        "domain_prefix": slug,
        "admin_lns_prefix": "admin",
        "admin_display_name": f"Admin {slug}",
    }, timeout=30)
    r.raise_for_status()
    return r.json()

def reg_employee(tenant_id, lns_full, display):
    r = requests.post(u("/api/lns/register"), headers=SOV, json={
        "lns_name": lns_full, "department": "Test", "admin": display,
        "tenant_id": tenant_id, "role": "operator",
    }, timeout=30)
    r.raise_for_status()
    return r.json()

def login(lns, sk_hex):
    rc = requests.post(u("/api/auth/challenge"), json={"lns_name": lns}, timeout=15)
    rc.raise_for_status()
    cd = rc.json()
    sig = mldsa_sign(bytes.fromhex(sk_hex), bytes.fromhex(cd["nonce_hex"]))
    rv = requests.post(u("/api/auth/verify"), json={
        "challenge_id": cd["challenge_id"], "lns_name": lns,
        "nonce_hex": cd["nonce_hex"], "signature_hex": sig.hex(),
    }, timeout=15)
    rv.raise_for_status()
    return rv.json()  # contains token + identity payload

slug = "iter19" + secrets.token_hex(3)
t = reg_tenant(slug)
domain = t["domain"]
tenant_id = t["tenant_id"]

# Create 2 employees (we already have admin from tenant register; use it as user A; create user B)
userA_lns = t["admin_lns"]
userA_sk = t["admin_keypair_json"]["secret_key_hex"]

userB_lns = f"userb.{domain}"
userB_resp = reg_employee(tenant_id, userB_lns, "User B")
userB_sk = userB_resp["secret_key_hex"]

loginA = login(userA_lns, userA_sk)
loginB = login(userB_lns, userB_sk)

print(json.dumps({
    "base_url": BASE,
    "tenant_id": tenant_id,
    "domain": domain,
    "userA": {"lns": userA_lns, "sk": userA_sk, "token": loginA["token"], "session": loginA},
    "userB": {"lns": userB_lns, "sk": userB_sk, "token": loginB["token"], "session": loginB},
}))
