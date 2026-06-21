# CAPITOLO 14 — Roadmap dell'autosovranità.

## 14.0 — Apertura

Abbiamo raccontato il problema (parti I), la sovranità come categoria operativa (parte II), Lattice come risposta tecnica (parte III), il quadro normativo e i casi d'uso (parte IV). Questo capitolo finale è il più pragmatico di tutti: indica i passi concreti per costruire l'autosovranità delle comunicazioni nei prossimi 18 mesi, indipendentemente da Lattice come prodotto specifico.

Anche se sceglieste un'altra strada (un'altra piattaforma sovrana, un mix di soluzioni, una soluzione interna), la sequenza di pensiero sarebbe la stessa. Quella che segue è una roadmap operativa applicabile a qualunque azienda italiana sopra i 30 dipendenti.

## 14.1 — Mese 0: l'inventario

Prima di decidere qualunque cosa, occorre sapere dove si è oggi. Un inventario delle comunicazioni aziendali in genere richiede 2-4 settimane di lavoro di un comitato ristretto (IT manager + responsabile compliance + un rappresentante del legale).

Domande dell'inventario:

1. **Quali fornitori cloud gestiscono nostre comunicazioni?** (Microsoft, Google, Slack, PEC, Dropbox, WhatsApp Business, altri).
2. **In quali datacenter sono fisicamente i dati?**
3. **Quante mail aziendali al giorno?** (totali e per tipologia di valore).
4. **Quante chat aziendali al giorno?**
5. **Quali tipi di comunicazioni hanno valore probatorio o strategico?**
6. **Quali contratti di fornitura ICT sono in essere, con quali clausole di terminazione, con quali penali?**
7. **Quante volte negli ultimi 24 mesi abbiamo avuto problemi con il fornitore primario?**
8. **Qual è il danno operativo stimato di una sospensione del fornitore primario per 24, 72, 168 ore?**

L'output dell'inventario è un documento di 10-20 pagine che il CdA può discutere. Senza di esso, le decisioni successive si prendono nel buio.

## 14.2 — Mese 1-2: la priorità strategica

Dato l'inventario, occorre identificare il 10-30% di comunicazioni che merita un trattamento sovrano. Sono tipicamente:

- Comunicazioni del consiglio.
- Trattative M&A in corso o prevedibili.
- Contenziosi attivi e potenziali.
- Brevetti e segreti industriali.
- Comunicazioni con organi di vigilanza (per banche, assicurazioni, sanità).
- Comunicazioni con clienti chiave (i top 10 per fatturato o sensibilità).
- Decisioni HR delicate (sanzioni, licenziamenti, casi disciplinari).

Per ogni categoria identificata, valutare: chi parla con chi, quanti messaggi al mese, quanto sopravvivono i dati (vita utile), qual è il costo di una compromissione.

L'output è una matrice "categoria di comunicazione × livello di criticità", che diventa input della scelta tecnologica del mese 3.

## 14.3 — Mese 3: la scelta tecnologica

A questo punto si confrontano le opzioni. Le principali, oggi (febbraio 2026):

**Opzione 1 — Continuare con Microsoft/Google + sovereign cloud option.** Costo: relativamente basso. Beneficio di sovranità: minimo (capitolo 5). Tempo di implementazione: rapido.

**Opzione 2 — Costruire infrastruttura interna ad hoc.** Costo: alto (250-800k a seconda della dimensione). Beneficio di sovranità: massimo, ma a rischio di realizzazione. Tempo: 12-24 mesi.

**Opzione 3 — Adottare Lattice (o un equivalente sovrano europeo).** Costo: medio (50-400k investimento iniziale a seconda della dimensione). Beneficio di sovranità: alto e dimostrato. Tempo: 3-6 mesi.

**Opzione 4 — Ibrida: Microsoft/Google per comunicazioni leggere + Lattice per quelle critiche.** Costo: medio. Beneficio: equilibrio pragmatico. Tempo: 3-6 mesi.

Per la stragrande maggioranza delle aziende italiane, l'opzione 4 è la raccomandazione: massimizza il valore sovrano dove conta, minimizza la disruption sul resto.

## 14.4 — Mese 3-4: l'installazione

Una volta scelta la tecnologia, l'installazione segue uno schema standard:

**Settimana 1.** Setup dell'infrastruttura (server fisici o cloud sovrano). Configurazione di rete. Backup. Sicurezza perimetrale.

