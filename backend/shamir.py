"""
Shamir Secret Sharing 2-of-3 over GF(256)
==========================================

Pure-Python, byte-wise implementation suitable for splitting a 4032-byte
ML-DSA-65 secret key into 3 shares (1 per guardian), recoverable with
ANY 2 of them.

Why GF(256)? Information-theoretically secure for byte-sized secrets,
no large-integer arithmetic, deterministic share size = secret size + 1.

  * `split(secret_bytes, total=3, threshold=2)` → list of 3 share dicts
  * `recover(shares)` → original secret bytes  (any 2 of the 3 shares)

Each share is `{ "x": int (1..255), "y": bytes }` where `y` is the same
length as the original secret.
"""
from __future__ import annotations
import secrets
from typing import List, Dict

# Standard AES MDS polynomial for GF(256).
_LOG = [0] * 256
_EXP = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x ^= (_x << 1) & 0xFF
    if _x & 0x100 or (_EXP[_i] & 0x80):
        _x ^= 0x1B
_EXP[255] = _EXP[0]


def _mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _EXP[(_LOG[a] + _LOG[b]) % 255]


def _div(a: int, b: int) -> int:
    if a == 0:
        return 0
    if b == 0:
        raise ZeroDivisionError("GF(256) division by zero")
    return _EXP[(_LOG[a] - _LOG[b]) % 255]


def split(secret: bytes, total: int = 3, threshold: int = 2) -> List[Dict]:
    """Split `secret` into `total` shares; any `threshold` recover it."""
    if not (1 < threshold <= total <= 255):
        raise ValueError("invalid threshold/total")
    if not secret:
        raise ValueError("empty secret")

    shares = [bytearray() for _ in range(total)]
    xs = list(range(1, total + 1))  # x coordinates 1..total

    for byte in secret:
        # Random degree-(threshold-1) polynomial with f(0) = byte.
        coeffs = [byte] + [secrets.randbelow(256) for _ in range(threshold - 1)]
        for i, x in enumerate(xs):
            y = 0
            for c in reversed(coeffs):
                y = _mul(y, x) ^ c
            shares[i].append(y)

    return [{"x": x, "y_hex": bytes(s).hex()} for x, s in zip(xs, shares)]


def recover(shares: List[Dict]) -> bytes:
    """Recover the original secret from any `threshold` shares."""
    if len(shares) < 2:
        raise ValueError("need at least 2 shares")
    xs = [s["x"] for s in shares]
    ys = [bytes.fromhex(s["y_hex"]) for s in shares]
    if len({len(y) for y in ys}) != 1:
        raise ValueError("shares have different sizes")
    out = bytearray()
    for i in range(len(ys[0])):
        # Lagrange interpolation at x=0 in GF(256).
        result = 0
        for j, xj in enumerate(xs):
            num = 1
            den = 1
            for k, xk in enumerate(xs):
                if k == j:
                    continue
                num = _mul(num, xk)
                den = _mul(den, xj ^ xk)
            term = _mul(ys[j][i], _div(num, den))
            result ^= term
        out.append(result)
    return bytes(out)


def fingerprint(share: Dict) -> str:
    """SHA3-256 hex of `x || y` — for on-chain notarisation."""
    import hashlib
    return hashlib.sha3_256(bytes([share["x"]]) + bytes.fromhex(share["y_hex"])).hexdigest()
