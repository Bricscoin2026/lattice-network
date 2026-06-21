/**
 * keypair-vault.js
 * =================
 *
 * Encrypts/decrypts a `.keypair.json` payload with a user-supplied
 * passphrase. Algorithm: AES-256-GCM, key derived via PBKDF2-SHA256
 * (600 000 iterations, NIST SP 800-132 minimum). Output is a JSON wrapper:
 *
 *   {
 *     "version": 1,
 *     "kdf": "PBKDF2-SHA256",
 *     "iterations": 600000,
 *     "salt_b64": "...",
 *     "nonce_b64": "...",
 *     "ciphertext_b64": "..."
 *   }
 *
 * Pure WebCrypto, runs entirely in the browser. The passphrase never
 * leaves the page. Useful for offsite backup of the operator/employee
 * keypair file: even if the encrypted file is stolen, decrypting it
 * requires the passphrase.
 */
const ITER = 600_000;

function b64encode(bytes) {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s);
}
function b64decode(b64) {
  const s = atob(b64);
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
  return out;
}

async function deriveKey(passphrase, salt) {
  const enc = new TextEncoder();
  const base = await crypto.subtle.importKey(
    "raw", enc.encode(passphrase), { name: "PBKDF2" }, false, ["deriveKey"],
  );
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", salt, iterations: ITER, hash: "SHA-256" },
    base,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

export async function encryptKeypairJson(plainObj, passphrase) {
  if (!passphrase || passphrase.length < 12) {
    throw new Error("passphrase must be at least 12 characters");
  }
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const nonce = crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveKey(passphrase, salt);
  const plaintext = new TextEncoder().encode(JSON.stringify(plainObj));
  const ct = new Uint8Array(
    await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce }, key, plaintext),
  );
  return {
    version: 1,
    kdf: "PBKDF2-SHA256",
    iterations: ITER,
    cipher: "AES-256-GCM",
    salt_b64: b64encode(salt),
    nonce_b64: b64encode(nonce),
    ciphertext_b64: b64encode(ct),
    note: "Decrypt with the original passphrase. PBKDF2-SHA256 / 600 000 iter / AES-256-GCM.",
  };
}

export async function decryptKeypairJson(envelope, passphrase) {
  const salt = b64decode(envelope.salt_b64);
  const nonce = b64decode(envelope.nonce_b64);
  const ct = b64decode(envelope.ciphertext_b64);
  const key = await deriveKey(passphrase, salt);
  const pt = new Uint8Array(
    await crypto.subtle.decrypt({ name: "AES-GCM", iv: nonce }, key, ct),
  );
  return JSON.parse(new TextDecoder().decode(pt));
}

export function isEncryptedKeypair(obj) {
  return (
    obj && obj.version === 1 && obj.cipher === "AES-256-GCM" && typeof obj.ciphertext_b64 === "string"
  );
}
