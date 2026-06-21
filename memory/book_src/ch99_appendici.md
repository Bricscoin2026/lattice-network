# APPENDICI

## APPENDICE A — Glossario tecnico

**AEAD** (Authenticated Encryption with Associated Data) — Modalità di cifratura che combina riservatezza e integrità in una singola operazione. Es: AES-256-GCM, ChaCha20-Poly1305.

**Anchor / Anchoring on-chain** — Operazione di registrare uno hash su una blockchain pubblica (in Lattice: Bitcoin via OpenTimestamps) come prova di esistenza temporale.

**Argon2id** — Algoritmo di derivazione di chiave da password, vincitore della Password Hashing Competition (2015). Resistente sia a attacchi GPU che a side-channel attack.

**Audit log hash-chained** — Registro di operazioni in cui ogni voce contiene lo hash della precedente, in modo che la modifica di una voce invalidi tutta la catena successiva.

**BLS** (Boneh-Lynn-Shacham) — Schema di firma su curve ellittiche che supporta l'aggregazione di firme. Usato in protocolli di consenso come Ethereum 2.0.

**BSL 1.1** (Business Source License) — Licenza software che consente uso non commerciale, ispezione, modifica, ma riserva l'uso commerciale al licenziante. Conversione automatica a Apache 2.0 dopo 4 anni.

**Chaum-Pedersen Σ-protocol** — Famiglia di protocolli interattivi zero-knowledge per provare la conoscenza di un logaritmo discreto. In Lattice usato per ZK-RLN.

**CLOUD Act** — Legge federale statunitense del 2018 che autorizza l'autorità giudiziaria americana a ordinare a operatori statunitensi la consegna di dati ovunque archiviati.

**Double Ratchet** — Protocollo di key derivation per messaggistica E2E, introdotto da Signal nel 2014. Garantisce forward secrecy e post-compromise security.

**DORA** (Digital Operational Resilience Act) — Regolamento UE 2022/2554. In vigore dal gennaio 2025. Definisce requisiti di resilienza ICT per operatori finanziari.

**E2E** (End-to-End) — Modello di cifratura dove solo mittente e destinatario finali possono leggere il contenuto; nessun intermediario, incluso il server, ha accesso.

**eIDAS** (electronic IDentification, Authentication and trust Services) — Regolamento UE 910/2014 (e successive modifiche eIDAS 2.0 del 2024) sui servizi di identità e firma elettronica.

**Envelope encryption** — Tecnica per cifrare i dati con una "data encryption key" che a sua volta è cifrata da una "key encryption key" più protetta.

**Fingerprint** (di una chiave pubblica) — Hash compatto (tipicamente 8-16 byte) di una chiave pubblica, usato per riferimento visivo o verifica.

**Forward Secrecy** — Proprietà per cui la compromissione di una chiave attuale non consente di decifrare comunicazioni passate.

**FIPS** (Federal Information Processing Standards) — Standard pubblicati dal NIST. FIPS 203 = ML-KEM, FIPS 204 = ML-DSA, FIPS 205 = SLH-DSA.

**Groth16** — Sistema di zero-knowledge proof non-interattivo basato su curve a pairing. Produce proof molto piccole (~200 byte) ma richiede setup di parametri pubblici.

**Hash-chain** — Struttura dati lineare dove ogni elemento include lo hash dell'elemento precedente. Rende impossibili modifiche retroattive senza essere rilevate.

**HSM** (Hardware Security Module) — Dispositivo hardware dedicato alla custodia di chiavi crittografiche, con protezioni anti-tamper.

**JWT** (JSON Web Token) — Standard per token di autenticazione firmati, con header, payload e signature in base64.

**KDF** (Key Derivation Function) — Funzione che deriva una chiave crittografica da un materiale segreto (password, master key, shared secret).

**LNS** (Lattice Name System) — Sistema di naming gerarchico usato in Lattice per identità (es: `mario.rossi@dipartimento.tenant.lns`).

