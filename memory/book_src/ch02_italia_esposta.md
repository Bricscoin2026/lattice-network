# CAPITOLO 2 — Perché l'Italia è esposta più di chiunque altro.

## 2.0 — Apertura

L'Italia ha tre caratteristiche che, combinate, la rendono il paese europeo più esposto al problema descritto nel capitolo precedente. Non per cattiva volontà, non per superficialità. Per una somma di fatti strutturali che vale la pena guardare insieme, perché nessuno di essi, da solo, sarebbe decisivo. Combinati, sì.

**Primo**: l'Italia ha un tessuto produttivo fatto al 95% da piccole e medie imprese sotto i 250 dipendenti. Queste imprese, statisticamente, non hanno un CISO interno e non hanno mai gestito una migrazione di infrastruttura critica. Quando hanno scelto Microsoft 365 dieci anni fa, lo hanno fatto seguendo un consulente IT esterno che proponeva ciò che era già pronto.

**Secondo**: l'Italia ha la PEC, che è uno strumento storicamente unico, ma — come abbiamo visto nel capitolo 1 — ha quattro limiti strutturali (vale solo in Italia, non garantisce il contenuto, dipende dal provider, espone i contenuti). Il dibattito pubblico tratta la PEC come "soluzione", quando è in realtà un mezzo strumento. Questo crea un'illusione di sicurezza che ritarda l'adozione di strumenti più seri.

**Terzo**: il mercato della cybersecurity italiano è dominato da rivenditori di prodotti americani e israeliani. Pochissime aziende italiane sviluppano prodotti propri. Quando un CISO italiano fa una RFP per una piattaforma di comunicazione aziendale sicura, la lista dei fornitori è quasi sempre la stessa: Microsoft, Google, Cisco, Mimecast, Proofpoint. Tutte aziende extra-UE.

## 2.1 — Le sei dipendenze materiali

Mettiamo in fila, in modo asciutto, dove sono concretamente le mail e le comunicazioni delle imprese italiane oggi.

**Dipendenza 1 — Microsoft 365.** Oltre il 70% delle imprese italiane sopra i 20 dipendenti usa Microsoft 365 come piattaforma mail principale. Il datacenter primario è in Irlanda (West Europe) e Olanda (North Europe), con repliche negli Stati Uniti. I dati sono soggetti al CLOUD Act statunitense. Il contratto è il Microsoft Services Agreement, modificabile unilateralmente da Microsoft con preavviso variabile.

**Dipendenza 2 — Google Workspace.** Circa il 18% delle imprese italiane sopra i 20 dipendenti. Stessa logica: datacenter in Belgio e Olanda, replicati negli USA. Stessa esposizione al CLOUD Act. Stesso modello contrattuale unilaterale.

**Dipendenza 3 — Provider PEC italiani.** Aruba, InfoCert, Namirial concentrano oltre il 90% del mercato PEC italiano. Sono soggetti privati, regolati da AgID, ma — come abbiamo visto — espongono il contenuto in chiaro per 30 mesi e vivono e muoiono con il provider stesso. Aruba ha avuto interruzioni significative di servizio negli ultimi tre anni; InfoCert è stata acquisita più volte e oggi è controllata da fondi internazionali.

**Dipendenza 4 — Slack / Microsoft Teams.** Le chat aziendali interne, dove passa la maggior parte del lavoro operativo quotidiano, sono ospitate negli Stati Uniti (Slack su AWS US-East) o in Irlanda/Olanda (Teams). Le aziende italiane non hanno un equivalente "PEC" per la chat: non c'è alcuno strumento con valore legale per la messaggistica istantanea aziendale.

**Dipendenza 5 — WhatsApp Business.** Nonostante quasi tutte le policy di sicurezza lo proibiscano formalmente, WhatsApp è ampiamente usato per comunicazioni di lavoro in Italia. È controllato da Meta (Facebook), datacenter primario negli USA, cifratura end-to-end ma metadati e backup non protetti.

**Dipendenza 6 — Sistemi documentali ibridi.** OneDrive (Microsoft), Google Drive, Dropbox sono usati come archivio condiviso. Spesso senza policy chiare su cosa può finire dove. I documenti più sensibili — bilanci, contratti, NDA — finiscono frequentemente nella prima cartella disponibile, senza distinzione di classificazione.

In ognuna di queste sei dipendenze, la tua azienda **non ha** controllo crittografico, **non ha** possibilità di audit indipendente, **non ha** garanzia di continuità. Sei in concessione.

## 2.2 — La PEC non basta, e il legislatore lo sa

Vale la pena tornare brevemente sulla PEC, perché è lo strumento che più frequentemente i CEO italiani citano quando viene loro detto "le tue comunicazioni sono fuori controllo". La risposta tipica è: "Ma noi usiamo la PEC".

La PEC, ricordiamolo, garantisce: (a) la consegna in una certa data, (b) ai sensi del DPR 68/2005, tra caselle PEC italiane. Non garantisce: l'integrità del contenuto, l'opponibilità all'estero, la sopravvivenza della prova oltre il provider.

