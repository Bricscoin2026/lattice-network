# CAPITOLO 8 — ML-DSA-65 e ML-KEM-768: i nuovi standard NIST.

## 8.0 — Apertura

Questo è il capitolo più tecnico del libro. Spiega gli algoritmi crittografici che proteggono Lattice e perché sono stati scelti tra le decine di candidati che il NIST americano ha valutato per otto anni nel processo di standardizzazione post-quantum (PQC).

Il lettore non tecnico può saltare al capitolo 10 senza perdere il filo. Per chi resta: questo è il capitolo che vi consente di rispondere alla domanda "ma è vero che è sicuro contro i computer quantistici?" con una risposta documentata invece che con una pinna di fede.

## 8.1 — Il problema e perché RSA non basta più

La crittografia che protegge oggi mail, PEC, VPN, HTTPS e firma digitale si basa su due famiglie di problemi matematici: fattorizzazione di numeri grandi (RSA) e logaritmo discreto su curve ellittiche (ECDSA, Ed25519). Entrambi i problemi sono **facili** per un computer quantistico universale di capacità adeguata, perché l'algoritmo di Shor (1994) li risolve in tempo polinomiale.

Il NIST ha stimato che, per rompere RSA-2048 in tempi pratici, serve un computer quantistico con circa 4-6 milioni di qubit fisici (circa 5.000-10.000 qubit logici dopo error correction). IBM ha pubblicato roadmap per 100.000 qubit entro il 2033. La Cina e Google hanno roadmap simili.

Indipendentemente da quando questo accadrà esattamente (vedi cap. 1.4 per la discussione), l'industria ha bisogno di algoritmi che siano sicuri **contro** un futuro computer quantistico. Questi algoritmi sono detti "post-quantum cryptography" (PQC) e si basano su problemi matematici diversi (lattici, hash, codici, isogenie) che — almeno secondo la matematica nota — restano difficili anche per computer quantistici.

## 8.2 — La selezione NIST 2016-2024

Il NIST ha lanciato nel 2016 una competizione aperta per standardizzare algoritmi PQC. Otto anni e tre round di analisi crittoanalitica internazionale dopo, ad agosto 2024, ha pubblicato i primi tre standard:

- **FIPS 203** — Module-Lattice-Based Key-Encapsulation Mechanism Standard (ML-KEM), basato su CRYSTALS-Kyber. Per scambio di chiavi simmetriche.
- **FIPS 204** — Module-Lattice-Based Digital Signature Standard (ML-DSA), basato su CRYSTALS-Dilithium. Per firma digitale.
- **FIPS 205** — Stateless Hash-Based Digital Signature Standard (SLH-DSA), basato su SPHINCS+. Per firma digitale alternativa, hash-based.

Sono in lavorazione altri standard per scenari specifici (firma compatta con FN-DSA, basata su Falcon, prevista 2025-2026; firma hash-based più compatta XMSS in casi specifici).

Lattice ha scelto **ML-DSA-65** (FIPS 204, livello di sicurezza 3) per le firme e **ML-KEM-768** (FIPS 203, livello di sicurezza 3) per lo scambio chiavi. Vediamo perché.

## 8.3 — Perché ML-DSA-65 e non altre opzioni

[FIGURA 8.1 — Confronto algoritmi di firma post-quantum]

ML-DSA è una famiglia con tre livelli di sicurezza:

- **ML-DSA-44** (livello 2, ~AES-128). Public key 1.312 byte, firma 2.420 byte.
- **ML-DSA-65** (livello 3, ~AES-192). Public key 1.952 byte, firma 3.293 byte.
- **ML-DSA-87** (livello 5, ~AES-256). Public key 2.592 byte, firma 4.595 byte.

Il livello 3 (ML-DSA-65) è il compromesso raccomandato dal NIST per la maggior parte delle applicazioni commerciali. La sicurezza è equivalente a AES-192 (più di 128 bit di sicurezza classica + margine generoso per attacchi quantistici futuri). La firma di 3.293 byte è gestibile (rispetto a ML-DSA-87 che è il 40% più grande).

Le alternative considerate e perché sono state scartate:

**SLH-DSA** (FIPS 205) — Firme hash-based con sicurezza dimostrabile basata su funzioni hash. Vantaggio: assunzione di sicurezza molto conservativa (basta che SHA-3 resti sicuro). Svantaggio: firme enormi (29.792 byte per SLH-DSA-Sha2-256s). Per Lattice questo è proibitivo: con milioni di transazioni firmate, lo storage e la banda diventerebbero insostenibili.

**FN-DSA** (basato su Falcon, FIPS in finalizzazione) — Firme molto compatte (~666 byte). Svantaggio: implementazione complessa per evitare side-channel attacks, e in finalizzazione standard, non disponibile per il deployment 2025-2026. Una volta finalizzato e auditato, Lattice valuterà migrazione.

**Schemi ibridi RSA-2048 + ML-DSA-65** — Alcuni fornitori (es. Cloudflare) usano schemi ibridi che firmano due volte (classica e PQ) per essere robusti anche se uno dei due fosse rotto. Lattice ha scelto di NON adottare l'ibrido perché complica l'audit, raddoppia la dimensione delle firme e perché il NIST stesso considera ML-DSA-65 standalone sicuro per il proprio livello.

## 8.4 — Perché ML-KEM-768 e non altre opzioni

ML-KEM (CRYSTALS-Kyber) è il meccanismo di key encapsulation. Serve per scambiare in modo sicuro una chiave simmetrica AES tra due parti che si conoscono solo via chiavi pubbliche.

Livelli disponibili:

