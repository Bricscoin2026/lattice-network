# Lattice Network — Sovereign Communications Platform

**Crittografia post-quantum on-premise per aziende che non vogliono dipendere da nessuno.**

---

## Cos'è

Lattice è una piattaforma di comunicazione sovrana che gira **sui tuoi server**. Nessun cloud americano, nessun fornitore terzo, nessuna azienda esterna che custodisce i tuoi dati.

- 📧 **Certify** — PEC interna firmata ML-DSA-65 (post-quantum FIPS 204) con cifratura end-to-end X25519
- 💬 **Pulse** — Chat aziendale stile WhatsApp con firma PQC e ricevute on-chain
- 🔐 **Le chiavi private non lasciano mai i browser dei dipendenti**
- ⛓️ **Notarizzazione QBFT** — 4 validatori in consenso bizantino su ogni evento legale
- 🛡️ **AES-256-GCM at-rest** — Anche chi ruba il DB vede solo blob cifrati

---

## Requisiti hardware (single server)

| Tier | vCPU | RAM | Disco | Esempio (€/mese) | Capacità |
|---|---|---|---|---|---|
| **Starter** | 2 | 4 GB | 40 GB | Hetzner CX22 — €5 | 1 tenant, ~50 utenti |
| **Pro** | 4 | 8 GB | 80 GB | Hetzner CCX13 — €20 | 5 tenant, ~500 utenti |
| **Enterprise** | 8 | 16 GB | 200 GB | OVH Advance — €50 | Multi-tenant, ~5000 utenti |

**Software**: Ubuntu 22.04 LTS · Docker 24+ · Docker Compose v2

---

## Installazione in 4 comandi

```bash
# 1) SSH al tuo server
ssh root@TUO_SERVER

# 2) Installa Docker se non c'è
curl -fsSL https://get.docker.com | sh && apt install -y docker-compose-plugin git

# 3) Clona Lattice
git clone https://github.com/<TUO_USER>/lattice-network.git /opt/lattice

# 4) Esegui l'installer guidato
cd /opt/lattice && bash deploy/installa.sh
```

Lo script `installa.sh` ti chiede via prompt:
- Dominio principale (es. `lattice.tuaazienda.it`)
- Dominio API (es. `api.lattice.tuaazienda.it`)
- Email Platform Operator
- Genera automaticamente tutti i secret crittografici
- Avvia i container e fa il bootstrap del tuo account

Tempo totale: **~15 minuti** (di cui 10 sono build Rust+WASM).

---

## Cosa contiene il repository

```
/app/
├── backend/          # FastAPI + 4 validatori QBFT + 3 relay Mixnet
├── frontend/         # React + WASM ML-DSA-65 client-side
├── lattice/          # Rust workspace (lattice-crypto, lattice-wasm, lattice-py)
└── deploy/
    ├── Dockerfile.backend       # Multi-stage Rust → Python
    ├── Dockerfile.frontend      # React build → Nginx
    ├── docker-compose.yml       # 5 servizi: mongo, backend, frontend, backup, tunnel
    ├── .env.production.example  # Template con tutte le variabili
    ├── installa.sh              # Installer guidato
    ├── README.md                # Guida deploy passo-passo
    └── supervisor.conf          # Config processi backend
```

---

## Sicurezza in 1 minuto

| Area | Implementazione |
|---|---|
| **Firma documenti** | ML-DSA-65 (FIPS 204) client-side via WebAssembly |
| **Cifratura PEC** | End-to-end X25519 + AES-256-GCM (server non vede il body) |
| **Cifratura chat** | AES-256-GCM con anchor on-chain |
| **Database at-rest** | Envelope AES-256-GCM (master key in `.env`) |
| **Backup** | mongodump + GPG AES-256 symmetric, nightly cron |
| **Auth** | Challenge-response ML-DSA-65 + JWT con revocation list + 2FA TOTP opzionale |
| **Rate limit** | Per-IP sliding window (lead 5/min, auth 10-20/min) |
| **Body cap** | 25 MB globale (DoS protection) |
| **Audit log** | Append-only con SHA3-512 hash chain (`/api/audit/verify`) |
| **Headers** | HSTS preload, CSP strict, X-Frame DENY, X-Content nosniff |

---

## Modello licenza

Il software è **commerciale**. La licenza d'uso permette:
- Installazione su un numero illimitato di server **della tua azienda**
- Modifica del codice per uso interno
- NON permette: rivendita, sublicenza, distribuzione a terzi

Per uso multi-tenant (più aziende clienti sulla stessa istanza) è richiesta licenza **Enterprise**.

Per dettagli: contatta `<CONTATTO_VENDITE>`.

---

## Supporto

| Pacchetto | Cosa include | Costo |
|---|---|---|
| **Community** | Issue su GitHub, documentazione, best effort | Gratuito con la licenza |
| **Business** | Email entro 24h lavorative, fix critici | €200/mese |
| **Enterprise** | SLA 4h, telefono diretto, hotfix prioritari | Custom |

---

## FAQ veloce

**Q: Devo aprire porte sul firewall?**
A: No. Usiamo Cloudflare Tunnel — connessione outbound dal server, zero porte aperte.

**Q: Cosa succede se perdo il `.keypair.json` del Platform Operator?**
A: Hai il **recovery code** stampato al primo bootstrap (carta, password manager). Lo usi per rotare la chiave e ne ottieni una nuova. Se perdi ANCHE il recovery code: irrecuperabile (è il design — nessun backdoor).

**Q: I dati dei miei clienti finiscono mai su un cloud americano?**
A: **No.** Cloudflare Tunnel trasporta byte cifrati TLS, ma il contenuto delle PEC è già cifrato end-to-end PRIMA di entrare nel tunnel. Cloudflare vede solo bytes opachi.

**Q: Posso esportare tutto e migrare altrove?**
A: Sì. `mongodump` + cartella `attachments/` + le keypair dei tuoi dipendenti. Lattice è open-format.

**Q: Funziona senza connessione internet?**
A: Sì in LAN aziendale. Senza internet non funzionano Cloudflare Tunnel e Pages — devi self-host anche il proxy (nginx + Let's Encrypt locale).

---

**Lattice Network** — `Sovereign Communications` — *quando i tuoi dati sono solo tuoi.*