**Loopix** — Protocollo accademico (USENIX 2017) per mixnet anonimi moderni con delay-based mixing.

**Master Key** — Chiave crittografica di alto livello da cui derivano (via KDF) altre chiavi operative.

**Merkle tree** — Struttura dati ad albero binario dove ogni nodo interno è lo hash dei figli. Permette prove efficienti di inclusione.

**ML-DSA-65** — Module-Lattice Digital Signature Algorithm, livello 5 (~256-bit security). Standard NIST FIPS 204. Era "Dilithium3".

**ML-KEM-768** — Module-Lattice Key Encapsulation Mechanism, livello 3 (~192-bit security). Standard NIST FIPS 203. Era "Kyber-768".

**MLWE** (Module Learning With Errors) — Problema computazionale alla base di ML-DSA e ML-KEM. Resistente al quantum computing (per quanto si sa oggi).

**NIS2** (Network and Information Security 2) — Direttiva UE 2022/2555. Recepita in Italia con DLgs 138/2024.

**Nullifier** — Valore deterministico ma unilineare derivato da un segreto, usato in ZK-RLN per identificare l'unicità di un'azione senza identificare l'autore.

**OpenTimestamps (OTS)** — Protocollo open source per anchorare hash su blockchain Bitcoin in modo efficiente batch.

**PBFT** (Practical Byzantine Fault Tolerance) — Algoritmo di consenso distribuito (Castro & Liskov, 1999) tollerante a guasti bizantini.

**PEC** (Posta Elettronica Certificata) — Sistema di posta elettronica con valore legale italiano, regolato da DPR 68/2005.

**Perfect Forward Secrecy (PFS)** — Vedi Forward Secrecy.

**Post-Compromise Security (PCS)** — Proprietà per cui, dopo la compromissione di una chiave, le comunicazioni future tornano sicure grazie al re-keying.

**PQC** (Post-Quantum Cryptography) — Crittografia resistente a computer quantistici. Standardizzata da NIST tramite il programma PQCSP iniziato nel 2016.

**PQXDH** (Post-Quantum Extended Diffie-Hellman) — Estensione post-quantistica di X3DH (handshake di Signal), introdotta nel 2023.

**PyO3** — Framework Rust per creare binding Python di codice Rust. Usato in Lattice per il bridge `lattice-py`.

**QBFT** (Quorum Byzantine Fault Tolerance) — Variante di PBFT ottimizzata per scenari enterprise con piccolo numero fisso di validatori.

**RLN** (Rate-Limiting Nullifier) — Schema crittografico per limitare il rate di azioni anonime usando zero-knowledge proofs.

**RTO/RPO** (Recovery Time Objective / Recovery Point Objective) — Metriche di disaster recovery: tempo per ripristinare il servizio / dati massimi persi.

**RSA-2048** — Algoritmo di firma e cifratura a chiave pubblica basato sulla difficoltà di fattorizzare grandi numeri. Vulnerabile a Shor.

**Sealed Sender** — Tecnica di Signal per nascondere l'identità del mittente al server, mantenendola visibile solo al destinatario.

**SHA-3 / SHA3-256 / SHA3-512** — Famiglia di funzioni hash basate su Keccak, standardizzate da NIST FIPS 202 (2015). Diversa struttura interna da SHA-2.

**Shamir Secret Sharing** — Algoritmo per dividere un segreto in N parti tali che K (con K ≤ N) parti siano sufficienti a ricostruirlo, ma K-1 non rivelino nulla.

**Shor's algorithm** — Algoritmo quantistico (Shor, 1994) che risolve fattorizzazione e logaritmo discreto in tempo polinomiale.

**SLH-DSA** (Stateless Hash-Based Digital Signature Algorithm) — Standard FIPS 205, basato solo su hash function. Era "SPHINCS+".

