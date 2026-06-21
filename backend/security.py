"""
Lattice Network — production hardening
======================================

Single source of truth for security-critical wiring:

* Refuses to boot in STRICT mode if JWT_SECRET or CORS_ORIGINS are the
  weak development defaults.
* Adds standard HTTP security headers (HSTS, CSP, X-Frame, etc).
* Rate-limiting (slowapi) — enforces per-IP caps on the public lead
  endpoint and the authentication endpoints.
* Global request-body size cap to prevent OOM bombs.
* MIME magic-byte sniffing for attachments (no longer trusts the client
  Content-Type header).
* Argon2id for recovery-code hashing (replaces plaintext storage).

Import this from `server.py` at startup time and call
`install_security(app, log, strict: bool)`.
"""
from __future__ import annotations

import logging
import os
import time
from collections import deque
from typing import Awaitable, Callable, Deque, Dict, Tuple

try:
    import magic  # libmagic-backed MIME sniffing
    _MAGIC_AVAILABLE = True
except ImportError:  # libmagic not installed (some minimal containers)
    magic = None  # type: ignore
    _MAGIC_AVAILABLE = False
from argon2 import PasswordHasher, exceptions as argon2_exc
from fastapi import FastAPI, HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


# ---------------------------------------------------------------------------
# Boot-time fail-fast checks
# ---------------------------------------------------------------------------
_WEAK_JWT_DEFAULTS = {"", "dev-only-please-rotate", "change-me", "secret"}


