# Lattice Network — FASE 3 Roadmap

Obiettivo: portare l'intero backend Python (`server.py` + 15 moduli `routes/*`) su Rust nativo (axum) per arrivare al **70%+ di Rust su GitHub Linguist** e avere un binario unico autocontento.

Strategia: **migrazione incrementale path-by-path** con nginx come reverse-proxy che inoltra a Rust ciò che è già pronto e a Python tutto il resto. Mai un big-bang.

---

## Stato attuale (Iter 43 — Spike Step 1)

🟢 **Binario `lattice-gateway`** in `/app/lattice/prod/lattice-gateway/`:
   - Stack: axum 0.7 + tokio + mongodb 3.2 + reqwest + tower-http (CORS)
   - 12 endpoint read-only nativi (~500 righe Rust)
   - Talk-to-MongoDB diretto, niente PyO3 hop
   - Compila in 1m30s sul container dev (~14 MB ELF binary aarch64)
   - **Parità Python verificata**: `/api/ledger/stats` produce JSON byte-identico al backend Python

### Endpoint portati ✅
| Endpoint | Letture giornaliere stimate | Owner Rust |
|----------|------------------------------|------------|
| `GET /api/health` | landing live-strip | `lattice-gateway` |
| `GET /api/ledger/stats` | dashboard + landing | `lattice-gateway` |
| `GET /api/ledger/blocks` | block explorer | `lattice-gateway` |
| `GET /api/qbft/status` | landing + console | `lattice-gateway` |
| `GET /api/qbft/nodes` | console Nodi QBFT | `lattice-gateway` |
| `GET /api/mixnet/status` | landing + console | `lattice-gateway` |
| `GET /api/certify/stats` | dashboard | `lattice-gateway` |
| `GET /api/certify/recent` | dashboard recent | `lattice-gateway` |
| `GET /api/lns/active` | dashboard + explorer | `lattice-gateway` |
| `GET /api/tenants/public` | landing + onboarding | `lattice-gateway` |
| `GET /api/transactions` | dashboard + explorer | `lattice-gateway` |
| `GET /api/explorer/stats` | block explorer | `lattice-gateway` |

→ **Stimato 70% del traffico letto** ora servibile dal binario Rust.

---

## FASE 3 — Roadmap 7 milestone

### M1 (questa sessione) — Spike + 12 endpoint read-only ✅
Done. 500 righe Rust nuove + parity check OK.

### M2 — Reverse-proxy split (1 turno)
Configurare nginx per inoltrare a `lattice-gateway:8002` i 12 path già pronti; tutto il resto al backend Python su 8001. Verifica E2E sul preview.
* File da modificare: `deploy/nginx-frontend.conf`
* Supervisor: aggiungere `lattice_gateway` come 8° processo
* Test: curl + screenshot + parity sui clienti reali

### M3 — Lead capture write path (1-2 turni · ~600 righe)
Portare in Rust il primo endpoint **scrittura**:
* `POST /api/leads` con SHA3-512 + ML-DSA-65 signing + chiamata a `lattice-crypto` per la firma + parlare ai validatori Rust per il quorum
* Sostituisce `backend/routes/leads.py::_notarize_lead_onchain`
* Implementare in `lattice-gateway` o in nuovo crate `prod/leads-service`
* Email SMTP (Aruba) tramite `lettre` crate
* **Dipendenze**: chain finalisation logic da `backend/chain.py` — va portata anche

### M4 — `chain.py` Rust port (3-4 turni · ~1200 righe)
Il cuore del ledger:
* `tx_canonical_message`, `block_canonical_message`, `merkle_root`, `tx_leaf_hash`, `compute_block_hash`
* `build_signed_block`, `qbft_finalise`, `finalise_block_for_tx`, `finalise_batch_block`
* Già esiste `lattice-node` crate ma è incompleto — espanderlo
* **Output**: nuovo modulo riusabile in `lattice-gateway`

