# Lattice Network — Roadmap operativa post-Sprint-1

> Tutto quello che NON è stato fatto nella sessione di chiusura, perché
> rischio-troppo-alto o fuori-portata di una conversazione di codice.
> Ogni voce è un ticket eseguibile, con stima e rischio.

## Tickets aperti

### LAT-201 · Refactor `server.py` → `routes/*.py`
**Stima**: 3-4 giorni con CI verde a ogni commit
**Rischio**: alto se fatto in un solo passaggio · basso se incrementale
**Approccio raccomandato** (branch `refactor/routes`):

1. Crea `backend/_deps.py` con tutti gli oggetti condivisi:
   ```python
   from motor.motor_asyncio import AsyncIOMotorClient
   import logging, os
   client = AsyncIOMotorClient(os.environ["MONGO_URL"])
   db = client[os.environ["DB_NAME"]]
   log = logging.getLogger("lattice.admin")
   # … _utc_iso, _det_hex, ROLE_SOVEREIGN, PQC_ALGORITHM, ecc.
   ```
2. Sposta UN router alla volta (suggested order):
   - `routes/alerts.py` ← `/api/qbft/alerts` + `/api/alerts/webhooks*` (~150 righe)
   - `routes/keyrecovery.py` ← `/api/keyrecovery/*` (~280 righe)
   - `routes/leads.py` ← `/api/leads*` (~180 righe)
   - `routes/auth.py` ← `/api/auth/{challenge,verify,logout,sessions}*` (~400 righe)
   - `routes/certify.py` ← `/api/certify/*` (~600 righe)
   - `routes/pulse.py` ← `/api/pulse/*` (~500 righe)
   - `routes/qbft.py` ← `/api/qbft/*` + `/api/mixnet/*` (~300 righe)
3. Ad ogni step:
   - `server.py` fa `from routes.alerts import router as alerts_router`
     e `api.include_router(alerts_router)` (mantiene path prefix)
   - Esegui `pytest -q backend/tests/` — DEVE essere `79 passed`
   - Commit con messaggio `refactor: extract X to routes/X.py`
4. Quando server.py scende sotto ~1500 righe, congela.

**Definition of Done**: server.py < 1500 righe, ogni router auto-contenuto,
tutti i test attivi verdi, CI green.

---

### LAT-202 · Groth16 reale via `arkworks`
**Stima**: 3 giorni
**Rischio**: basso (puro Rust, prover offline)
**Approccio**:

1. Crea `lattice/prod/zk-rln-prover/Cargo.toml` con:
   ```toml
   [dependencies]
   ark-bn254 = "0.5"
   ark-groth16 = "0.5"
   ark-circom = "0.5"
   poseidon-ark = "0.1"
   ```
2. Scrivi il circuito Circom per ZK-RLN:
   - input privato: `secret` (felt 251 bit)
   - input pubblico: `commitment = Poseidon(secret)`, `epoch`, `nullifier = Poseidon(secret, epoch)`
   - constraint: il prover dimostra di conoscere `secret` senza rivelarlo
3. Genera setup ceremony (Powers of Tau riusabile da Hermez/Aztec).
4. Espongli via PyO3 al backend: `prove(secret, epoch) -> proof_bytes`
   e `verify(proof_bytes, commitment, epoch, nullifier) -> bool`.
5. Sostituisci la chiamata Chaum-Pedersen attuale (`rln_zk_prove` in
   `server.py:2267`) con `groth16_prove(...)`. Il backend già accetta
   proof opaca, quindi il refactor è isolato.

**Definition of Done**: `/api/rln/zk/verify` accetta proof Groth16 valida
e rigetta proof contraffatte; benchmark prover < 200 ms per proof.

---

### LAT-203 · Multi-host deploy (4 VM QBFT + 3 region Mixnet)
**Stima**: 1 settimana di setup operativo, **zero codice**
**Rischio**: medio (NAT/firewall/TLS tra VM)
**Approccio**:

