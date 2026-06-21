/**
 * Pure-JS Shamir Secret Sharing over GF(256) — port of `backend/shamir.py`.
 * Used as a fallback because the Rust→WASM build (Iter_30) silently
 * produces incorrect log/exp tables on some toolchains (the
 * `const fn build_tables` evaluation does not populate the arrays
 * correctly, leading to wrong gf_mul and a broken round-trip). This JS
 * impl is correctness-tested against the Python `shamir.py`.
 */

// --- GF(256) log/exp tables (AES poly 0x1B, generator α=3) ----------------
// Standard AES-style tables: generator is 0x03 (alpha + 1), NOT 0x02.
// We seed exp/log using xtime(x) * x = xtime(x) XOR x (multiplication by 3).
const LOG = new Uint8Array(256);
const EXP = new Uint8Array(256);
{
  // Multiplication by 3 in GF(256) modulo 0x11B: x*3 = xtime(x) XOR x.
  const mulBy3 = (a) => {
    const x2 = (a << 1) & 0xff;
    const xtime = (a & 0x80) ? (x2 ^ 0x1b) : x2;
    return xtime ^ a;
  };
  let x = 1;
  for (let i = 0; i < 255; i++) {
    EXP[i] = x;
    LOG[x] = i;
    x = mulBy3(x);
  }
  EXP[255] = EXP[0];
}

function gfMul(a, b) {
  if (a === 0 || b === 0) return 0;
  return EXP[(LOG[a] + LOG[b]) % 255];
}

function gfDiv(a, b) {
  if (a === 0) return 0;
  if (b === 0) throw new Error("GF(256) division by zero");
  return EXP[(((LOG[a] - LOG[b]) % 255) + 255) % 255];
}

function hexToBytes(h) {
  const t = (h || "").trim();
  if (t.length % 2 !== 0) throw new Error("odd hex length");
  const out = new Uint8Array(t.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(t.substr(i * 2, 2), 16);
  return out;
}

function bytesToHex(b) {
  let s = "";
  for (const v of b) s += v.toString(16).padStart(2, "0");
  return s;
}

/**
 * Split a hex-encoded secret into `total` shares; any `threshold` recover it.
 * Returns an array of strings in the format `"x:hex"`, matching the WASM
 * interface (and `backend/shamir.py` wire format).
 */
export function shamirSplitJs(secretHex, threshold = 2, total = 3) {
  if (!(1 < threshold && threshold <= total && total <= 255)) {
    throw new Error("invalid threshold/total");
  }
  const secret = hexToBytes(secretHex);
  if (secret.length === 0) throw new Error("empty secret");
  const xs = [];
  for (let x = 1; x <= total; x++) xs.push(x);
  const shares = xs.map(() => new Uint8Array(secret.length));
  const coeffBuf = new Uint8Array(threshold - 1);
  for (let bi = 0; bi < secret.length; bi++) {
    const byte = secret[bi];
    crypto.getRandomValues(coeffBuf); // fresh random coefficients per byte
    for (let i = 0; i < xs.length; i++) {
      let y = 0;
      // Horner: y = (((0*x ^ c[k-1])*x ^ c[k-2])*x ^ ... )*x ^ a0
      for (let k = coeffBuf.length - 1; k >= 0; k--) {
        y = gfMul(y, xs[i]) ^ coeffBuf[k];
      }
      y = gfMul(y, xs[i]) ^ byte;
      shares[i][bi] = y;
    }
  }
  return xs.map((x, i) => `${x}:${bytesToHex(shares[i])}`);
}

/**
 * Recombine the secret from any K shares (`["x:hex", "x:hex"]` strings).
 * Returns the original hex-encoded secret.
 */
export function shamirRecoverJs(sharesStr) {
  if (!Array.isArray(sharesStr) || sharesStr.length < 2) {
    throw new Error("need at least 2 shares");
  }
  const xs = [];
  const ys = [];
  for (const s of sharesStr) {
    const colon = s.indexOf(":");
    if (colon < 0) throw new Error("malformed share, missing ':'");
    const x = parseInt(s.slice(0, colon).trim(), 10);
    if (!Number.isFinite(x) || x < 1 || x > 255) throw new Error("invalid x coord");
    xs.push(x);
    ys.push(hexToBytes(s.slice(colon + 1)));
  }
  const n = ys[0].length;
  for (const y of ys) if (y.length !== n) throw new Error("shares have different sizes");
  const out = new Uint8Array(n);
  for (let i = 0; i < n; i++) {
    // Lagrange interpolation at x=0 in GF(256).
    let result = 0;
    for (let j = 0; j < xs.length; j++) {
      let num = 1, den = 1;
      for (let k = 0; k < xs.length; k++) {
        if (k === j) continue;
        num = gfMul(num, xs[k]);
        den = gfMul(den, xs[j] ^ xs[k]);
      }
      const term = gfMul(ys[j][i], gfDiv(num, den));
      result ^= term;
    }
    out[i] = result;
  }
  return bytesToHex(out);
}

/** SHA3-256 fingerprint of a single share ("x:hex"), matching backend. */
export async function shamirFingerprintJs(shareStr) {
  const colon = shareStr.indexOf(":");
  if (colon < 0) throw new Error("malformed share");
  const x = parseInt(shareStr.slice(0, colon).trim(), 10);
  const y = hexToBytes(shareStr.slice(colon + 1));
  const buf = new Uint8Array(1 + y.length);
  buf[0] = x;
  buf.set(y, 1);
  // Use @noble/hashes sha3 (already a dep via x25519 module).
  const { sha3_256 } = await import("@noble/hashes/sha3.js");
  return bytesToHex(sha3_256(buf));
}