**Settimana 2.** Installazione del software (Lattice o equivalente). Test interni. Configurazione delle policy aziendali.

**Settimana 3.** Generazione delle prime identità (founder + key admin). Setup del Key Recovery (Shamir 2-di-3 con guardiani designati). Test di recupero.

**Settimana 4.** Onboarding dei primi utenti pilota (10-30 persone, tipicamente il team strategico). Training. Validazione.

Per aziende che hanno scelto cloud sovrano selezionato, la settimana 1 può essere ridotta a 2-3 giorni. Per chi installa on-premise da zero, può estendersi a 2 settimane.

## 14.5 — Mese 5-9: l'estensione

Una volta che il pilota è stabile, l'estensione segue il pattern "ondate progressive":

**Ondata 1 (mese 5).** Estensione al primo reparto completo (es. legale + compliance + finanza). Tipicamente 20-50 persone aggiunte.

**Ondata 2 (mese 6-7).** Estensione al secondo reparto strategico (es. commerciale o R&D). Altre 30-100 persone.

**Ondata 3 (mese 8-9).** Estensione al resto dell'organizzazione (il "lungo coda" di reparti minori e personale operativo).

In parallelo: progressiva riduzione della licenza Microsoft 365 (da Business Premium a Plan 1), eliminazione di Slack e Dropbox per le comunicazioni interne, mantenimento di PEC solo per comunicazioni con PA italiane che la richiedono per legge.

## 14.6 — Mese 10-12: la stabilizzazione

L'ultimo trimestre del primo anno è dedicato alla stabilizzazione operativa:

- Audit interno completo dell'infrastruttura Lattice.
- Verifica delle policy di backup e disaster recovery.
- Esercitazione di emergenza (es. sospensione simulata del fornitore primario residuo, verifica della continuità Lattice).
- Documentazione di compliance per NIS2/DORA/GDPR.
- Eventuale audit esterno indipendente (consulenza ISO 27001 o equivalente).

Al termine del mese 12, l'azienda è in una posizione di sovranità sostanziale per la maggior parte delle sue comunicazioni critiche.

## 14.7 — Anno 2 e oltre: gli sviluppi naturali

Una volta che la sovranità delle comunicazioni è stata stabilita, emergono naturalmente sviluppi correlati:

**Identità sovrana dell'azienda.** L'azienda inizia a usare le proprie identità LNS come "carta di identità digitale aziendale" per: portali clienti, autenticazione su sistemi terzi (via SAML/OIDC), firma di documenti, accessi fisici (badge).

**Archivio sovrano dei documenti.** Oltre alle mail e alle chat, l'azienda sposta su Lattice (o su un sistema integrato) anche l'archivio dei documenti firmati, brevetti, contratti.

**Comunicazione cross-aziendale sovrana.** Con il diffondersi di Lattice (e di sistemi compatibili), le aziende iniziano a comunicare tra loro sovranamente. Questo è il punto di svolta: la sovranità non è più solo "interna" ma diventa un'infrastruttura B2B.

**EUDI Wallet integration.** L'arrivo dell'European Digital Identity Wallet entro il 2027 si integra naturalmente con Lattice: i cittadini possono identificarsi verso le aziende via EUDI, le aziende rispondono via Lattice.

## 14.8 — Il senso ultimo

Il senso ultimo di questa roadmap non è "passare a Lattice". È **riprendere in mano il controllo della propria infrastruttura di comunicazione**. Lattice è una delle risposte operative possibili al 2026 — quella più completa, secondo gli autori. Ma il problema, e la necessità di rispondervi, restano indipendentemente dal prodotto scelto.

Un consiglio di amministrazione che, alla fine di un anno fiscale, può dire "abbiamo riportato sotto controllo le nostre comunicazioni più importanti" ha fatto una cosa che pochissimi CdA italiani potranno dire nei prossimi 24 mesi. È una differenza che, in caso di crisi, si misura in milioni di euro non persi, in cause non perdute, in reputazioni protette.

## 14.9 — Domanda finale

Portate al prossimo consiglio questa domanda, l'unica importante: **"Quanto tempo possiamo ancora permetterci di affidare le nostre comunicazioni più importanti a fornitori che possono sospenderle senza preavviso, leggerle senza autorizzazione e modificarne il valore probatorio retroattivamente?"**

Se la risposta è "non molto", il momento di partire è adesso. La roadmap che avete appena letto è di 12 mesi. Inizia oggi.

Buon viaggio.

— *Gli autori, Milano, febbraio 2026*