**SPID** (Sistema Pubblico di Identità Digitale) — Sistema italiano di identità digitale, ~38 milioni di utenti registrati.

**TOTP** (Time-based One-Time Password) — Standard RFC 6238 per password monouso basate sul tempo. Usato in Lattice per 2FA.

**WASM** (WebAssembly) — Formato binario per eseguire codice nel browser ad alte prestazioni. Lattice usa WASM per le operazioni client-side ML-DSA-65.

**X3DH / X25519** — Protocollo di handshake di Signal (X3DH) basato su scambio Diffie-Hellman su curva Curve25519 (X25519).

**Zero-Knowledge Proof (ZKP)** — Procedura crittografica per dimostrare la conoscenza di un segreto senza rivelarlo.

## APPENDICE B — Come verificare indipendentemente una ricevuta Certify

Una delle proprietà che distinguono Certify dalla PEC tradizionale è che **la verifica della validità di una ricevuta non richiede alcun software proprietario di Lattice**. Chiunque, in qualsiasi momento — anche tra trent'anni, anche se Lattice non esistesse più — può convincersi della validità di una ricevuta seguendo cinque passi standard.

I cinque passi sono i seguenti.

**Passo 1: ricostruire il payload canonico.** A partire dalle informazioni presenti nel PDF della ricevuta (mail ID, data di seal, mittente, destinatario, hash del documento), si ricostruisce la stringa canonica firmata dal destinatario. Le regole di costruzione sono pubbliche e descritte nell'appendice C.

**Passo 2: calcolare lo hash SHA3-512 del payload canonico.** SHA3-512 è uno standard NIST FIPS 202, pubblicato nel 2015 e implementato in ogni libreria crittografica moderna. Il valore calcolato deve coincidere con quello stampato nel PDF della ricevuta (campo "Preimage hash").

**Passo 3: recuperare la chiave pubblica del firmatario.** La chiave pubblica del destinatario al momento della firma (1.952 byte, formato ML-DSA-65) può essere recuperata da: (a) l'archivio del deployment Lattice di emissione, se ancora disponibile; (b) l'archivio storico di ricerca AgID, se richiesto; (c) il fingerprint stampato nel PDF, che permette di disambiguare la chiave tra più candidate.

**Passo 4: verificare la firma ML-DSA-65 standard NIST FIPS 204.** Usando una qualsiasi implementazione di riferimento dell'algoritmo (la libreria di riferimento del NIST è PQClean, disponibile in C, Rust, Python, JavaScript), si verifica che la firma sia stata effettivamente generata con la chiave privata corrispondente alla pubblica recuperata, applicata al payload canonico ricostruito al passo 1. Se la verifica matematica passa, **la ricevuta è autentica**.

**Passo 5 (opzionale ma raccomandato): verificare l'anchor OpenTimestamps su Bitcoin.** Il PDF della ricevuta contiene un riferimento al blocco QBFT e al successivo anchor OTS sulla blockchain Bitcoin (avviene ogni 6 ore). Questo passo aggiunge una garanzia "perpetua" indipendente da qualsiasi sistema italiano o europeo: chiunque, con qualsiasi nodo Bitcoin del mondo, può verificare che, in un certo momento di un certo giorno, esisteva un blocco QBFT con quel particolare hash di stato. È la prova di esistenza temporale di ultima istanza.

I cinque passi possono essere eseguiti da:

- Un consulente tecnico nominato da un giudice in giudizio civile.
- Un perito grafologo informatico in giudizio penale.
- Un auditor interno dell'organizzazione titolare.
- Un singolo cittadino con conoscenze tecniche di base.

Il punto chiave è che **nessuno di questi attori deve fidarsi di Lattice**, né del fornitore Lattice, né del deployment originario. Si fida solo della matematica e degli standard pubblici (NIST FIPS 202, FIPS 204, OpenTimestamps, Bitcoin protocol).

