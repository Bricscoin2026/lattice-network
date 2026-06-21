<div align="center">

# 🦀 Lattice Network

**Sovereign B2B Cybersecurity Ecosystem · Post-Quantum · 100% Self-Hosted**

[![Rust](https://img.shields.io/badge/Rust-9400+_LOC-orange?logo=rust)](#)
[![Axum](https://img.shields.io/badge/Axum-89_endpoints-blue?logo=rust)](#)
[![ML-DSA-65](https://img.shields.io/badge/PQC-ML--DSA--65_NIST_FIPS_204-green)](#)
[![QBFT](https://img.shields.io/badge/Consensus-QBFT_4--validator-purple)](#)
[![Bitcoin](https://img.shields.io/badge/Anchor-OpenTimestamps-yellow?logo=bitcoin)](#)
[![License](https://img.shields.io/badge/License-Proprietary-red)](#)

*Lattice è un'infrastruttura di comunicazione sicura on-premise per aziende e PA italiane —
post-quantum end-to-end, ledger QBFT-finalizzato, mail certificata legalmente opponibile,
chat Signal-style, isolamento tenant by-design.*

</div>

---

## ⚠️ Repository Privato — Software Proprietario

Questo codice è **proprietà privata** e protetto da copyright. La sua presenza su GitHub è esclusivamente per gestione interna di sviluppo. **Non è autorizzato alcun uso, copia, modifica o ridistribuzione** senza accordo scritto.

Per acquistare una licenza Lattice Network, visita il sito ufficiale:
👉 **https://latticenetwork.it**

---

## 🎯 Cosa fa Lattice

| Modulo | Descrizione |
|--------|-------------|
| **Pulse** | Chat E2EE Signal-style con Double-Ratchet PQXDH + sealed sender via mixnet Loopix 3-hop |
| **Certify** | Posta certificata legalmente opponibile (PEC-compat) con receipt PDF firmata ML-DSA-65 e notarizzata on-chain |
| **LNS** | Lattice Name System — identità verificabili sotto dominio aziendale (`alice.acme.lns`) |
| **Tenants** | Multi-tenant isolation by-design, cross-company forbidden by default |
| **Sovereign Console** | Dashboard amministrativa con KPI live: 4 validatori, 9 relay mixnet, blockchain, alerts |
| **OTS Anchor** | Notarizzazione blockchain Lattice → **Bitcoin** via OpenTimestamps (immutable forever) |

---

## 💼 Modello di Licensing

Lattice Network adotta un modello **on-premise una tantum**:

- 💰 **Pagamento singolo** — nessun abbonamento, nessun canone mensile
- 🏢 **Installazione sul server dell'azienda cliente** — il software vive sull'infrastruttura del cliente
- ♾️ **Licenza perpetua** — il cliente possiede il software finché ha la sua infrastruttura
- 🔐 **Sovereignty totale** — nessun dato esce mai dal perimetro del cliente
- 📞 **Aggiornamenti e supporto** disponibili tramite contratto separato

Per dettagli su edizioni disponibili (Professional / Banking / Enterprise) e configurazioni server, visita **https://latticenetwork.it**.

---

## 🔐 Post-Quantum Cryptography

Ogni firma è eseguita in **Rust nativo** tramite `pqcrypto-mldsa 0.1`, nessun PyO3, nessun fallback.

| Primitivo | Standard | Uso |
|-----------|----------|-----|
| **ML-DSA-65** | NIST FIPS 204 (ex-Dilithium3) | Firme on-chain · receipt PEC |
| **ML-KEM-768** | NIST FIPS 203 (ex-Kyber-768) | PQXDH handshake Pulse |
| **AES-256-GCM** | NIST SP 800-38D | AEAD payload Pulse · envelope at-rest |
| **SHA3-512** | NIST FIPS 202 | Audit chain · canonical preimage |
| **Poseidon** | Starknet Felt prime | ZK-RLN nullifier (anti-spam) |

---

## ⚖️ Consensus · Byzantine Fault Tolerance

- **QBFT** (Quorum Byzantine Fault Tolerance) — 4 validatori indipendenti, quorum `2f+1 = 3/4`
- Ogni block è firmato **ML-DSA-65** da almeno 3 validatori
- Ogni transazione critica (LNS register, Tenant register, Pulse anchor, Certify send, OTS pin) genera un block
- Anchor on-chain ogni 3 messaggi Pulse, ogni mail Certify, ogni receipt firmata
- I 4 binari validator sono in `/lattice/prod/qbft-validator` — 100% Rust standalone

---

## 🟧 Bitcoin Anchoring (OpenTimestamps)

Ogni block Lattice finalizzato è ancorato a **Bitcoin** via OTS:

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
   + Bitcoin mempool bundling ~3h
   + Final btc_attested=true tag 0588960d73d71901
```

---

## 📊 Metriche Codebase

| Metrica | Valore |
|---------|--------|
| **Rust LOC (sorgente, escluso build artifacts)** | **9,398** |
| **Endpoint Rust nativi** | **89** |
| **Validators QBFT live** | 4/4 ONLINE |
| **Mixnet relays Loopix** | 9 (3 layer × 3 relay) |
| **Audit chain entries verified** | 1182 byte-perfect |

---

## 📂 Struttura

```
lattice-network/
├── lattice/                       Cargo workspace (Rust)
│   ├── core/lattice-crypto/       ML-DSA-65 · ML-KEM-768 · SHA3
│   ├── core/lattice-node/         QBFT consensus primitives
│   ├── core/pulse-protocol/       AES-256-GCM sealed sender
│   ├── core/pulse-ratchet/        PQXDH + Double Ratchet
│   ├── core/lattice-zk-rln/       rate-limit ZK Poseidon
│   ├── core/lattice-mixnet/       Loopix mixnet relay
│   ├── prod/lattice-gateway/      Axum API server (89 endpoints)
│   ├── prod/qbft-validator/       Standalone validator binary
│   └── prod/mixnet-relay/         Standalone mixnet relay
├── backend/                       Python FastAPI (proxy + legacy)
├── frontend/                      React SPA (Vite + Shadcn UI)
├── deploy/                        nginx config + deploy script
└── memory/                        Documentazione interna
```

---

## 🛡️ Sicurezza

Lattice Network è progettato secondo il principio **Zero Trust + Sovereignty**:

- Tutte le firme digitali sono post-quantum (ML-DSA-65 NIST FIPS 204)
- Nessun dato sensibile lascia mai il server del cliente
- Audit chain SHA3-512 immutabile + ancoraggio Bitcoin
- Cross-tenant isolation enforced a livello applicativo

Per segnalazioni di sicurezza, contatta tramite il sito ufficiale **https://latticenetwork.it**.

---

<div align="center">

**Built in Italy 🇮🇹 with Rust 🦀 · Post-Quantum Ready · Bitcoin-Anchored**

© 2026 — All rights reserved. Software proprietario.

</div>
