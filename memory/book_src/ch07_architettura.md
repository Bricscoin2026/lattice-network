# CAPITOLO 7 — L'architettura di Lattice Network.

## 7.0 — Apertura

Dopo sei capitoli che hanno raccontato perché esiste un problema e come Lattice lo affronta a livello di business, questo è il primo capitolo che entra nei dettagli tecnici. È pensato per chi vuole capire come funziona davvero la macchina sotto il cofano: CTO, CISO, architetti di sicurezza, sviluppatori, consulenti tecnici. Il lettore non-tecnico può saltare al capitolo 12 senza perdere il filo del discorso.

## 7.1 — La domanda di partenza

Costruire un'infrastruttura di comunicazione aziendale sovrana richiede di soddisfare cinque vincoli simultaneamente, che storicamente sono stati visti come trade-off:

1. **Riservatezza forte** — i contenuti devono restare cifrati end-to-end, leggibili solo dal mittente e dal destinatario.
2. **Identità aziendale verificabile** — chi scrive deve essere riconoscibile in modo crittografico come membro della stessa azienda.
3. **Prova legale opponibile** — ogni mail "ufficiale" deve essere notarizzata in modo verificabile pubblicamente.
4. **Resistenza al futuro** — la crittografia deve essere immune ai computer quantistici (NIST FIPS 203/204).
5. **Operabilità su rete privata** — l'intera infrastruttura deve poter girare offline, on-premise, senza dipendere da servizi esterni.

L'architettura di Lattice è il risultato della scelta di non sacrificare nessuno di questi cinque vincoli. È una scelta che ha aumentato la complessità implementativa, ma che — secondo gli autori — è l'unica onesta dato il problema da risolvere.

## 7.2 — Vista d'insieme

