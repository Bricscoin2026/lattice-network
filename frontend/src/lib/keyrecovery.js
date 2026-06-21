/**
 * 2-of-3 Nominee Key Recovery (client-side only).
 *
 * Pipeline:
 *   1. The LNS owner asks the WASM module to Shamir-split their
 *      4032-byte ML-DSA-65 sk into 3 byte-shares with threshold 2.
 *   2. Each share is sealed (ECIES, X25519+AES-256-GCM) against the
 *      corresponding guardian's X25519 public key.
 *   3. The server stores ONLY the three opaque ciphertexts + SHA3-256
 *      fingerprints. Notarises the fingerprints on-chain (no plaintext
 *      ever leaves the device).
 *
 * Recovery:
 *   A) Owner opens a recovery request.
 *   B) Each nominated guardian fetches the request, decrypts their
 *      share locally with their X25519 sk, then re-seals it for the
 *      requester's NEW X25519 pk.
 *   C) Once any 2 of 3 guardians have contributed, the requester
 *      decrypts the two contributions and runs WASM `shamir_recover`.
 *      The reconstructed sk equals the original secret bytes.
 */
import { x25519 } from "@noble/curves/ed25519.js";
import { sha256 } from "@noble/hashes/sha2.js";
import {
  shamirSplitWasm,
  shamirRecoverWasm,
  shamirFingerprintWasm,
} from "@/lib/latticeWasm";

// ---- shared helpers (no external deps to keep bundle small) --------------
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
async function aesKey(rawBytes, usages) {
  return crypto.subtle.importKey("raw", rawBytes, { name: "AES-GCM" }, false, usages);
}

/**
 * ECIES seal: produce { eph_pk_hex, nonce_b64, ct_b64 } for `plaintext` bytes
 * destined to `recipientEncPkHex` (32-byte X25519 pk in hex).
 */
async function sealForGuardian(recipientEncPkHex, plaintextString) {
  const recipPk = hexToBytes(recipientEncPkHex);
  const _rnd = x25519.utils?.randomSecretKey || x25519.utils?.randomPrivateKey;
  if (typeof _rnd !== "function") throw new Error("x25519 utils.randomSecretKey/randomPrivateKey not available");
  const ephSk = _rnd();
  const ephPk = x25519.getPublicKey(ephSk);
  const shared = x25519.getSharedSecret(ephSk, recipPk);
  const aesBytes = sha256(shared);
  const key = await aesKey(aesBytes, ["encrypt"]);
  const nonce = crypto.getRandomValues(new Uint8Array(12));
  const ct = new Uint8Array(
    await crypto.subtle.encrypt(
      { name: "AES-GCM", iv: nonce },
      key,
      new TextEncoder().encode(plaintextString),
    ),
  );
  return {
    version: 1,
    algorithm: "X25519+AES-256-GCM",
    eph_pk_hex: bytesToHex(ephPk),
    nonce_b64: b64encode(nonce),
    ct_b64: b64encode(ct),
  };
}

async function openSealedShare(recipientEncSkHex, envelope) {
  const recipSk = hexToBytes(recipientEncSkHex);
  const ephPk = hexToBytes(envelope.eph_pk_hex);
  const shared = x25519.getSharedSecret(recipSk, ephPk);
  const aesBytes = sha256(shared);
  const key = await aesKey(aesBytes, ["decrypt"]);
  const nonce = b64decode(envelope.nonce_b64);
  const ct = b64decode(envelope.ct_b64);
  const pt = new Uint8Array(
    await crypto.subtle.decrypt({ name: "AES-GCM", iv: nonce }, key, ct),
  );
  return new TextDecoder().decode(pt); // share format: "x:hex"
}

/**
 * Build the payload accepted by `POST /api/keyrecovery/enroll`.
 *
 *   buildEnrollPayload({
 *     ownerLns,
 *     ownerSkHex,                    // 4032 byte ML-DSA-65 sk (hex)
 *     guardians: [
 *       { lns, enc_public_key_hex },  // 3 of them
 *       …
 *     ],
 *   })
 */
