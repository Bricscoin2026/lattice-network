# CAPITOLO 12 — NIS2, DORA, GDPR, eIDAS 2.0: la mappa di conformità.

## 12.0 — Apertura

Il quadro normativo europeo sulla sicurezza digitale è cambiato profondamente tra il 2022 e il 2025. Quattro regolamenti — GDPR (già del 2016), eIDAS 2.0 (2024), NIS2 (recepito in Italia con DLgs 138/2024), DORA (in vigore dal gennaio 2025) — costituiscono oggi l'ossatura che ogni azienda con più di 50 dipendenti deve rispettare. La compliance non è più un esercizio formale ma una serie di requisiti tecnici molto specifici.

Questo capitolo non sostituisce un consulente legale. Quello che fa è mappare, in modo operativo, **quali requisiti di queste quattro normative sono soddisfatti by-design da Lattice** e in che modo. Per il responsabile compliance, è una lista di voci che può portare in un audit.

## 12.1 — GDPR (Reg. UE 2016/679 + sentenze Schrems)

Il GDPR resta la pietra angolare. I requisiti rilevanti per la comunicazione aziendale:

**Art. 5 — Principi.** Limitazione di scopo, minimizzazione, integrità e riservatezza. Lattice: cifratura end-to-end (riservatezza), audit log immutabile (integrità), policy di retention configurabili (minimizzazione e limitazione).

**Art. 25 — Privacy by design and default.** Le impostazioni di default devono essere le più protettive. Lattice: tutto è cifrato per default, nessuna opzione "disabilita la cifratura per migliorare le performance", nessuna telemetria opt-out.

**Art. 30 — Registro delle attività di trattamento.** Lattice genera automaticamente il registro delle attività di trattamento per le mail Certify e i messaggi Pulse, con timestamp on-chain.

**Art. 32 — Misure di sicurezza adeguate.** Pseudonimizzazione, cifratura, ridondanza, test periodici. Lattice: tutti questi requisiti sono nativi (cifratura PQC, QBFT-based replication, test di stress documentati).

**Art. 33-34 — Notifica di violazione.** In caso di data breach, l'azienda ha 72 ore per notificare al Garante. Con Lattice, la quantificazione di "quali dati sono stati esposti" è precisa perché ogni accesso è loggato on-chain.

**Schrems II — Trasferimenti extra-UE.** La sentenza CGUE 2020 ha dichiarato incompatibile col GDPR il trasferimento di dati personali verso fornitori cloud soggetti al CLOUD Act USA. Lattice gira on-premise o in cloud sovrano europeo (cap. 6.4) → nessun trasferimento extra-UE → conforme.

## 12.2 — NIS2 (DLgs 138/2024)

NIS2 (Direttiva UE 2022/2555) recepita in Italia il 16 ottobre 2024 estende la cybersecurity regolamentata da 4.000 a oltre 50.000 entità italiane. Requisiti operativi rilevanti:

**Art. 21 — Misure di gestione dei rischi.** Politiche di analisi rischi, gestione incidenti, business continuity, sicurezza della supply chain, sicurezza acquisizione/sviluppo/manutenzione di rete, gestione vulnerabilità, valutazione efficacia, igiene digitale, crittografia, sicurezza personale, autenticazione multifattore, comunicazioni sicure di emergenza. Lattice copre nativamente: crittografia, autenticazione multifattore (via challenge ML-DSA-65), comunicazioni sicure, gestione incidenti (audit log immutabile), business continuity (self-hosted = niente single point of failure esterno).

**Art. 23 — Obblighi di segnalazione incidenti.** 24h per "preallerta", 72h per "notifica iniziale", 1 mese per "relazione finale". Con Lattice, gli incidenti sulla comunicazione aziendale sono ricostruibili in modo deterministico dal ledger → la relazione finale è producible in ore, non settimane.

**Art. 24 — Misure di vigilanza, controllo, sanzioni.** Le sanzioni per non-compliance arrivano fino al 2% del fatturato globale (entità essenziali) o 1.4% (importanti). Lattice è uno degli strumenti che permettono di dimostrare al supervisor di aver adottato "misure appropriate".

**Entità "essenziali" e "importanti".** Banche, sanità, energia, trasporti, infrastrutture digitali, pubblica amministrazione (essenziali). Servizi postali, gestione rifiuti, manifatturiero strategico, fornitori ICT, ricerca (importanti). Tutte queste organizzazioni sono ora soggette a NIS2 — e Lattice è una risposta diretta per gran parte dei loro requisiti di comunicazione.

## 12.3 — DORA (Reg. UE 2022/2554)

Il Digital Operational Resilience Act è in vigore dal 17 gennaio 2025 e si applica al settore finanziario (banche, assicurazioni, intermediari, gestori di mercati, fornitori critici di servizi ICT al finance). Requisiti specifici:

**Art. 5-15 — Quadro di gestione dei rischi ICT.** Governance, identificazione, protezione, rilevamento, risposta, ripristino. Lattice: protezione (cifratura end-to-end), rilevamento (audit on-chain), risposta (revoca crittografica immediata), ripristino (Shamir key recovery).

