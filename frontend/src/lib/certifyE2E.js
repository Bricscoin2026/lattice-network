/**
 * Certify End-to-End Encryption (X25519 + AES-256-GCM)
 * =====================================================
 *
 * The sender:
 *   1. Fetches the recipient's X25519 public key from /api/lns/{lns}/enc-key
 *   2. Generates a fresh ephemeral X25519 keypair in the browser
 *   3. Derives a shared secret via ECDH
 *   4. Encrypts the mail body with AES-256-GCM using the shared secret
 *   5. Sends only the ciphertext + the ephemeral pk to the server
 *
 * The recipient:
 *   1. Reads its X25519 secret key from sessionStorage (.keypair.json)
 *   2. Derives the same shared secret via ECDH with the ephemeral pk
 *   3. Decrypts the AES-GCM body locally — server NEVER sees plaintext
 *
 * X25519 keypair is generated client-side using @noble/curves (already
 * installed). The encryption pk is registered alongside the ML-DSA-65
 * signing pk at LNS registration time.
 */
import { x25519 } from "@noble/curves/ed25519.js";
import { sha256 } from "@noble/hashes/sha2.js";

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
function hexToBytes(h) {
  const len = h.length / 2;
  const out = new Uint8Array(len);
  for (let i = 0; i < len; i++) out[i] = parseInt(h.substr(i * 2, 2), 16);
  return out;
}
function bytesToHex(b) {
  let s = "";
  for (const x of b) s += x.toString(16).padStart(2, "0");
  return s;
}

/** Generate a fresh X25519 keypair (32-byte pk, 32-byte sk). */
export function generateEncKeypair() {
  // Noble/curves >=2.x exposes randomSecretKey; older builds used randomPrivateKey.
  const rnd = x25519.utils?.randomSecretKey || x25519.utils?.randomPrivateKey;
  if (typeof rnd !== "function") {
    throw new Error("x25519 utils.randomSecretKey/randomPrivateKey not available");
  }
  const sk = rnd();
  const pk = x25519.getPublicKey(sk);
  return {
    enc_public_key_hex: bytesToHex(pk),
    enc_secret_key_hex: bytesToHex(sk),
  };
}

async function aesKey(rawBytes, usages) {
  return crypto.subtle.importKey("raw", rawBytes, { name: "AES-GCM" }, false, usages);
}

/**
 * E2E-encrypt a mail body for a single recipient.
 * @param recipientEncPkHex 64-char X25519 public key (hex)
 * @param plaintext mail body (UTF-8 string)
 * @returns { body_ciphertext_b64, envelope: { eph_pk_hex, nonce_b64, algorithm } }
 */
export async function encryptMailBody(recipientEncPkHex, plaintext) {
  const recipPk = hexToBytes(recipientEncPkHex);
  const _rnd = x25519.utils?.randomSecretKey || x25519.utils?.randomPrivateKey;
  if (typeof _rnd !== "function") throw new Error("x25519 utils.randomSecretKey/randomPrivateKey not available");
  const ephSk = _rnd();
  const ephPk = x25519.getPublicKey(ephSk);
  const shared = x25519.getSharedSecret(ephSk, recipPk);
  // Derive the AES key with SHA-256 of the shared secret (HKDF-style minimal).
  const aesKeyBytes = sha256(shared);
  const key = await aesKey(aesKeyBytes, ["encrypt"]);
  const nonce = crypto.getRandomValues(new Uint8Array(12));
  const ct = new Uint8Array(
    await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce }, key, new TextEncoder().encode(plaintext)),
  );
  return {
    body_ciphertext_b64: b64encode(ct),
    envelope: {
      version: 1,
      algorithm: "X25519+AES-256-GCM",
      eph_pk_hex: bytesToHex(ephPk),
      nonce_b64: b64encode(nonce),
    },
  };
}

/**
 * E2E-decrypt a mail body using the recipient's X25519 sk.
 * @param recipientEncSkHex 64-char X25519 secret key (hex)
 * @param ciphertextB64 the body field returned by the API (when is_e2e_encrypted=true)
 * @param envelope the body_e2e_envelope dict from the mail doc
 * @returns plaintext string
 */
export async function decryptMailBody(recipientEncSkHex, ciphertextB64, env) {
  const recipSk = hexToBytes(recipientEncSkHex);
  const ephPk = hexToBytes(env.eph_pk_hex);
  const shared = x25519.getSharedSecret(recipSk, ephPk);
  const aesKeyBytes = sha256(shared);
  const key = await aesKey(aesKeyBytes, ["decrypt"]);
  const nonce = b64decode(env.nonce_b64);
  const ct = b64decode(ciphertextB64);
  const pt = new Uint8Array(
    await crypto.subtle.decrypt({ name: "AES-GCM", iv: nonce }, key, ct),
  );
  return new TextDecoder().decode(pt);
}
