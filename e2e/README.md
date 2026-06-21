# Lattice Network — End-to-End Test Suite (Playwright)

This directory contains the regression test suite that drives a real
Chromium browser against the running Lattice frontend + backend stack.

## Quick start

```bash
cd /app/e2e
yarn install                       # installs @playwright/test
yarn install:browsers              # downloads Chromium (~150MB)
yarn test                          # runs the suite (headless)
yarn test:headed                   # watch the browser
yarn test:report                   # open the HTML report after a run
```

## What's covered

| File | Flow tested |
|------|-------------|
| `tests/landing.spec.ts` | Public landing renders, whitepaper link works |
| `tests/sovereign_health.spec.ts` | `/admin/health` shows validators 4/4, license badge, secrets badge |
| `tests/sovereign_license.spec.ts` | `/api/admin/license/status` returns signed enterprise license; forged signature rejected |
| `tests/sovereign_secrets.spec.ts` | `/api/admin/secrets/status` returns `unlocked=true`; `/init` rejected when static key loaded |
| `tests/ledger_reachable.spec.ts` | Core read endpoints (`/qbft/status`, `/mixnet/status`, `/ledger/stats`, `/certify/stats`) all 200 |

## Targeting a custom environment

```bash
PLAYWRIGHT_BASE_URL=https://my-tenant.banca-xyz.it yarn test
```

Without the env var the suite reads `REACT_APP_BACKEND_URL` from
`../frontend/.env` and points there — matches the working preview.

## Updating snapshots / adding tests

* Tests are TypeScript using `@playwright/test`
* `data-testid` selectors are the contract — see the test files for naming
* When adding a new admin page, add a smoke test that just `page.goto()`s
  the route and asserts that the `PageHeader`'s `title` is visible

## CI integration

Workflow pre-configurato in `.github/workflows/e2e.yml`:

* **Trigger**: push/PR su `main`/`develop` quando cambiano `backend/`, `frontend/` o `e2e/`.
* **Pipeline** (≈8 minuti):
  1. Avvia MongoDB come service
  2. Boot del backend FastAPI su `:8001` (con licenza ML-DSA enterprise generata al volo)
  3. Build + serve del frontend CRA su `:3000`
  4. Installa Chromium e lancia `npx playwright test`
  5. Carica come artifact: `playwright-report/` (14 giorni) + log del backend in caso di failure

Per testare contro un'istanza già deployata (staging/prod):

```bash
# In GitHub: Actions → E2E → Run workflow → target_url=https://staging.lattice.it
```

Esiste anche `.github/workflows/backend-tests.yml` per il pytest standalone
(16 admin + 4 ots + 10 iter30) — gira più veloce (≈3 min) e blocca i merge
prima del lancio dei full E2E.
