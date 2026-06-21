<div align="center">

# 🦀 Lattice Network

**Sovereign B2B Cybersecurity Ecosystem · Post-Quantum · 100% Self-Hosted**

[![Rust](https://img.shields.io/badge/Rust-9400+_LOC-orange?logo=rust)](./lattice)
[![Axum](https://img.shields.io/badge/Axum-89_endpoints-blue?logo=rust)](./lattice/prod/lattice-gateway)
[![ML-DSA-65](https://img.shields.io/badge/PQC-ML--DSA--65_NIST_FIPS_204-green)](#-post-quantum-cryptography)
[![QBFT](https://img.shields.io/badge/Consensus-QBFT_4--validator-purple)](#-consensus--byzantine-fault-tolerance)
[![Bitcoin](https://img.shields.io/badge/Anchor-OpenTimestamps-yellow?logo=bitcoin)](#-bitcoin-anchoring)
[![License](https://img.shields.io/badge/License-BSL_1.1_/_Commercial-red)]()

*Lattice è un'infrastruttura di comunicazione sicura on-premise per aziende e PA italiane —
post-quantum end-to-end, ledger QBFT-finalizzato, mail certificata legalmente opponibile,
chat Signal-style, isolamento tenant by-design.*

</div>

---

## 🎯 Cosa fa Lattice

| Modulo | Descrizione | Stato |
|--------|-------------|-------|
| **Pulse** | Chat E2EE Signal-style con Double-Ratchet PQXDH + sealed sender via mixnet Loopix 3-hop | ✅ Live |
| **Certify** | Posta certificata legalmente opponibile (PEC-compat) con receipt PDF firmata ML-DSA-65 e notarizzata on-chain | ✅ Live |
| **LNS** | Lattice Name System — identità verificabili sotto dominio aziendale (`alice.acme.lns`) | ✅ Live |
| **Tenants** | Multi-tenant isolation by-design, cross-company forbidden by default | ✅ Live |
| **Sovereign Console** | Dashboard amministrativa con KPI live: 4 validatori, 9 relay mixnet, blockchain, alerts | ✅ Live |
| **OTS Anchor** | Notarizzazione blockchain Lattice → **Bitcoin** via OpenTimestamps (immutable forever) | ✅ Live |

---

## 🔐 Post-Quantum Cryptography

Ogni firma è eseguita in **Rust nativo** tramite `pqcrypto-mldsa 0.1`, nessun PyO3, nessun fallback.

| Primitivo | Standard | Uso | Performance |
|-----------|----------|-----|-------------|
| **ML-DSA-65** | NIST FIPS 204 (ex-Dilithium3) | Firme on-chain · receipt PEC | sk 4032B · pk 1952B · sig 3309B · verify ~1.5ms |
| **ML-KEM-768** | NIST FIPS 203 (ex-Kyber-768) | PQXDH handshake Pulse | pk 1184B · ct 1088B |
| **AES-256-GCM** | NIST SP 800-38D | AEAD payload Pulse · envelope at-rest | 12B nonce · 128bit tag |
| **SHA3-512** | NIST FIPS 202 | Audit chain · canonical preimage | 1182 entries verified byte-perfect Python↔Rust |
| **Poseidon** | Starknet Felt prime | ZK-RLN nullifier (anti-spam) | cross-interop `poseidon_py` ↔ `starknet-crypto` verified |

---

## ⚖️ Consensus · Byzantine Fault Tolerance

- **QBFT** (Quorum Byzantine Fault Tolerance) — 4 validatori indipendenti, quorum `2f+1 = 3/4`
- Ogni block è firmato **ML-DSA-65** da almeno 3 validatori
- Ogni transazione critica (LNS register, Tenant register, Pulse anchor, Certify send, OTS pin) genera un block
- Anchor on-chain ogni 3 messaggi Pulse, ogni mail Certify, ogni receipt firmata
- I 4 binari validator sono in `/lattice/prod/qbft-validator` — 100% Rust standalone

---

## 🟧 Bitcoin Anchoring (OpenTimestamps)

Ogni block Lattice finalizzato può essere ancorato a **Bitcoin** via OTS:

```
Block #N (Lattice) ──SHA-256──► digest 32B
                                   │
              ┌────────────────────┴────────────────────┐
              │ POST /digest                            │
              ▼                                          │
   a.pool.opentimestamps.org                            │
   b.pool.opentimestamps.org                            │
   alice.btc.calendar.catallaxy.com                     │
              │                                          │
       .ots proof (237B) DetachedTimestampFile           │
              │                                          │
   Verified by ots verify CLI ───────────────────────────┘
   + Python opentimestamps-py parses byte-perfect
   + Bitcoin mempool bundling ~3h
   + Final btc_attested=true tag 0588960d73d71901
```

Endpoint: `POST /api/admin/ots/anchor` · `POST /api/admin/ots/upgrade-all` · `GET /api/admin/ots/anchors/{id}/proof`

---

## 📊 Metriche Codebase

| Metrica | Valore |
|---------|--------|
| **Rust LOC (sorgente, escluso `target/`)** | **9,398** |
| **Endpoint Rust nativi** | **89 / ~110 totali (~80%)** |
| **Endpoint Python residui** | ~21 (deep crypto BN254 + Shamir + admin tools) |
| **Test E2E passati** | 69 XHR su 8 pagine, 0 fail |
| **Validators QBFT live** | 4/4 ONLINE (latency 0.1-0.2ms) |
| **Mixnet relays Loopix** | 9 (3 layer × 3 relay) |
| **Audit chain entries verified** | 1182 byte-perfect Python↔Rust |

---

## 🚀 Quick Start

### Production deploy (Hetzner / bare-metal)
```bash
ssh root@<your-server>
git clone https://github.com/Bricscoin2026/lattice-network.git /opt/lattice-network
cd /opt/lattice-network
bash deploy/deploy-fase2.sh
```

Lo script `deploy-fase2.sh` configura nginx + TLS Let's Encrypt + supervisord per `lattice-gateway` (Rust) + `qbft-validator x4` + `mixnet-relay x3` + MongoDB con auth.

### Development
```bash
# Backend Rust
cd lattice && cargo build --release -p lattice-gateway
./target/release/lattice-gateway     # :8002

# Backend Python (proxy + legacy endpoints)
cd backend && pip install -r requirements.txt
uvicorn server:app --port 8001

# Frontend
cd frontend && yarn install && yarn dev   # :3000
```

---

## 📂 Struttura

```
lattice-network/
├── lattice/                       Cargo workspace (Rust)
│   ├── core/lattice-crypto/       ML-DSA-65 · ML-KEM-768 · SHA3 (BSL 1.1)
│   ├── core/lattice-node/         QBFT consensus primitives (BSL 1.1)
│   ├── core/pulse-protocol/       AES-256-GCM sealed sender (BSL 1.1)
│   ├── core/pulse-ratchet/        PQXDH + Double Ratchet (BSL 1.1)
│   ├── core/lattice-zk-rln/       rate-limit ZK Poseidon (BSL 1.1)
│   ├── core/lattice-mixnet/       Loopix mixnet relay (BSL 1.1)
│   ├── prod/lattice-gateway/      Axum API server (89 endpoints)
│   ├── prod/qbft-validator/       Standalone validator binary
│   └── prod/mixnet-relay/         Standalone mixnet relay
├── backend/                       Python FastAPI (proxy + legacy)
│   ├── server.py                  Main app + middleware
│   ├── rust_proxy.py              Middleware → Rust :8002
│   └── routes/                    Endpoint legacy (RLN BN254, Keyrecovery)
├── frontend/                      React SPA (Vite + Shadcn UI)
│   └── src/pages/                 Sovereign Dashboard · Pulse · Certify
├── deploy/                        nginx config + deploy script
└── memory/                        PRD.md · CHANGELOG.md · ROADMAP.md
```

---

## 📜 Licenza

| Componente | Licenza |
|-----------|---------|
| `lattice/core/*` | Business Source License 1.1 → Apache 2.0 dopo 4 anni |
| `lattice/prod/*` | Commercial (€59-499/mese per seat) |
| `frontend/*` `backend/*` `deploy/*` | Commercial / proprietary |

Per licenze commerciali, contatti enterprise: **commercial@latticenetwork.it**

---

## 🛡️ Security Disclosure

Security issues: **security@latticenetwork.it**

**Bug bounty** aperto per vulnerabilità che bypassano:
- ML-DSA-65 signature verification
- QBFT quorum validation
- Cross-tenant isolation
- Pulse PQXDH session derivation

Premio: €500–5000 in base alla criticità.

---

## 🤝 Contatti

| Canale | Dettaglio |
|--------|-----------|
| Website | https://latticenetwork.it |
| Email commerciale | sales@latticenetwork.it |
| WhatsApp | +39 351 961 8068 |

---

<div align="center">

**Built in Italy 🇮🇹 with Rust 🦀 · Post-Quantum Ready · Bitcoin-Anchored**

*"L'unica infrastruttura di comunicazione aziendale che resta sicura anche dopo l'arrivo del computer quantistico — perché ogni firma è ML-DSA-65 standardizzata NIST FIPS 204."*

</div>