### M5 — LNS + Tenants + Auth (2-3 turni · ~1500 righe)
* `POST /api/lns/register|revoke`, `DELETE /api/lns/{id}` — chiama chain finalise
* `POST /api/tenants/register` — bootstrap admin LNS + keypair delivery
* `POST /api/auth/challenge` + `POST /api/auth/verify` — JWT ML-DSA-65
* Quota enforcement (license check, `license.py` port)
* **Dipendenze**: M4 (chain), envelope encryption per sessione (M6)

### M6 — Envelope + License + Secrets (1-2 turni · ~800 righe)
* Argon2id + AES-256-GCM at-rest (`secret_manager.py` port)
* License signing ML-DSA-65 verification (`license.py`)
* `GET /api/admin/license/*`, `/admin/secrets/*`
* **Dipendenze**: `lattice-crypto` già pronto

### M7 — Certify + Pulse (3-4 turni · ~2000 righe)
* `POST /api/certify/send` con E2E envelope X25519 + AEAD
* `POST /api/certify/{id}/receipt.pdf` — PDF generation in Rust via `printpdf` o `genpdf`
* `POST /api/pulse/send` — Double-Ratchet via `pulse-ratchet` crate (esiste già!)
* Mixnet route selection — collega a `prod/mixnet-relay`
* OTS Bitcoin anchor — porting di `ots_anchor.py` (è semplice, sotto-100 righe)
* **Dipendenze**: M4 + M6

### M8 — Cutover + Python kill (1 turno)
* Nginx rilancia 100% del traffico a `lattice-gateway:8002`
* Python `server.py` rimosso dal supervisor
* Backend Python archiviato in `legacy/python-gateway/`
* GitHub Linguist: ~70%+ Rust 🎉

---

## Metriche obiettivo

| Metrica | Prima FASE 3 | Dopo M2 | Dopo M8 |
|---------|--------------|---------|---------|
| % Rust su GitHub | 6.5% | ~10% | ~70% |
| Container image size | 1.2 GB | 1.2 GB | ~180 MB |
| Cold-start backend | ~3.5s | ~2s | ~0.4s |
| RSS memory backend | ~180 MB | ~180 MB | ~25 MB |
| Latenza p99 `/api/ledger/stats` | 22 ms | 7 ms | 5 ms |
| Throughput letture | ~800 RPS | ~3000 RPS | ~8000 RPS |

(stime preliminari basate su benchmark axum/python tipici · da validare con `wrk`)

---

## Rollback safety

Ogni milestone è **deployabile indipendentemente** e **rollbackabile in 30 secondi** rimuovendo la routing rule da nginx. Se M3 introduce regressioni sul lead capture, basta togliere quel `location /api/leads` da nginx e Python riprende il traffico immediatamente.

---

## Stima totale ore-uomo

| Milestone | Stima ottimistica | Stima realistica | Tokens 1 turno |
|-----------|-------------------|------------------|----------------|
| M1 (done) | 4h | 8h | ~50k |
| M2 | 2h | 4h | ~30k |
| M3 | 8h | 16h | ~60k |
| M4 | 16h | 24h | ~100k (multi-turno) |
| M5 | 12h | 20h | ~80k (multi-turno) |
| M6 | 8h | 12h | ~50k |
| M7 | 20h | 32h | ~140k (multi-turno) |
| M8 | 4h | 8h | ~20k |
| **TOT** | **74h** | **124h** | **~530k** |

In pratica: **~3-4 settimane full-time** se lavorato bene. Con un agente E1 che fa 1 turno = 30-60 min, sono **circa 15-20 turni distribuiti su 1-2 mesi** di lavoro saltuario.

---

## Riferimenti

- Workspace: `/app/lattice/`
- Binario gateway: `/app/lattice/prod/lattice-gateway/`
- Backend Python da migrare: `/app/backend/server.py` + `/app/backend/routes/*.py`
- Schema MongoDB documentato in `/app/memory/PRD.md`

© 2026 Lattice Network · FASE 3 strategy doc
