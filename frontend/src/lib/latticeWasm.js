/**
 * Lattice WASM bridge — client-side ML-DSA-65 signing
 * ===================================================
 *
 * This module is a thin async wrapper around the Rust→WASM `lattice_wasm`
 * package. It exposes the same surface as `pqcAuth.js` but routes all
 * signing/verification through a real FIPS 204 ML-DSA-65 implementation
 * compiled from RustCrypto's `ml-dsa` crate.
 *
 *   import { initLatticeWasm, signWithWasm, generateKeypairWasm } from "./latticeWasm";
 *   await initLatticeWasm();
 *   const kp = await generateKeypairWasm();     // sk NEVER leaves the browser
 *   const sigHex = await signWithWasm(skHex, "canonical|payload");
 *
 * Wire-format is byte-for-byte compatible with the server-side Python
 * `pqcrypto.sign.ml_dsa_65` library (verified by the host-side interop
 * test at `backend/tests/test_wasm_interop.py`).
 */
import init, {
  generate_keypair as wasm_generate_keypair,
  sign as wasm_sign,
  sign_text as wasm_sign_text,
  verify as wasm_verify,
  algorithm as wasm_algorithm,
} from "../wasm/lattice/lattice_wasm.js";

import wasmUrl from "../wasm/lattice/lattice_wasm_bg.wasm";
import { shamirSplitJs, shamirRecoverJs, shamirFingerprintJs } from "./shamirJs";

let _ready = null;

export function initLatticeWasm() {
  if (!_ready) {
    _ready = init(wasmUrl).then(() => true);
  }
  return _ready;
}

export async function generateKeypairWasm() {
  await initLatticeWasm();
  const kp = wasm_generate_keypair();
  return {
    public_key_hex: kp.public_key_hex,
    secret_key_hex: kp.secret_key_hex,
    algorithm: wasm_algorithm(),
  };
}

export async function signWithWasm(secretKeyHex, message) {
  await initLatticeWasm();
  if (typeof message === "string") {
    return wasm_sign_text(secretKeyHex, message);
  }
  // Assume Uint8Array.
  return wasm_sign(secretKeyHex, message);
}

export async function verifyWithWasm(publicKeyHex, message, signatureHex) {
  await initLatticeWasm();
  const bytes = typeof message === "string" ? new TextEncoder().encode(message) : message;
  return wasm_verify(publicKeyHex, bytes, signatureHex);
}

export async function wasmAlgorithm() {
  await initLatticeWasm();
  return wasm_algorithm();
}

/**
 * Split a hex-encoded secret into N shares (default 3) recoverable
 * from any K (default 2). Returns an array of "x:hex" strings.
 *
 *   const shares = await shamirSplitWasm(skHex, 2, 3);
 *   //   shares[0] === "1:aa…", shares[1] === "2:bb…", shares[2] === "3:cc…"
 *
 * Note: the function name keeps the "Wasm" suffix for callsite stability,
 * but the underlying implementation is pure JS (`shamirJs.js`). The original
 * Rust→WASM Shamir routines were removed in Iter_52 after a GF(256) toolchain
 * bug; the pure-JS implementation is correctness-tested against backend/shamir.py.
 */
export async function shamirSplitWasm(secretHex, threshold = 2, total = 3) {
  return shamirSplitJs(secretHex, threshold, total);
}

/** Recombine any K shares back into the original hex secret. */
export async function shamirRecoverWasm(shares /* array of "x:hex" */) {
  return shamirRecoverJs(shares);
}

/** SHA3-256 fingerprint of a single share ("x:hex"). */
export async function shamirFingerprintWasm(share) {
  return shamirFingerprintJs(share);
}