[FIGURA 7.1 — L'architettura a layer di Lattice Network]

Lattice è organizzato in cinque layer logici, ciascuno con responsabilità definite:

**Layer 1 — Storage layer.** Database MongoDB (o equivalente compatibile) con cifratura at-rest AES-256-GCM. Conserva: identità LNS, transazioni del ledger, blocchi finalizzati, mail Certify cifrate, conversazioni Pulse cifrate, audit log.

**Layer 2 — Crypto layer.** Componente Rust (compilato in WebAssembly per il browser e in nativo per il backend) che implementa: ML-DSA-65 (firma post-quantum), ML-KEM-768 (key encapsulation post-quantum), SHA3-512 (hash), AES-256-GCM (cifratura simmetrica), Argon2id (key derivation), Shamir Secret Sharing su GF(256) (key recovery).

**Layer 3 — Ledger layer.** Implementazione tokenless del consenso QBFT (Quorum Byzantine Fault Tolerant), con finalità deterministica entro 1-3 secondi e tolleranza a f<n/3 nodi guasti o malevoli. I blocchi seguono il modello Substrate (extrinsics_root, state_root, weight_used, events). Tutte le transazioni sono firmate ML-DSA-65.

**Layer 4 — Application layer.** FastAPI (Python) come backend HTTP, organizzato in moduli: `lns` (identità), `certify` (mail), `pulse` (chat), `keyrecovery` (recupero chiavi), `explorer` (verifica pubblica), `qbft` (consenso), `tenants` (multi-tenancy).

**Layer 5 — Presentation layer.** Single Page Application React + TailwindCSS. Comunica col backend via REST + Server-Sent Events. Tutta la crittografia sensibile (generazione chiavi, firma, decifratura messaggi) avviene client-side via WASM. Il backend non vede mai chiavi segrete utente.

## 7.3 — Il principio dell'isolamento multi-tenant

Lattice è progettato per supportare **più aziende sulla stessa rete fisica senza che possano vedersi a vicenda**. Questa proprietà — l'isolamento multi-tenant — è critica per due ragioni: (a) permette a Lattice come operatore di rete di servire più clienti su un'infrastruttura condivisa quando appropriato, (b) ma soprattutto, dentro una singola azienda, isola i tenant logici (es. controllata vs capogruppo, azienda vs partner esterno).

L'isolamento è implementato a quattro livelli:

**Isolamento crittografico.** Ogni tenant ha la propria chiave di gateway (`CERTIFY-GATEWAY-{tenant_id}`). Le mail e i messaggi di un tenant sono cifrati con chiavi diverse da quelli di un altro tenant. Anche se l'infrastruttura fisica è condivisa, un tenant non può leggere i dati di un altro perché non possiede le chiavi.

**Isolamento di identità.** Le identità LNS sono organizzate per tenant in modo gerarchico (`mario.acme.lns` vs `paolo.beta.lns`). L'API di Lattice rifiuta richieste cross-tenant a meno che il sovrano-operatore non abbia esplicitamente abilitato un trust link.

**Isolamento di accesso.** I JWT di autenticazione contengono il tenant_id e la role. L'API verifica entrambi prima di restituire qualunque dato. Un utente di acme non può accedere a un endpoint che gli restituirebbe dati di beta, anche manipolando l'URL.

**Isolamento di audit.** Ogni transazione on-chain contiene il tenant_id come metadato. L'Audit Pubblico mostra dati aggregati per tenant senza esporre cross-correlazioni indebite.

## 7.4 — Il flusso di una mail Certify, passo passo

Per rendere concreta l'architettura, vediamo cosa succede quando Mario di Acme invia una mail Certify a Paolo di Beta.

1. **Composizione (browser di Mario).** Mario scrive la mail. Il client React tiene il contenuto in memoria locale.
2. **Recupero chiave destinatario.** Il client di Mario chiede al backend la chiave pubblica ML-KEM-768 di Paolo. Il backend la restituisce insieme alla prova di registrazione on-chain.
3. **Cifratura (browser di Mario).** Il client genera una chiave simmetrica AES-256 effimera, cifra il contenuto, e poi incapsula la chiave AES con la chiave pubblica ML-KEM-768 di Paolo. Solo Paolo, con la sua chiave segreta, potrà decifrare.
4. **Hash e firma (browser di Mario).** Il client calcola SHA3-512 dell'header (mittente, destinatario, oggetto, timestamp, hash_contenuto_cifrato). Firma l'header con la chiave segreta ML-DSA-65 di Mario.
5. **Invio al backend (rete cifrata TLS).** Il client invia: header firmato, contenuto cifrato, firma di Mario. La chiave segreta di Mario non lascia mai il browser.
6. **Verifica del backend.** Il backend verifica la firma di Mario (usando la chiave pubblica registrata on-chain di Mario). Se valida, costruisce una transazione `NotarySeal` che contiene header firmato e hash. Firma a sua volta la transazione con la chiave di gateway di Acme.
7. **Finalizzazione QBFT.** La transazione viene inviata ai validatori QBFT. Quando ricevono 2/3 + 1 dei voti, viene finalizzata in un nuovo blocco entro 1-3 secondi.
8. **Notifica e consegna.** Il backend di Lattice notifica via SSE il client di Paolo. Paolo apre la mail; il suo client decapsula la chiave AES con la sua chiave segreta, decifra il contenuto e firma una `DeliveryReceipt` che testimonia l'apertura.
9. **Notarizzazione della ricevuta.** La DeliveryReceipt viene anch'essa firmata, inviata, validata QBFT e finalizzata.

Risultato: Mario ha una prova crittografica che (a) la mail è stata inviata da lui, (b) è arrivata a Paolo, (c) è stata effettivamente aperta. Tutto verificabile pubblicamente sul Block Explorer.

## 7.5 — Lo stack tecnico in pratica

[FIGURA 7.2 — Lo stack Rust + Python + React di Lattice]

Per i lettori tecnici, ecco lo stack in dettaglio:

**Componenti Rust (crittografia e core):**
- `pqcrypto-dilithium` per ML-DSA-65 (NIST FIPS 204).
- `pqcrypto-kyber` per ML-KEM-768 (NIST FIPS 203).
- `sha3` per SHA3-512.
- `aes-gcm` per AES-256-GCM.
- `argon2` per Argon2id.
- `gf256` (sviluppato internamente) per Shamir Secret Sharing.

Compilato in WebAssembly via `wasm-bindgen` per uso nel browser. Compilato in libreria nativa per uso nel backend Python via `PyO3`.

**Backend Python:**
- FastAPI + Uvicorn (async server).
- Motor (driver MongoDB async).
- PyJWT per i token di sessione.
- `python-multipart` per upload allegati.

**Frontend React:**
- React 19 + Vite.
- TailwindCSS + shadcn/ui.
- Axios per HTTP, EventSource per SSE.
- WebAssembly bindings via `lattice-wasm.js`.

**Storage:**
- MongoDB 7+ (o compatibile come Percona Server for MongoDB).
- Cifratura at-rest a livello di filesystem (LUKS su Linux) o nativa MongoDB Enterprise.

## 7.6 — Le decisioni controverse

Vale la pena spiegare alcune scelte architetturali che sono state oggetto di dibattito interno e che continuano a sollevare domande dai clienti tecnici.

**Perché tokenless.** Lattice non ha una criptovaluta nativa. Le transazioni non hanno gas fees. Questa scelta deriva dall'osservazione che le reti tokenizzate hanno introdotto, nelle blockchain pubbliche, un meccanismo economico necessario per allineare incentivi tra nodi anonimi. In una rete aziendale dove i validatori sono identificati e contrattuali, il token è una complicazione inutile. Tokenless = nessuna esposizione finanziaria, nessuna pressione regolatoria su asset crypto, focus sul valore probatorio.

**Perché QBFT e non PoS.** QBFT (Quorum Byzantine Fault Tolerant) raggiunge finalità deterministica entro pochi secondi con un numero limitato di validatori (tipicamente 4-21). Proof-of-Stake richiederebbe un sistema di staking economico che — di nuovo — è inutile in una rete identificata. QBFT è la scelta giusta per blockchain "permissionata", che è la categoria di Lattice.

**Perché ML-DSA-65 e non SLH-DSA.** Sono entrambi standard NIST post-quantum (FIPS 204 e FIPS 205). ML-DSA-65 ha firme di 3.293 byte, SLH-DSA-Sha2-256s ha firme di 29.792 byte. Per un sistema che firma milioni di transazioni, la dimensione di firma è il vincolo critico. ML-DSA-65 vince per economia di banda e storage senza compromettere la sicurezza.

**Perché Rust per la crittografia.** Sicurezza di memoria garantita a compile-time, performance native, audit open-source disponibili sulle principali librerie post-quantum. Le alternative (Go, C++, Python wrappers) hanno tutte limiti documentati.

## 7.7 — Domanda per il proprio CTO

Se siete un CISO o un dirigente non-tecnico, portate questa domanda al vostro CTO o consulente di sicurezza: **"L'architettura di Lattice, come descritta nel capitolo 7 e nei whitepaper pubblici, soddisfa i nostri requisiti di sicurezza, prestazioni e operabilità? Quali sono le tre cose che ti preoccupano di più?"**

Le risposte del CTO sono il punto di partenza concreto della valutazione. Lattice è disegnato per superare gli scrutini tecnici seri — non per evitarli.