Per informazioni operative su come eseguire la verifica e link alle librerie di riferimento, contattare l'assistenza Lattice o consultare la documentazione tecnica pubblica.

## APPENDICE C — Specifica del formato della ricevuta PEC court-grade

La ricevuta PDF generata da `GET /api/certify/{mail_id}/receipt.pdf` ha la struttura seguente (formato A4, orientamento verticale, font Helvetica e Helvetica-Bold).

### Header (margine superiore)

- Titolo "LATTICE NETWORK" in Helvetica-Bold 18pt, colore RGB (10, 15, 30).
- Sottotitolo "RICEVUTA DI CONSEGNA · PROVA LEGALE OPPONIBILE" in Helvetica 9pt, colore RGB oro (212, 175, 55).
- Timestamp UTC dell'emissione del PDF in alto a destra.
- Linea di separazione di 1.2pt in colore oro.

### Sezione 1: identificazione della comunicazione

Coppie etichetta/valore:
- `MAIL ID`: identificatore univoco
- `MITTENTE`: LNS completo
- `DESTINATARIO`: LNS completo
- `DATA INVIO`: ISO 8601 UTC
- `CLASSIFICAZIONE`: INTERNAL / CONFIDENTIAL / SECRET
- `OGGETTO`: subject originale (eventualmente redacted secondo policy)
- `HASH DOCUMENTO (SHA3-512)`: prime 96 caratteri esadecimali

### Sezione 2: ricevuta di apertura firmata digitalmente

- `FIRMATA DA (LNS DESTINATARIO)`: LNS del firmatario
- `DATA FIRMA`: ISO 8601 UTC
- `ALGORITMO`: "ML-DSA-65 (NIST FIPS 204 · post-quantum)"
- `PREIMAGE HASH (SHA3-512)`: 128 caratteri esadecimali
- `FIRMA DIGITALE (ML-DSA-65, 3309 byte)`: prime 120 caratteri della firma + ellipsis

### Sezione 3: notarizzazione blockchain

- `TRANSACTION ID`: tx-XXXXXXXXXXXX
- `BLOCK INDEX`: #N
- `CONSENSO`: "QBFT · 4 validatori · 3/4 firme ML-DSA-65"
- `CATENA`: "lattice-sovereign-it-prod"

### Sezione 4: istruzioni di verifica indipendente

Cinque punti di guida testuale per la verifica:
1. Ricostruire il payload canonico.
2. Recuperare la chiave pubblica del destinatario.
3. Verificare la firma ML-DSA-65.
4. Verificare il blocco QBFT.
5. (Opzionale) Verificare l'anchor OpenTimestamps su Bitcoin.

### Footer (margine inferiore)

- Disclaimer legale in 4-5 righe corsivo 7.5pt, colore grigio scuro.
- Riga in oro, Helvetica-Bold 7pt: "LATTICE NETWORK · cybersicurezza sovrana · Contatti".

### Caratteristiche tecniche del PDF

- Conforme a PDF/A-2b per archiviazione di lungo termine.
- Tutti i font incorporati (subsetted).
- Metadati XMP con dichiarazione del software, della versione, dell'algoritmo crittografico.
- Dimensione tipica: 4-8 KB per ricevuta semplice, 15-30 KB con allegati.
- SHA-256 del PDF stesso pubblicato in `/api/certify/{mail_id}/receipt.pdf.sha256`.

## APPENDICE D — Bibliografia

### Standard ufficiali NIST/IETF/ISO

