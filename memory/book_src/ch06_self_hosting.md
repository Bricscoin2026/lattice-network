# CAPITOLO 6 — Self-hosting e on-premise come scelta strategica.

## 6.0 — Apertura

Negli anni 2010 il consenso del settore IT era: "il cloud è meglio per tutto". Il self-hosting era diventato sinonimo di arretratezza tecnologica. Server fisici in azienda, amministrati da un team interno, erano percepiti come una soluzione del passato.

Quel consenso è cambiato a partire dal 2022. La combinazione di crescita dei costi cloud, normativa europea sulla data sovereignty (GDPR + NIS2 + DORA + AI Act), sospensioni di account da parte di hyperscaler e maturità degli strumenti open-source ha riportato il self-hosting al centro del dibattito IT — non come scelta nostalgica, ma come scelta strategica per workload specifici.

Questo capitolo ragiona sul perché il self-hosting (o, in alternativa, l'hosting in cloud sovrano europeo selezionato dal cliente) è la scelta giusta per la comunicazione aziendale ad alto valore, e sui contro-argomenti che vengono tipicamente sollevati.

## 6.1 — Cosa intendiamo per "self-hosting"

Per chiarezza, distinguiamo due modelli:

**Self-hosting puro (on-premise).** I server fisici sono nel datacenter dell'azienda o in un suo locale dedicato. L'azienda li acquista, li amministra, li sostituisce. La connettività e l'alimentazione sono garantite dall'azienda.

**Hosting in cloud sovrano selezionato (private cloud).** I server fisici sono in un datacenter di un fornitore europeo scelto dall'azienda (OVH, Hetzner, Aruba, Seeweb, Scaleway, IRIDEOS, partner regionali). L'azienda non possiede l'hardware, ma sceglie il fornitore, audita il contratto, e ha facoltà di portabilità completa.

Per il discorso di questo libro entrambi i modelli sono accettabili, perché entrambi soddisfano le sei dimensioni della sovranità del capitolo 4. Il primo (on-premise) ha sovranità leggermente più forte; il secondo (cloud sovrano selezionato) ha costi operativi inferiori. Per la maggior parte delle PMI italiane, il cloud sovrano selezionato è il punto di equilibrio ragionevole.

## 6.2 — I cinque vantaggi del self-hosting per la comunicazione

**Vantaggio 1 — Continuità.** Nessun fornitore può sospendere il servizio. L'unica autorità che può imporre uno spegnimento è la magistratura italiana o europea, con procedimento documentato. Il rischio di sospensione "amministrativa" o "automatica" è eliminato.

**Vantaggio 2 — Riservatezza tecnica.** I dati sono fisicamente nei server della tua azienda (o del cloud sovrano che tu hai scelto). Nessun fornitore extra-UE ha accesso tecnico. Le richieste di consegna di dati da parte di autorità estere non sono soddisfacibili perché Lattice come azienda non ha accesso ai dati dei clienti.

**Vantaggio 3 — Costo prevedibile.** I costi del cloud pubblico crescono in modo non sempre lineare al business (storage, bandwidth, computation, API calls). Il self-hosting ha costi fissi (hardware, manutenzione, energia, banda) che possono essere previsti con accuratezza per 3-5 anni. Per aziende sopra i 200 dipendenti, il TCO del self-hosting per la sola comunicazione è inferiore a quello di Microsoft 365 nell'80% dei casi che abbiamo analizzato.

**Vantaggio 4 — Audit indipendente.** Tu puoi auditare l'infrastruttura, il codice, le configurazioni. Puoi pubblicare il risultato dell'audit (come fanno alcune banche) per rafforzare la fiducia dei clienti. Il fornitore cloud non ti offre questa trasparenza, perché il suo modello di business è proprio la non-ispezione.

**Vantaggio 5 — Personalizzazione.** Lattice si integra con i tuoi sistemi esistenti (Active Directory, gestionale, ERP) in modo nativo. Le policy di archiviazione, retention, classificazione le decidi tu. Nessun "click-through agreement" con un fornitore esterno.

## 6.3 — I quattro contro-argomenti tipici (e perché non reggono più)

**Contro-argomento 1 — "Non abbiamo competenze interne".** Era vero quando l'on-premise voleva dire installare e amministrare un server Exchange con migliaia di parametri. Oggi Lattice (e piattaforme moderne in generale) si installa via container Docker o appliance virtuale. Il setup iniziale richiede una settimana di un partner di Lattice. La manutenzione ordinaria richiede meno di 4 ore al mese di un sysadmin senior. Per un'azienda sopra i 50 dipendenti il costo equivalente di un consulente esterno specializzato è inferiore al costo della licenza Microsoft 365 Business Premium per gli stessi utenti.

**Contro-argomento 2 — "Non possiamo permetterci l'hardware".** L'hardware necessario per ospitare Lattice per un'azienda di 50-200 dipendenti è modesto: 2 server fisici (per ridondanza) con 32 GB di RAM, 1 TB di storage NVMe ciascuno. Costo totale: tra i 4.000 e gli 8.000 euro una tantum, ammortizzati su 5 anni. Per 1.000 dipendenti, l'investimento sale a 30.000-50.000 euro. Confrontato con il costo annuale di Microsoft 365 per quel numero di utenti (oltre 100.000 euro/anno), l'hardware si ammortizza in pochi mesi.

**Contro-argomento 3 — "Non abbiamo continuità operativa H24".** I provider di cloud pubblico hanno SLA del 99.9% (~8 ore di downtime all'anno) o 99.95%. Lattice, configurato con ridondanza standard, raggiunge SLA del 99.95% con architettura interna o del 99.99% con cloud sovrano di seconda generazione. La differenza in pratica è negligibile, e l'overhead di gestione è meno di quello che si pensa.

**Contro-argomento 4 — "Il cloud è il futuro, non vogliamo andare contro tendenza".** Il cloud per scalabilità globale è il futuro. Il cloud per dati strategici aziendali sta perdendo terreno in tutta Europa proprio mentre scriviamo. Banche tedesche, francesi e olandesi stanno tornando a infrastrutture sovrane per le comunicazioni regolamentate. Le linee guida BSI, ANSSI, ENISA del 2024-2025 spingono verso la sovranità tecnica reale. L'Italia, in ritardo come al solito sulle tendenze regolatorie, arriverà su queste posizioni entro il 2027.

## 6.4 — Quando Lattice gira nel cloud sovrano

Per le aziende che non vogliono gestire hardware fisico, Lattice è installabile nei seguenti provider di cloud sovrano europeo che abbiamo testato e con cui abbiamo partnership documentate:

- **OVHcloud** (Francia, Italia, Germania) — Bare metal o cloud pubblico, ISO 27001 + SecNumCloud (qualificazione ANSSI).
- **Hetzner** (Germania) — Bare metal economico, datacenter in DE/FI.
- **Aruba** (Italia) — Datacenter italiani, certificazione ACN per PA.
- **Seeweb** (Italia, gruppo Hosting Solutions) — Italia, ISO 27001/27017/27018.
- **Scaleway** (Francia, gruppo Iliad) — Datacenter europei, focus sviluppatori.

Tutti i provider citati hanno clausole contrattuali standard che escludono il trasferimento dati extra-UE e che garantiscono la portabilità (export completo, niente lock-in di formato). Le configurazioni reference che pubblichiamo sono testate su questi cinque provider.

Importante: Lattice **non** raccomanda — e tecnicamente non supporta — il deployment su Azure, AWS, Google Cloud o altri hyperscaler americani, anche nelle loro "regioni sovrane". Sarebbe contraddire la promessa del prodotto.

## 6.5 — La transizione concreta

Migrare a Lattice non significa "spegnere Microsoft 365 lunedì". Significa pianificare una transizione progressiva, tipicamente in tre fasi.

**Fase 1 — Comunicazioni ad alto valore (3-6 mesi).** Si migra a Lattice ciò che ha più valore strategico o probatorio: comunicazioni del consiglio, M&A, contenziosi in corso, brevetti, segreti industriali. Il resto rimane su Microsoft 365.

**Fase 2 — Comunicazioni operative medie (6-12 mesi).** Si migra la corrispondenza con clienti chiave, la chat di reparto, le decisioni operative dei comitati. Microsoft 365 viene confinato a comunicazioni "leggere" o esterne non strategiche.

**Fase 3 — Cleanup finale (12-24 mesi).** Tipicamente, la maggior parte delle aziende che ha completato la fase 2 sceglie di lasciare Microsoft 365 solo come "mail marketing / mail leggera / collegamenti col mondo extra". Il volume effettivo passa per il 70-90% su Lattice. Il costo della licenza Microsoft scala di conseguenza (passa da Business Premium a Exchange Online Plan 1 per i restanti utenti).

Questo modello "ibrido controllato" è quello che la maggior parte dei clienti enterprise di Lattice adotta. È pragmatico, ha rischi gestibili, e produce ROI misurabile sin dalla fase 1.

## 6.6 — Domanda per la prossima riunione

Portate questa domanda al CdA: **"Quale percentuale del nostro fatturato dipende, oggi, da una mail o da una chat che gira su infrastruttura non controllata da noi? E in fase 1 di una migrazione, qual è il primo 10% di comunicazione che vorremmo mettere al sicuro?"**

Se ne discutete in modo concreto, vi accorgerete che la migrazione non è un salto nel vuoto. È una scelta razionale di quale rischio è prioritario.