Il legislatore italiano lo sa. Per questo, dal 2023, è stata avviata una progressiva integrazione con il sistema europeo eIDAS 2.0 (Regolamento UE 910/2014, modificato 2024) attraverso il **Recommended Electronic Registered Delivery Service** (R-ERDS) — un nuovo standard che dovrebbe sostituire le PEC nazionali con un equivalente europeo cross-border. La transizione è prevista entro il 2027, ma è ancora largamente teorica.

Per le imprese italiane questo significa due cose. Primo: lo strumento "PEC" come lo conosciamo oggi è in declino normativo. Secondo: lo strumento sostitutivo (R-ERDS) sarà gestito da fornitori commerciali che probabilmente saranno gli stessi attuali, con gli stessi limiti di indipendenza. Nessuno dei due offre quello che Lattice Certify offre: prova crittografica verificabile dal Block Explorer, indipendente dal fornitore, valida ovunque, durevole nel tempo.

## 2.3 — Tre esempi italiani concreti

Per rendere il discorso non teorico, ecco tre situazioni — anonimizzate ma reali — che il consulente che ha scritto questo capitolo ha incontrato negli ultimi diciotto mesi presso clienti italiani.

**Esempio 1 — Studio legale, 45 dipendenti, Roma.** Lo studio gestisce contenziosi M&A per un portafoglio di PMI. Tutta la corrispondenza con i clienti passa via Outlook (Microsoft 365). Nel 2024 un dipendente uscito in conflitto ha "portato con sé", via download su disco personale prima della cessazione del rapporto, oltre 4.000 mail con clienti. La causa civile in corso è ancora aperta. Lo studio ha scoperto la fuga dati solo quando uno dei clienti ha ricevuto una proposta competitiva da un altro studio con dettagli che solo il primo poteva conoscere. **Cosa avrebbe cambiato Lattice**: ogni mail interna firmata dal dipendente, identità revocabile in tempo reale, ledger di accesso. Il furto sarebbe stato dimostrabile in modo crittografico e il dipendente non avrebbe potuto sostenere che le mail erano "originali sue".

**Esempio 2 — Banca privata, 380 dipendenti, Milano.** Nel 2025 Microsoft ha sospeso temporaneamente l'account 365 della banca per 19 ore a causa di un falso positivo in un sistema automatico di rilevamento attività anomala. Durante quelle 19 ore, la banca non poteva inviare conferme di trade ai propri clienti istituzionali. Il danno reputazionale è stato contenuto solo grazie al fatto che il consiglio aveva richiesto, l'anno prima, l'installazione di un sistema mail di backup interno. La banca paga oggi due licenze parallele. **Cosa avrebbe cambiato Lattice**: l'infrastruttura primaria sui server della banca, Microsoft 365 come sistema secondario per le comunicazioni meno critiche. Sospensione del fornitore = problema operativo limitato, non blocco totale.

**Esempio 3 — Manifatturiero, 120 dipendenti, Vicenza.** L'azienda produce componenti per il settore automotive e ha ricevuto, nel 2024, un'offerta di acquisizione da un gruppo cinese. La trattativa è transitata, per ragioni di velocità, su Gmail dei singoli soci. Una mail importante è poi finita "per errore" (sostiene il socio) inoltrata a un broker concorrente. La trattativa è saltata. Il socio ha negato di aver inoltrato la mail. Senza prova crittografica del contenuto, la disputa interna è oggi al consulente tecnico. **Cosa avrebbe cambiato Lattice**: ogni mail firmata dal mittente, registro on-chain dei forward. La domanda "chi ha inoltrato cosa, quando" sarebbe stata risolta in 30 secondi sul Block Explorer.

## 2.4 — Cosa dovrebbe fare un CdA italiano nel 2026

Da queste osservazioni emerge una specifica operativa, indipendente dal libro che state leggendo. Un consiglio di amministrazione italiano, di un'azienda con più di 30 dipendenti che gestisce dati riservati, dovrebbe nei prossimi diciotto mesi:

1. **Inventariare** dove sono fisicamente i propri dati di comunicazione (mail, chat, archivi, backup). Spesso il CdA non sa la risposta esatta.
2. **Quantificare** il danno operativo di una sospensione del fornitore primario per 24, 72, 168 ore. Il numero spesso supera il fatturato medio settimanale.
3. **Identificare** quali comunicazioni hanno valore strategico o probatorio sopra i 5 anni, e dunque richiedono trattamento speciale.
4. **Valutare** alternative sovrane: on-premise, cloud sovrano EU, soluzioni open-source ispezionabili.
5. **Pianificare** una migrazione progressiva: prima la posta con valore legale, poi la chat strategica, poi il resto.

Lattice è una possibile risposta operativa al punto 4. Non l'unica. Ma — secondo gli autori del libro — quella più completa nella combinazione di sovranità, isolamento, prova verificabile e apertura del codice.

## 2.5 — Domanda per la prossima riunione

Se siete in un CdA, portate questa domanda: **"Se uno dei nostri tre fornitori principali di comunicazione (Microsoft, Google, il provider PEC) sospendesse il servizio per 48 ore, qual è il piano B operativo e quanto costerebbe in fatturato perso?"**

Se non c'è piano B operativo, è perché si è dato per scontato che il fornitore "non lo farà mai". Negli ultimi cinque anni, in Europa, lo ha fatto.