**Art. 17-23 — Gestione incidenti.** Classificazione, segnalazione, notifica all'autorità competente. DORA introduce categorie di incidente molto specifiche (cyber threat reporting). Lattice fornisce dati strutturati immediatamente esportabili.

**Art. 24-27 — Test di resilienza operativa digitale.** Test annuali obbligatori; ogni 3 anni Threat-Led Penetration Testing (TLPT). Lattice è progettata per essere "auditabile e testabile" — il codice è ispezionabile, le configurazioni sono documentate, i test sono replicabili.

**Art. 28-44 — Rischio della catena di fornitura ICT.** Punto critico di DORA: le entità finanziarie devono mappare e gestire il rischio dei loro fornitori ICT critici. Lattice **riduce drasticamente il numero di fornitori critici esterni** (sostituisce Microsoft 365, Slack, provider PEC, archiviazione documentale).

Per una banca italiana, l'adozione di Lattice è oggi uno dei modi più efficienti di rispondere ai requisiti DORA Art. 28-44.

## 12.4 — eIDAS 2.0 (Reg. UE 910/2014 modificato 2024)

eIDAS 2.0 modernizza il quadro europeo delle identità digitali e dei servizi fiduciari. Punti rilevanti:

**European Digital Identity Wallet (EUDI Wallet).** Ogni cittadino europeo avrà un wallet di identità digitale entro il 2027. Lattice è compatibile con EUDI in fase di lettura (può richiedere attributi al wallet) e in fase di scrittura (può rilasciare certificati di prova firmati ML-DSA-65 — non ancora qualificati eIDAS ma in roadmap per il 2026).

**Recommended Electronic Registered Delivery Service (R-ERDS).** Successore europeo della PEC italiana, con valore legale cross-border. Lattice Certify è progettato per rispettare le specifiche tecniche R-ERDS bozza (ENISA 2024) e sarà certificato come Qualified Trust Service Provider non appena la procedura sarà disponibile.

**Qualified Electronic Signature (QES).** Le firme di Lattice sono "advanced" oggi. Per essere "qualified" servono un processo di certificazione presso AgID/ANSSI/BSI e l'uso di un Qualified Signature Creation Device (QSCD). Lattice si interfaccia con QSCD di terze parti (es. token hardware Aruba, InfoCert) per produrre QES su mail Certify.

## 12.5 — La matrice di compliance

Per riassumere, ecco una matrice operativa che il responsabile compliance può portare in CdA:

| Norma | Requisito | Lattice |
|---|---|---|
| GDPR Art. 5 | Riservatezza, integrità | End-to-end PQC + ledger immutabile |
| GDPR Art. 25 | Privacy by design | Cifratura by default, niente opt-out |
| GDPR Art. 30 | Registro trattamenti | Auto-generato on-chain |
| GDPR Art. 32 | Misure di sicurezza | PQC + replicazione QBFT |
| GDPR Schrems II | No transfer extra-UE | On-prem / cloud sovrano EU |
| NIS2 Art. 21 | Crittografia, MFA, comunicazioni sicure | Native |
| NIS2 Art. 23 | Segnalazione incidenti | Ledger ricostruibile |
| DORA Art. 5-15 | Gestione rischi ICT | Native |
| DORA Art. 17-23 | Gestione incidenti | Audit on-chain |
| DORA Art. 28 | Rischio fornitori critici | Riduzione drastica fornitori |
| eIDAS 2.0 | R-ERDS, QES | Compatible / in roadmap |

## 12.6 — Il punto strategico

C'è una conseguenza non secondaria di questa mappatura: **per molte aziende italiane regolamentate, Lattice non è un costo aggiuntivo ma una scelta che riduce il costo totale di compliance**.

Una banca italiana media, per essere conforme DORA + GDPR + NIS2, deve oggi investire tra 250.000 e 700.000 euro l'anno in consulenza, audit, sistemi di compliance dedicati, e contratti di fornitura specifici. Buona parte di questo costo deriva dal dover gestire la complessità della catena di fornitura ICT (Microsoft + Google + Slack + PEC + archivi + auditor + altro).

Sostituendo gran parte di questa catena con Lattice, il costo di compliance si riduce significativamente (i pochi clienti che hanno completato la migrazione riportano riduzioni del 30-50%). Non perché Lattice "fa magie", ma perché elimina interi grovigli di interdipendenze.

## 12.7 — Domanda per il responsabile compliance

Portate questa domanda al CCO o al DPO: **"Quanto del nostro budget di compliance annuo deriva dalla gestione della catena di fornitura ICT di terzi (audit dei fornitori, contratti specifici, gestione del rischio fornitore)? E quanto si ridurrebbe se sostituissimo la maggior parte di quella catena con un'infrastruttura sovrana?"**

Vi accorgerete che la risposta giustifica spesso, da sola, la migrazione.