- NIST FIPS 203 — Module-Lattice-Based Key-Encapsulation Mechanism Standard (2024).
- NIST FIPS 204 — Module-Lattice-Based Digital Signature Standard (2024).
- NIST FIPS 205 — Stateless Hash-Based Digital Signature Standard (2024).
- NIST FIPS 202 — SHA-3 Standard (2015).
- NIST SP 800-208 — Recommendation for Stateful Hash-Based Signature Schemes (2020).
- RFC 6238 — TOTP: Time-Based One-Time Password Algorithm (2011).
- RFC 8032 — Edwards-Curve Digital Signature Algorithm (EdDSA) (2017).
- ISO/IEC 27001:2022 — Information security, cybersecurity and privacy protection.
- ISO/IEC 19790:2025 — Cryptographic modules (in pubblicazione).

### Paper accademici fondamentali

- Castryck, W., Decru, T. (2023) — An efficient key recovery attack on SIDH. EUROCRYPT.
- Castro, M., Liskov, B. (1999) — Practical Byzantine Fault Tolerance. OSDI.
- Gidney, C., Ekerå, M. (2021) — How to factor 2048-bit RSA integers in 8 hours using 20 million noisy qubits. Quantum.
- Piotrowska, A., et al. (2017) — The Loopix Anonymity System. USENIX Security.
- Shor, P. (1994) — Algorithms for quantum computation: discrete logarithms and factoring. FOCS.
- Signal Foundation (2023) — PQXDH: Post-Quantum X3DH.

### Normativa europea e italiana

- Regolamento UE 2016/679 (GDPR).
- Direttiva UE 2022/2555 (NIS2).
- Regolamento UE 2022/2554 (DORA).
- Regolamento UE 910/2014 (eIDAS) e successive modifiche 2024/1183 (eIDAS 2.0).
- DLgs 138/2024 (recepimento NIS2 in Italia).
- DLgs 82/2005 (Codice dell'Amministrazione Digitale, CAD).
- DPR 68/2005 (PEC).
- Provvedimenti del Garante Privacy 2022-2025 sull'art. 32 GDPR.

### Risorse pratiche

- PQClean: https://github.com/PQClean/PQClean
- libsodium: https://libsodium.gitbook.io/
- OpenTimestamps: https://opentimestamps.org/
- arkworks (Rust ZK toolkit): https://github.com/arkworks-rs
- Signal Protocol documentation: https://signal.org/docs/

## APPENDICE E — Il Manifesto Lattice

> 12 principi per la sovranità digitale italiana.

1. **La crittografia è un diritto fondamentale.** Tutela il diritto costituzionale alla riservatezza (art. 15) e alla segretezza della corrispondenza.

2. **La sovranità si misura in chi possiede le chiavi.** Non in chi possiede il logo, il dominio, il datacenter. Le chiavi.

3. **Il codice deve essere ispezionabile sempre.** Senza accesso al sorgente, "sicurezza" è solo un atto di fede.

4. **I dati devono restare dove nasce la loro responsabilità.** I dati italiani in Italia. I dati di un'organizzazione, sotto il suo controllo.

5. **Le prove crittografiche devono essere verificabili per trent'anni e oltre.** Non per "il tempo del contratto col vendor".

6. **Nessuno standard è inviolabile: usa solo standard NIST e ISO.** L'innovazione fa progressi, ma gli standard sono il pavimento minimo.

7. **Il vendor lock-in è incompatibile con la sovranità.** Un sistema sovrano deve permettere di andarsene in qualsiasi momento, con tutti i propri dati.

8. **I metadati sono dati, e meritano la stessa protezione.** Chi sa "chi parla con chi" sa molto.

9. **Nessuna terza parte deve poter leggere ciò che non ti appartiene.** Né operatore, né provider, né autorità — senza un mandato giudiziario specifico e proporzionato.

10. **La compliance non è uno scopo — è il pavimento.** È il minimo, non il massimo. La sicurezza vera supera ampiamente i requisiti di compliance.

11. **La velocità di adozione è una vulnerabilità.** Non corriamo per essere primi. Corriamo per essere giusti.

12. **L'autosovranità italiana è la sovranità di domani.** Costruiamola, ingegnere per ingegnere, organizzazione per organizzazione, città per città.

— Lattice Network