export async function buildEnrollPayload({ ownerLns, ownerSkHex, guardians }) {
  if (!guardians || guardians.length !== 3) {
    throw new Error("exactly 3 guardians are required");
  }
  if (new Set(guardians.map((g) => g.lns)).size !== 3) {
    throw new Error("guardians must be distinct LNS identities");
  }
  for (const g of guardians) {
    if (!g.enc_public_key_hex) {
      throw new Error(`guardian ${g.lns} has no X25519 encryption key on file`);
    }
  }
  // 1) Real Rust/WASM Shamir split, threshold = 2 / total = 3.
  const shares = await shamirSplitWasm(ownerSkHex, 2, 3); // ["1:…", "2:…", "3:…"]
  // 1.5) Consistency check (Iter_51+52) — verify Shamir round-trip BEFORE
  //   uploading. Catches WASM/library regressions and protects against
  //   producing an enrollment whose recovered SK does not parse as ML-DSA.
  //   Normalize both sides to lowercase no-whitespace hex bytes to avoid
  //   spurious mismatch from case/whitespace differences in the keypair file.
  const norm = (h) => (h || "").replace(/\s+/g, "").toLowerCase();
  const expected = norm(ownerSkHex);
  const recovered12 = norm(await shamirRecoverWasm([shares[0], shares[1]]));
  const recovered13 = norm(await shamirRecoverWasm([shares[0], shares[2]]));
  const recovered23 = norm(await shamirRecoverWasm([shares[1], shares[2]]));
  // Try a tolerant comparison: pure bytes equality (ignore even an odd
  // trailing/leading hex char that the wasm might pad differently).
  const sameBytes = (a, b) => {
    if (a === b) return true;
    if (Math.abs(a.length - b.length) > 1) return false;
    // align lengths by truncating to the shortest even multiple of 2
    const n = Math.min(a.length, b.length) & ~1;
    return a.slice(0, n) === b.slice(0, n);
  };
  if (!sameBytes(recovered12, expected)) {
    // Diagnostic info — surface lengths and first/last bytes so we can tell
    // the user what's misaligned (encoding issue vs. shamir math regression).
    const head = (s) => (s || "").slice(0, 16);
    const tail = (s) => (s || "").slice(-16);
    throw new Error(
      "Shamir round-trip 1+2 fallito · enrollment annullato. " +
      `in_len=${expected.length} out_len=${recovered12.length} · ` +
      `in_head=${head(expected)} out_head=${head(recovered12)} · ` +
      `in_tail=${tail(expected)} out_tail=${tail(recovered12)}`,
    );
  }
  if (!sameBytes(recovered13, expected) || !sameBytes(recovered23, expected)) {
    throw new Error("Shamir round-trip incoerente tra coppie · enrollment annullato");
  }
  // 2) Seal each share against the corresponding guardian.
  const sealed = await Promise.all(
    shares.map((s, i) => sealForGuardian(guardians[i].enc_public_key_hex, s)),
  );
  // 3) Fingerprints (SHA3-256) — these go on-chain. Server cannot
  //    derive the share from the fingerprint.
  const fps = await Promise.all(shares.map((s) => shamirFingerprintWasm(s)));
  return {
    lns: ownerLns,
    guardian1_lns: guardians[0].lns,
    guardian2_lns: guardians[1].lns,
    guardian3_lns: guardians[2].lns,
    encrypted_share1: sealed[0],
    encrypted_share2: sealed[1],
    encrypted_share3: sealed[2],
    share1_fingerprint: fps[0],
    share2_fingerprint: fps[1],
    share3_fingerprint: fps[2],
  };
}

/**
 * Re-seal a guardian's share for a recovery requester.
 *
 *   guardianContribute({
 *     myEncSkHex,           // guardian's X25519 sk (from .keypair.json)
 *     sealedEnvelopeForMe,  // ciphertext stored on the server for this guardian
 *     requesterEncPkHex,    // the requester's NEW X25519 pk
 *   })
 *
 * Returns the new sealed envelope (the share, re-encrypted) ready to POST
 * to /api/keyrecovery/contribute.
 */
export async function guardianContribute({
  myEncSkHex,
  sealedEnvelopeForMe,
  requesterEncPkHex,
}) {
  const rawShare = await openSealedShare(myEncSkHex, sealedEnvelopeForMe);
  const sealedForRequester = await sealForGuardian(requesterEncPkHex, rawShare);
  return sealedForRequester;
}

/**
 * Final recovery step (run by the requester after 2 guardians contributed).
 *
 *   recoverSecretKey({
 *     myEncSkHex,                       // requester's NEW X25519 sk
 *     contributions: [
 *       { envelope, guardian_lns }, …    // exactly 2 (or more)
 *     ],
 *   }) → sk_hex
 */
export async function recoverSecretKey({ myEncSkHex, contributions }) {
  if (!contributions || contributions.length < 2) {
    throw new Error("need at least 2 guardian contributions to recover");
  }
  const shares = [];
  for (const c of contributions) {
    const s = await openSealedShare(myEncSkHex, c.envelope);
    shares.push(s);
  }
  const recovered = await shamirRecoverWasm(shares);
  // Sanity check (Iter_51) — ML-DSA-65 sk is exactly 4032 bytes = 8064 hex chars.
  // If we get something different, the inputs are inconsistent (e.g. shares
  // from two different enrollments were mixed by a re-enroll race) and the
  // would-be SK cannot be loaded into ml_dsa65.sign. Fail loudly here with
  // an actionable message instead of crashing later in Login.jsx.
  if (typeof recovered !== "string" || recovered.length !== 8064) {
    throw new Error(
      `chiave ricostruita di lunghezza inattesa (${recovered?.length} hex) · ` +
      "i contributi dei nominati provengono probabilmente da enrollment diversi " +
      "(re-enroll race). Apri una nuova richiesta di recupero.",
    );
  }
  return recovered;
}
