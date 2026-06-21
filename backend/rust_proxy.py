"""
Lattice Network — Rust gateway proxy middleware (M8 finale).

Intercepts requests in the FastAPI app and forwards them to the in-process
Rust gateway (port 8002) when the path is one of the 89 Rust-native routes.

Why a Python-side proxy?
  In the **preview** Kubernetes container, the ingress routes /api/* to
  port 8001 (FastAPI), not 8002 (Rust). This middleware bridges that gap
  so the frontend transparently hits the Rust binary for every endpoint
  we've already ported — while remaining 100% backwards compatible with
  the legacy Python routes still bolted on FastAPI.

  In **production** (Hetzner / docker-compose), nginx (config in
  `deploy/nginx-frontend.conf`) does the same split-routing at L7 and
  this Python proxy is a no-op (it's bypassed because nginx never lets
  matched paths reach the Python container).
"""

from __future__ import annotations

import os
import re

import httpx
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

RUST_GATEWAY = os.environ.get(
    "LATTICE_RUST_GATEWAY_URL", "http://127.0.0.1:8002"
).rstrip("/")

# -- Path matcher -----------------------------------------------------------
# Exact paths (HTTP method ignored — Rust gateway handles per-method auth).
_EXACT = {
    "/api/health", "/api/me", "/api/pqc/info", "/api/rust/info", "/api/rust/selftest",
    "/api/ledger/stats", "/api/ledger/blocks", "/api/qbft/status", "/api/qbft/nodes",
    "/api/qbft/alerts", "/api/mixnet/status", "/api/mixnet/topology", "/api/mixnet/route",
    "/api/certify/stats", "/api/certify/recent", "/api/certify/send",
    "/api/certify/pec/webhook",
    "/api/lns", "/api/lns/check", "/api/lns/active", "/api/lns/register",
    "/api/tenants", "/api/tenants/public", "/api/tenants/register",
    "/api/explorer/stats", "/api/transactions",
    "/api/leads", "/api/leads/unread-count", "/api/leads/read-all",
    "/api/vendor/stats", "/api/vendor/tenants",
    "/api/pulse/send", "/api/pulse/conversations", "/api/pulse/messages",
    "/api/auth/challenge", "/api/auth/verify", "/api/auth/logout",
    "/api/auth/revoke-all", "/api/auth/sessions",
    "/api/auth/2fa/enroll", "/api/auth/2fa/verify",
    "/api/auth/2fa/disable", "/api/auth/2fa/status",
    "/api/audit/verify", "/api/audit/stream", "/api/audit/export",
    "/api/alerts/webhooks", "/api/alerts/test-fire",
    "/api/admin/health/overview", "/api/admin/chain/reset",
    "/api/admin/license/status", "/api/admin/license/verify",
    "/api/admin/license/install", "/api/admin/license/reload",
    "/api/admin/secrets/status", "/api/admin/secrets/init",
    "/api/admin/secrets/unlock", "/api/admin/secrets/lock",
    "/api/admin/secrets/seal", "/api/admin/secrets/open",
    "/api/admin/ots/status", "/api/admin/ots/anchor", "/api/admin/ots/upgrade-all",
    "/api/leads", "/api/logs/stream",
    "/api/attachments/upload",
}
# Regex patterns (parameterised paths).
_REGEX = [
    re.compile(p) for p in [
        r"^/api/certify/[^/]+$",
        r"^/api/certify/[^/]+/(read|restore)$",
        r"^/api/certify/[^/]+/receipt\.pdf$",
        r"^/api/pulse/session/[^/]+$",
        r"^/api/keystore/[^/]+$",
        r"^/api/ledger/verify/[^/]+$",
        r"^/api/audit/public/[^/]+$",
        r"^/api/lns/[^/]+/(enc-key|role)$",
        r"^/api/tenants/[^/]+/(employees|stats)$",
        r"^/api/leads/[^/]+(/read)?$",
        r"^/api/auth/sessions/[^/]+/revoke$",
        r"^/api/admin/ots/upgrade/[^/]+$",
        r"^/api/admin/ots/anchors/[^/]+/proof$",
        r"^/api/attachments/[^/]+(/meta)?$",
    ]
]

# Hop-by-hop headers we MUST strip per RFC 7230 §6.1 + framing headers
# that mess with httpx's own re-encoding.
_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade",
    "content-length", "host",
}


def is_rust_path(path: str) -> bool:
    if path in _EXACT:
        return True
    return any(rx.match(path) for rx in _REGEX)


class RustGatewayProxy(BaseHTTPMiddleware):
    """ASGI middleware that forwards matched paths to the Rust gateway."""

    def __init__(self, app):
        super().__init__(app)
        # Long-lived client (HTTP/1.1 keep-alive); SSE uses streaming.
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=2.0, read=60.0, write=10.0, pool=5.0),
            base_url=RUST_GATEWAY,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not is_rust_path(path):
            return await call_next(request)

        # Forward request as-is.
        method = request.method.upper()
        query = request.url.query
        url = path + (f"?{query}" if query else "")
        body = await request.body()
        upstream_headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in _HOP
        }

        try:
            # SSE / streaming endpoints — must use stream mode.
            is_stream = path in ("/api/audit/stream",)
            if is_stream:
                # Long-lived stream — open separate client to keep connection
                # tied to the request lifetime.
                async def stream_iter():
                    async with httpx.AsyncClient(
                        base_url=RUST_GATEWAY, timeout=None,
                    ) as cli:
                        async with cli.stream(method, url,
                            content=body, headers=upstream_headers) as r:
                            async for chunk in r.aiter_raw():
                                yield chunk
                from starlette.responses import StreamingResponse
                # Probe once to copy headers (no actual body consumed yet)
                return StreamingResponse(stream_iter(),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache"})

            resp = await self._client.request(
                method, url, content=body, headers=upstream_headers
            )
        except httpx.RequestError as e:
            return Response(
                content=f'{{"detail":"rust gateway unreachable: {type(e).__name__}"}}',
                status_code=502,
                media_type="application/json",
            )

        # Filter hop-by-hop headers on the way back.
        out_headers = {
            k: v for k, v in resp.headers.items()
            if k.lower() not in _HOP
        }
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=out_headers,
            media_type=resp.headers.get("content-type"),
        )