- **ML-KEM-512** (livello 1, ~AES-128). PK 800 byte, CT 768 byte.
- **ML-KEM-768** (livello 3, ~AES-192). PK 1.184 byte, CT 1.088 byte.
- **ML-KEM-1024** (livello 5, ~AES-256). PK 1.568 byte, CT 1.568 byte.

Lattice usa ML-KEM-768 per coerenza di livello di sicurezza con ML-DSA-65. Dimensioni accettabili. Performance eccellenti (incapsulamento e decapsulamento sotto il millisecondo su hardware moderno).

## 8.5 — Cosa fa ogni algoritmo in Lattice

**ML-DSA-65** è usato per:
- Firma di transazioni on-chain (NotarySeal, IdentityRegister, IdentityRevoke).
- Firma di blocchi da parte dei validatori QBFT.
- Firma di mail Certify dal mittente.
- Firma delle DeliveryReceipt dal destinatario.
- Firma di richieste e contributi di Key Recovery.
- Firma del gateway aziendale (`CERTIFY-GATEWAY-{tenant_id}`).

**ML-KEM-768** è usato per:
- Incapsulamento di chiavi AES-256-GCM nel canale Pulse (chat end-to-end).
- Incapsulamento di chiavi AES-256-GCM nelle mail Certify per il destinatario.

**SHA3-512** (non PQC, ma quantum-resistant fino a livello di sicurezza Grover, ovvero ~256 bit residui) è usato per:
- Hash di contenuti documento.
- Hash di blocchi (block_hash, prev_hash).
- Merkle root delle transazioni.
- Identificatori di transazione.

**AES-256-GCM** (cifratura simmetrica, quantum-resistant fino a Grover) per:
- Cifratura del contenuto delle mail.
- Cifratura dei messaggi Pulse.
- Cifratura at-rest del database.

**Argon2id** per:
- Derivazione della passphrase admin in chiave di envelope per la cifratura at-rest.

**Shamir Secret Sharing su GF(256)** per:
- Splitting della chiave segreta dei dipendenti in 3 parti, soglia 2-di-3, per il key recovery (vedi cap. 7B).

## 8.6 — Le proprietà di sicurezza che otteniamo

Combinando questi algoritmi, Lattice garantisce:

**Confidenzialità.** Solo mittente e destinatario possono leggere il contenuto. Né Lattice, né l'amministratore del server, né un attaccante che intercetta il traffico hanno accesso al contenuto in chiaro. Vale anche post-Q-Day.

**Integrità.** Il contenuto non può essere modificato senza invalidare la firma. Qualsiasi modifica (anche di un solo bit) viene rilevata.

**Autenticità.** Il mittente è verificabile crittograficamente. Una mail "da Mario" è stata effettivamente firmata con la chiave segreta di Mario.

**Non-ripudio.** Mario non può negare di aver firmato. La firma è non-trasferibile (solo chi possiede la SK può produrla) e verificabile pubblicamente.

**Ora certa.** Il timestamp della finalizzazione QBFT (concordato dai validatori) è verificabile e non manipolabile.

**Resistenza al futuro quantistico.** Tutti gli algoritmi citati sono nei livelli di sicurezza che il NIST e le agenzie nazionali (BSI, ANSSI, NSA) considerano sicuri per dati con vita superiore ai 20 anni, anche assumendo che Q-Day arrivi nei prossimi 10-15 anni.

## 8.7 — La parte onesta — i limiti

Per onestà tecnica, vale la pena nominare i limiti.

**Limite 1 — La crittografia post-quantum è giovane.** Gli algoritmi PQC sono stati analizzati intensamente per 8 anni nel processo NIST, ma sono in produzione mondiale solo dal 2024-2025. Non è impossibile che, in futuro, si scopra una vulnerabilità nuova. Per questo il NIST ha standardizzato due algoritmi di firma (ML-DSA-65 e SLH-DSA) basati su problemi matematici diversi — chi sceglie PQC oggi può, in caso di compromissione di uno dei due, migrare all'altro.

**Limite 2 — Le firme sono grandi.** 3.293 byte per firma, rispetto ai ~64 byte di Ed25519. Per applicazioni con miliardi di firme al secondo (es. Visa), questo è proibitivo. Per applicazioni aziendali (decine di milioni di firme per anno) è gestibile ma richiede consapevolezza nella progettazione di banda e storage.

**Limite 3 — Le implementazioni hanno side-channel.** Tutte le implementazioni di crittografia, post-quantum incluse, possono avere attacchi side-channel (timing, cache, power analysis). Le implementazioni Rust che Lattice usa sono testate contro questi attacchi ma — come tutte le implementazioni — non sono dimostrabilmente perfette. Per scenari militari/classified si raccomanda HSM dedicati con implementazione certificata FIPS 140-3.

## 8.8 — In sintesi per il decisore

Per un CISO che valuta Lattice, le tre cose da portarsi a casa da questo capitolo sono:

1. Lattice usa **gli standard NIST 2024**, gli stessi che la NSA americana e il BSI tedesco impongono per i sistemi classificati. Non sono algoritmi inventati internamente.
2. Lattice è **uno dei pochi prodotti europei** che oggi (febbraio 2026) usa nativamente PQC per tutte le firme e tutti gli scambi chiavi, non solo come "opzione". Per il 99% delle aziende italiane, anche quelle "regolamentate", Lattice è il primo punto di contatto con la PQC reale.
3. La transizione PQC del resto dell'industria è in corso ma richiederà 5-10 anni. Adottare Lattice significa essere **avanti, non in ritardo**. Per dati con vita > 10 anni, è la scelta sensata.