1. Provisioning 7 VM (Hetzner / OVH / scaleway, regione EU):
   - 4 nodi QBFT in regioni diverse (FRA/AMS/PAR/MIL)
   - 3 nodi Mixnet in regioni diverse (DUB/WAR/HEL)
2. Su ogni VM: clona repo, `bash deploy/installa.sh`, fai partire **solo**
   il container del rispettivo ruolo (override profiles in compose).
3. Override `endpoint:` nei seed (`NODE_LABELS` in server.py): le URL
   QBFT diventano `https://val-01.lattice-net.example/health`.
4. WireGuard mesh tra le 7 VM per crittografia in-transit (anche dentro UE).
5. Update `docker-compose.yml` con env `LATTICE_VALIDATOR_ENDPOINTS` da
   leggere a startup invece di hard-code `127.0.0.1:9001..9004`.

**Definition of Done**: `/api/qbft/alerts` da una VM mostra 4/4 validators
ONLINE su 4 hostname distinti, latency_ms riflette la geografia reale.

---

### LAT-204 · Pen-test esterno
**Stima**: 2-3 settimane (commissionato a terzi)
**Costo**: 8-15 k€ per audit OWASP standard
**Approccio**:

1. Scegli vendor (Bishop Fox / NCC Group / Yarix in IT).
2. Forniscigli: deploy isolato su VM dedicata, account sovereign + tenant,
   `.keypair.json` di test, accesso read-only al codice via tarball.
3. Scope minimo: PQC implementation, JWT lifecycle, X25519 recovery flow,
   ZK-RLN, cross-tenant isolation, container escape, supply-chain.
4. Riservati 1 settimana extra per fix dei finding.

**Definition of Done**: report finale con `severity_high == 0` e
`severity_critical == 0`.

---

### LAT-205 · E2E Playwright frontend
**Stima**: 2 giorni
**Rischio**: basso
**Approccio**:

1. Crea `/app/tests/e2e/playwright.config.ts`.
2. 7 spec coprono i flow critici:
   - landing → lead capture → notarizzazione on-chain
   - tenant register → admin login → onboarding dipendenti
   - employee login → invia Certify → destinatario riceve E2E
   - admin enroll backup 2-di-3 → recovery con 2 guardian
   - admin Pulse chat con dipendente
   - alert webhook CRUD da /qbft
   - logout dopo idle 15min
3. Wire-in nel `.github/workflows/ci.yml` come 4° job parallelo.

**Definition of Done**: ogni spec passa contro un container Lattice fresh
montato dal CI; report HTML auto-pubblicato come artifact.

---

## Stato Sprint 1 (chiuso)

| Voce | Stato | Test |
|---|---|---|
| Recovery UX zero-friction | ✅ | iter_24/26 |
| Rate limit per-tenant | ✅ | iter_26 |
| `/api/qbft/alerts` real-time | ✅ | iter_25/26 |
| Alert webhooks (Slack/Telegram/JSON) | ✅ | iter_25 |
| `_infra_health_loop` background | ✅ | manuale |
| DeliveryReceipt verify ok | ✅ | iter_17/26 |
| Backfill 13 TX legacy | ✅ | manuale |
| CI GitHub Actions | ✅ | self-validating |
| Stale tests quarantinati | ✅ | 135 skip |

**Test totali**: 79 passed, 135 quarantined, 0 failures.

---

## Decisione architetturale: cosa NON va fatto

* **NON** ricompilare `core/lattice-crypto` a WASM. Il crate `lattice-wasm`
  fornisce già PQC reale al browser; ricompilare anche `lattice-crypto`
  significa duplicare 4 MB di binari per zero beneficio funzionale.
* **NON** wireare un binario `lattice-admin-console` Rust separato. La
  console React + FastAPI è funzionalmente sostitutiva e già in produzione.
* **NON** wireare `certify-gateway` SMTP → NotaryTX. Scelta architetturale
  esplicita del prodotto: zero SMTP esterno. Le mail Certify si scambiano
  solo via Lattice Network.