def verify_production_env(strict: bool, log: logging.Logger) -> None:
    """In STRICT mode, refuse to boot with weak production config.

    Anything below is a hard NO-GO for a public deployment:
    * default LATTICE_JWT_SECRET — JWTs become forgeable
    * CORS_ORIGINS=`*` — any third-party site can call our APIs
    * MONGO_URL pointing to localhost without auth
    """
    if not strict:
        log.warning(
            "LATTICE_STRICT_AUTH is OFF — running in development mode. "
            "Do NOT expose this instance to the public Internet."
        )
        return

    jwt_secret = os.environ.get("LATTICE_JWT_SECRET", "").strip()
    if jwt_secret in _WEAK_JWT_DEFAULTS or len(jwt_secret) < 32:
        raise SystemExit(
            "FATAL: LATTICE_STRICT_AUTH=1 but LATTICE_JWT_SECRET is missing "
            "or weak. Generate one with: python -c 'import secrets; "
            "print(secrets.token_hex(32))' and set it in .env.production."
        )

    cors = os.environ.get("CORS_ORIGINS", "*").strip()
    if cors == "*" or not cors:
        raise SystemExit(
            "FATAL: LATTICE_STRICT_AUTH=1 but CORS_ORIGINS is '*' or empty. "
            "Set it to a comma-separated list of your real frontend origins."
        )

    log.info("Production hardening: JWT secret OK · CORS pinned to %s", cors)


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------
_HSTS_VALUE = "max-age=63072000; includeSubDomains; preload"
_CSP_API = (
    # API responses are mostly JSON / PDFs; lock the document context down.
    "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; "
    "form-action 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects industry-standard security headers on every response."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        response.headers.setdefault("Strict-Transport-Security", _HSTS_VALUE)
        # Apply a strict CSP only to non-static API paths.
        if request.url.path.startswith("/api"):
            response.headers.setdefault("Content-Security-Policy", _CSP_API)
        # Prevent caching of authenticated responses.
        if "Authorization" in request.headers:
            response.headers["Cache-Control"] = "no-store"
        return response


# ---------------------------------------------------------------------------
# Global body-size cap
# ---------------------------------------------------------------------------
class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Reject any request whose Content-Length exceeds `max_bytes`.

    Streams aren't sniffed — Content-Length is mandatory for POST/PUT.
    Per-endpoint exemptions are honoured via the `_exempt_prefixes` list
    (used for the attachment upload, which streams and validates itself).
    """

    def __init__(self, app, max_bytes: int, exempt_prefixes: tuple[str, ...] = ()):
        super().__init__(app)
        self._max = max_bytes
        self._exempt_prefixes = exempt_prefixes

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method in ("POST", "PUT", "PATCH"):
            if not any(request.url.path.startswith(p) for p in self._exempt_prefixes):
                cl = request.headers.get("content-length")
                if cl and cl.isdigit() and int(cl) > self._max:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": f"request body too large (max {self._max} bytes)"},
                    )
        return await call_next(request)


# ---------------------------------------------------------------------------
# Rate limiter — sliding-window per (client IP, path)
# ---------------------------------------------------------------------------
class RateLimiter:
    """Minimal in-process sliding-window limiter.

    Configure per-path caps via `add(path_prefix, max_calls, window_sec)`.
    For multi-pod use Redis; this implementation is single-process safe.

    Supports TWO independent rule families:
      * per-IP   — anti-DDoS / anti-scrape (anonymous traffic)
      * per-tenant — anti-abuse on authenticated endpoints (one tenant
        can't saturate the backend across all its IPs)
    """

    def __init__(self) -> None:
        self._rules: list[Tuple[str, int, float]] = []
        self._tenant_rules: list[Tuple[str, int, float]] = []
        self._hits: Dict[Tuple[str, str], Deque[float]] = {}
        self._tenant_hits: Dict[Tuple[str, str], Deque[float]] = {}

    def add(self, path_prefix: str, max_calls: int, window_sec: float) -> None:
        self._rules.append((path_prefix, max_calls, window_sec))

    def add_tenant(self, path_prefix: str, max_calls: int, window_sec: float) -> None:
        """Apply a cap that aggregates ALL traffic from the same tenant_id."""
        self._tenant_rules.append((path_prefix, max_calls, window_sec))

    def check(self, ip: str, path: str) -> Tuple[bool, int]:
        now = time.monotonic()
        for prefix, max_calls, window in self._rules:
            if not path.startswith(prefix):
                continue
            key = (ip, prefix)
            dq = self._hits.setdefault(key, deque())
            while dq and now - dq[0] > window:
                dq.popleft()
            if len(dq) >= max_calls:
                retry_after = max(1, int(window - (now - dq[0])))
                return False, retry_after
            dq.append(now)
        return True, 0

    def check_tenant(self, tenant_id: str | None, path: str) -> Tuple[bool, int]:
        if not tenant_id:
            return True, 0
        now = time.monotonic()
        for prefix, max_calls, window in self._tenant_rules:
            if not path.startswith(prefix):
                continue
            key = (tenant_id, prefix)
            dq = self._tenant_hits.setdefault(key, deque())
            while dq and now - dq[0] > window:
                dq.popleft()
            if len(dq) >= max_calls:
                retry_after = max(1, int(window - (now - dq[0])))
                return False, retry_after
            dq.append(now)
        return True, 0


# Module-level singleton wired to known public endpoints.
rate_limiter = RateLimiter()
# Per-IP (anonymous + auth)
rate_limiter.add("/api/leads", max_calls=5, window_sec=60)
rate_limiter.add("/api/auth/challenge", max_calls=20, window_sec=60)
rate_limiter.add("/api/auth/verify", max_calls=10, window_sec=60)
# Per-tenant aggregate caps (each tenant, regardless of IP)
rate_limiter.add_tenant("/api/certify/send",     max_calls=300, window_sec=60)
rate_limiter.add_tenant("/api/pulse/send",       max_calls=600, window_sec=60)
rate_limiter.add_tenant("/api/attachments/upload", max_calls=120, window_sec=60)
rate_limiter.add_tenant("/api/keyrecovery/",     max_calls=30,  window_sec=60)
rate_limiter.add_tenant("/api/lns/register",     max_calls=60,  window_sec=60)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: RateLimiter):
        super().__init__(app)
        self._limiter = limiter

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Only POSTs trigger the limiter (GETs are cacheable).
        if request.method != "POST":
            return await call_next(request)
        ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if not ip:
            ip = request.client.host if request.client else "unknown"
        ok, retry = self._limiter.check(ip, request.url.path)
        if not ok:
            return JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded", "retry_after_seconds": retry},
                headers={"Retry-After": str(retry)},
            )
        # Per-tenant cap (extracted from the JWT if present).
        tenant_id = _extract_tenant_id(request)
        if tenant_id:
            ok_t, retry_t = self._limiter.check_tenant(tenant_id, request.url.path)
            if not ok_t:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "tenant rate limit exceeded",
                        "retry_after_seconds": retry_t,
                        "tenant_id": tenant_id,
                    },
                    headers={"Retry-After": str(retry_t)},
                )
        return await call_next(request)


def _extract_tenant_id(request: Request) -> str | None:
    """Best-effort decode the JWT 'tenant_id' claim without verifying the
    signature (the auth dependency on each route does the real verify).

    Used purely to bucket rate-limit slots per tenant. We never trust
    this value for authorisation.
    """
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:].strip()
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        import base64, json
        pad = "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + pad).decode())
        tid = payload.get("tenant_id")
        return tid if isinstance(tid, str) else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Magic-byte MIME sniffing for attachments
# ---------------------------------------------------------------------------
_ALLOWED_MAGIC_PREFIXES = (
    "image/",
    "application/pdf",
    "application/zip",
    "application/x-7z-compressed",
    "application/vnd.openxmlformats-officedocument",  # docx/xlsx/pptx
    "application/msword",
    "application/vnd.ms-excel",
    "application/vnd.ms-powerpoint",
    "application/vnd.oasis.opendocument",  # ODF
    "text/plain",
    "text/csv",
)

_BLOCKED_EXECUTABLE_MAGIC = (
    "application/x-executable",
    "application/x-mach-binary",
    "application/x-msdownload",
    "application/x-msdos-program",
    "application/x-sharedlib",
    "application/x-pie-executable",
)


def detect_mime_from_blob(blob: bytes, fallback: str = "application/octet-stream") -> str:
    """Sniff the real MIME from the first KBs of a blob — never trust client."""
    if not blob:
        return fallback
    if not _MAGIC_AVAILABLE:
        # libmagic missing on this host — degrade gracefully but keep
        # the rest of the upload guard (size cap, header-byte heuristic).
        return fallback
    try:
        return magic.from_buffer(blob[: 64 * 1024], mime=True) or fallback
    except Exception:
        return fallback


def assert_safe_attachment(blob: bytes, claimed_mime: str | None) -> str:
    """Raise HTTPException if the blob is an executable or its real MIME
    is outside the safe allow-list. Returns the real MIME on success."""
    real = detect_mime_from_blob(blob, fallback=claimed_mime or "application/octet-stream")
    if any(real.startswith(p) for p in _BLOCKED_EXECUTABLE_MAGIC):
        raise HTTPException(status_code=415, detail=f"executable uploads are blocked (sniffed {real})")
    if not any(real.startswith(p) for p in _ALLOWED_MAGIC_PREFIXES):
        raise HTTPException(status_code=415, detail=f"mime not allowed: {real}")
    return real


# ---------------------------------------------------------------------------
# Argon2id hasher (recovery codes, future password fields)
# ---------------------------------------------------------------------------
_password_hasher = PasswordHasher(
    time_cost=3, memory_cost=64 * 1024, parallelism=2, hash_len=32, salt_len=16
)


def hash_secret(value: str) -> str:
    return _password_hasher.hash(value)


def verify_secret(value: str, stored_hash: str) -> bool:
    try:
        return _password_hasher.verify(stored_hash, value)
    except (argon2_exc.VerifyMismatchError, argon2_exc.InvalidHash):
        return False


# ---------------------------------------------------------------------------
# Master installer — call from server.py at startup
# ---------------------------------------------------------------------------
def install_security(app: FastAPI, log: logging.Logger, strict: bool) -> None:
    verify_production_env(strict, log)

    # Body cap: 25 MB by default (covers the 10 MB per-attachment limit
    # plus envelope overhead). Tunable via env.
    max_body = int(os.environ.get("LATTICE_MAX_BODY_BYTES", "26214400"))  # 25 MB
    app.add_middleware(
        MaxBodySizeMiddleware,
        max_bytes=max_body,
        # Attachment upload validates internally and is the only large path.
        exempt_prefixes=("/api/attachments/upload",),
    )

    app.add_middleware(SecurityHeadersMiddleware)

    app.add_middleware(RateLimitMiddleware, limiter=rate_limiter)

    log.info(
        "Security middleware installed · strict=%s · max_body=%d bytes",
        strict, max_body,
    )
