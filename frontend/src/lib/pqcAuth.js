/**
 * Real client-side ML-DSA-65 helpers for PQC challenge-response login.
 * Uses @noble/post-quantum (NIST FIPS 204 implementation).
 */
import { ml_dsa65 } from "@noble/post-quantum/ml-dsa.js";

const TOKEN_KEY = "lattice.session.jwt";
const SESSION_KEY = "lattice.session.payload";

export function hexToBytes(hex) {
  const clean = hex.startsWith("0x") ? hex.slice(2) : hex;
  const out = new Uint8Array(clean.length / 2);
  for (let i = 0; i < out.length; i++) {
    out[i] = parseInt(clean.substr(i * 2, 2), 16);
  }
  return out;
}

export function bytesToHex(bytes) {
  return Array.from(bytes).map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function pqcSignChallenge(secretKeyHex, nonceHex) {
  const sk = hexToBytes(secretKeyHex);
  const nonce = hexToBytes(nonceHex);
  const sig = ml_dsa65.sign(nonce, sk);
  return bytesToHex(sig);
}

/**
 * Sign an arbitrary canonical message (UTF-8 string) with the ML-DSA-65
 * secret key currently held in sessionStorage. Returns the hex signature
 * or null if no key is available.
 */
export function pqcSignMessage(canonicalString) {
  try {
    const skHex = sessionStorage.getItem("lattice.sk");
    if (!skHex) return null;
    const sk = hexToBytes(skHex);
    const msg = new TextEncoder().encode(canonicalString);
    const sig = ml_dsa65.sign(msg, sk);
    return bytesToHex(sig);
  } catch (e) {
    console.warn("pqcSignMessage failed", e);
    return null;
  }
}

export function saveSession(token, payload) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(SESSION_KEY, JSON.stringify(payload));
  } catch (e) { console.warn(e); }
}

export function loadSession() {
  try {
    const token = localStorage.getItem(TOKEN_KEY);
    const raw = localStorage.getItem(SESSION_KEY);
    if (!token || !raw) return null;
    return { token, ...JSON.parse(raw) };
  } catch { return null; }
}

export function clearSession() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(SESSION_KEY);
    sessionStorage.removeItem("lattice.sk");
  } catch (e) { console.warn(e); }
}

export function getAuthToken() {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}

export function downloadKeypair(lnsName, registerResponse) {
  const payload = {
    lattice_keypair_version: 1,
    lns_name: lnsName,
    algorithm: "ML-DSA-65 · NIST FIPS 204",
    public_key_hex: registerResponse.public_key_hex,
    secret_key_hex: registerResponse.secret_key_hex,
    did: registerResponse.did,
    public_key_fingerprint: registerResponse.public_key_fingerprint,
    tenant_id: registerResponse.tenant_id,
    role: registerResponse.role,
    issued_at: registerResponse.timestamp,
    block_index: registerResponse.block_index,
    tx_id: registerResponse.tx_id,
    warning: "Conserva questo file in luogo sicuro. È l'UNICA copia della tua chiave segreta. Senza questo file NON potrai accedere alla console.",
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${lnsName}.keypair.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
