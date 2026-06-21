# `backend/routes/` — Modular FastAPI routes

This package is the home for the **gradual refactor** of the monolithic
`server.py` (~6300 lines) into focused, testable modules.

## Status

| Module | Routes | Lines moved | Status |
|--------|--------|-------------|--------|
| `routes/ots.py` | `/api/admin/ots/*` | ~107 | ✅ Done (Iter_29) |
| `routes/secrets.py` | `/api/admin/secrets/*` | ~79 | ✅ Done (Iter_30) |
| `routes/license_admin.py` | `/api/admin/license/*` | ~54 | ✅ Done (Iter_30) |
| `routes/admin_health.py` | `/api/admin/health/*` | ~102 | ✅ Done (Iter_30) |
| `routes/backup.py` | `/api/admin/backup/*` | ~85 | ✅ Done (Iter_30) |
| `routes/lns.py` | `/api/lns/{active,check,register,revoke,{id}}` | ~340 | ✅ Done (Iter_32 + 35 — full) |
| `routes/qbft.py` | `/api/qbft/{status,nodes,alerts}` | ~210 | ✅ Done (Iter_33) |
| `routes/certify.py` | `/api/certify/{stats,recent}` | ~83 | ✅ Done (Iter_33 — read-only) |
| `routes/pulse.py` | `/api/pulse/{conversations,messages}` | ~83 | ✅ Done (Iter_33 — read-only) |
| `routes/tenants.py` | `/api/tenants/{,/public,/{id},/{id}/employees,/{id}/stats,POST /register}` | ~210 | ✅ Done (Iter_34 + 36 — full) |
| `routes/keyrecovery.py` | `/api/keyrecovery/{status,enrollment,share-for-guardian,pending-as-guardian,POST enroll/request/contribute}` | ~270 | ✅ Done (Iter_34 + 36 — full) |
| `routes/auth.py` | `/api/me` + `/api/auth/{challenge,verify,logout,revoke-all,sessions,2fa/*}` | ~360 | ✅ Done (Iter_36/37/38 — full) |
| `auth_state.py` | JWT helpers (issue/decode/is_revoked) | ~68 | ✅ Done (Iter_37) |
| `routes/audit_public.py` | `/api/audit/{public,verify}` | ~114 | ✅ Done (Iter_37) |
| `routes/certify_mutating.py` | `/api/certify/{send,{id}/read,{id}/restore,{id}/receipt.pdf,DELETE {id}}` | ~514 | ✅ Done (Iter_38 — full) |
| `core.py` | helpers + PQC keystore | ~180 | ✅ Done (Iter_32) |
| `models.py` | 27 Pydantic wire models | ~460 | ✅ Done (Iter_32) |
| `chain.py` | block construction + QBFT finalisation | ~331 | ✅ Done (Iter_34) |
| `routes/pulse_mutating.py` | `POST /api/pulse/send` + `GET /api/pulse/session/{conv_id}` | ~407 | ✅ Done (Iter_39 — full) |
| `routes/leads.py` | `POST/GET/PATCH /api/leads/*` + LeadCapture notarisation | ~220 | ✅ Done (Iter_40) |
| `routes/attachments.py` | `/api/attachments/upload,meta,download` | ~167 | ✅ Done (Iter_40) |
| `routes/pec_webhook.py` | `PUT/GET /api/tenants/{id}/pec-webhook` | ~70 | ✅ Done (Iter_40) |
| `routes/vendor_rln.py` | `/api/vendor/*` + `/api/rln/*` (read-only) | ~165 | ✅ Done (Iter_40) |
| `routes/ledger_public.py` | `/api/ledger/{stats,blocks,verify}` + `/api/transactions{,/export}` + `/api/keystore/{entity}` + `/api/pqc/info` + `/api/rust/{info,selftest}` | ~250 | ✅ Done (Iter_40) |
| `data/demo_seed_data.py` | DEMO_TENANTS_CONFIG + DEMO_PROFILES + helpers | ~253 | ✅ Done (Iter_40) |

### Why the mutating routes are deferred

These handlers reuse 30+ helper functions defined inline in `server.py`
(`_pqc_sign`, `_get_or_create_keypair`, `_utc_iso`, `_det_hex`,
`_qbft_known_validators`, `_seed_if_empty`, plus 20+ Pydantic models).
A clean extraction first requires moving the helpers into a new
`backend/core.py` module to avoid circular imports — otherwise
`routes/lns.py` would import from `server.py` which already imports
from `routes/`.

**Recommended next step:**
1. Create `backend/core.py` and move pure helper functions (no FastAPI
   decorators) there.
2. Move the Pydantic models into `backend/models.py`.
3. Then each `routes/<area>.py` can import cleanly from `core` + `models`.
4. Only THEN extract the routes (~600 lines per area).

Estimated effort: 1 full session per area (qbft cheap, lns/certify/pulse
~3-4h each), with comprehensive regression testing between steps.

The admin/* extractions (secrets, license, health, backup, ots) were
straightforward because their handlers depend only on 3-4 well-defined
constants (db, NODE_LABELS, CHAIN_ID, etc) that can be passed through
`register()` arguments.

## Extraction pattern

Each module exposes a `register(api, *, db, require_sovereign, …)`
function so server.py can wire dependencies WITHOUT importing back from
server.py (which would cause a circular import).

### Template

```python
# routes/<area>.py
from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Callable

router = APIRouter(prefix="/<area>", tags=["<area>"])

def register(api: APIRouter, *, db: Any, require_sovereign: Callable, **opts) -> None:
    @router.get("/...")
    async def handler(_sov: dict = Depends(require_sovereign())) -> dict:
        ...
    api.include_router(router)
```

### server.py wiring

```python
from routes import ots as ots_routes

# … at module bottom, BEFORE app.include_router(api):
ots_routes.register(api, db=db, require_sovereign=require_platform_sovereign, chain_id=CHAIN_ID)
```

## Why incremental

The refactor is intentionally slow:

1. **Zero behaviour change per extraction** — every route returns the
   same JSON, the same status codes, the same headers.
2. **Run the pytest suite after each extraction** — the existing
   `backend/tests/test_iteration_23_admin.py` covers admin/* and is the
   acceptance gate.
3. **Stop the moment something breaks** — extract one area at a time.

Future agents: do NOT do "while you're at it" refactors during an
extraction. Move the code verbatim, parameterise the globals, run the
tests, commit, only THEN improve.
