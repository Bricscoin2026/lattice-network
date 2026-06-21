# CAPITOLO 13 — Casi d'uso reali.

## 13.0 — Apertura

Questo capitolo racconta quattro storie concrete di adozione di Lattice in quattro settori distinti del tessuto produttivo italiano: una banca privata, uno studio legale, un comune di medie dimensioni, un'azienda manifatturiera. I nomi, le date e i dettagli identificativi sono stati modificati per ragioni di riservatezza commerciale e di sicurezza informatica. Le dinamiche operative, i numeri e i risultati sono fedeli a situazioni effettive.

L'obiettivo è mostrare, settore per settore, dove Lattice produce valore concreto e come si misura il ritorno dell'investimento.

[FIGURA 13.1 — ROI: tempi di payback per i quattro casi d'uso]

## 13.1 — Caso 1 — Banca privata, 380 dipendenti, Milano

**Il contesto.** Banca di gestione patrimoniale, clientela high-net-worth, AUM circa 8 miliardi. Stack di comunicazione: Microsoft 365 (mail + Teams), Aruba PEC, file shares su OneDrive, sistemi proprietari per trading. 380 dipendenti tra Milano, Roma, Lugano.

**Il trigger.** A maggio 2025, una sospensione automatica del tenant Microsoft 365 per 19 ore (falso positivo) ha bloccato le conferme di trade verso clienti istituzionali. Il CdA, su pressione del comitato rischi, ha chiesto un piano B. Una valutazione costi-benefici ha identificato Lattice come la migliore tra le quattro opzioni considerate (le altre tre: secondo provider mail in parallelo, ritorno a Exchange on-premise, soluzione di sovereign cloud Microsoft).

**Il rollout.** Fase 1 (3 mesi): Lattice installato come backup sovrano per le comunicazioni del comitato esecutivo + ufficio compliance + ufficio legale (35 utenti). Microsoft 365 resta primario. Fase 2 (6 mesi): si estende a tutto il front-office (200 utenti) per le comunicazioni con i clienti istituzionali. Fase 3 (9-12 mesi): la totalità delle comunicazioni con valore probatorio (contratti, conferme trade, notifiche regolamentari) passa per Lattice Certify. Microsoft 365 resta per la mail "leggera" interna.

**I numeri.** Investimento totale (HW + licenze Lattice + consulenza): 380.000 euro su 18 mesi. Riduzione del costo Microsoft 365 da Business Premium a Plan 1 per 250 utenti: -180.000 euro/anno. Riduzione del costo di compliance DORA (meno fornitori critici da auditare): -90.000 euro/anno. Payback: ~14 mesi. Beneficio non monetario: capacità di operare anche in caso di nuova sospensione Microsoft → quantificato in 8 ore × 50.000 euro/ora di fatturato a rischio = 400.000 euro evitati per evento.

**Cosa è cambiato qualitativamente.** Il CdA ha smesso di porre la domanda "siamo esposti a Microsoft?" perché ha visto la risposta operativa. Il comitato rischi ha incluso Lattice come pilastro permanente del piano BCP. Le conversazioni con i clienti istituzionali avvengono ora su un'infrastruttura che la banca controlla integralmente.

## 13.2 — Caso 2 — Studio legale, 45 dipendenti, Roma

**Il contesto.** Studio specializzato in M&A e contenziosi commerciali. 45 dipendenti tra avvocati, paralegal, segretarie. Stack: Microsoft 365, Aruba PEC, archivio cartaceo in cassaforte (sì, ancora), Dropbox aziendale per condivisione bozze.

**Il trigger.** Nel 2024 un dipendente uscito in conflitto ha scaricato oltre 4.000 mail con clienti prima della cessazione del rapporto e — sospetto — ha usato i contatti per offerte concorrenziali. Lo studio ha aperto causa civile, ma la dimostrazione tecnica del furto e dell'uso indebito si è rivelata difficile (gli audit log Microsoft 365 erano limitati a 90 giorni, l'integrità del log dipendeva da Microsoft, il dipendente sostiene che le mail "erano modificate dopo lo scaricamento"). L'esito della causa è ancora pendente al momento della stesura del capitolo.

**Il rollout.** Lo studio ha deciso di adottare Lattice integralmente per tutto lo studio in un'unica fase di 4 mesi. La motivazione: piccolo, omogeneo, alta sensibilità, costo ridotto.

**I numeri.** Investimento totale: 95.000 euro (HW + Lattice + consulenza + training). Risparmio annuale: 22.000 euro (Microsoft 365 ridotto, Dropbox eliminato, PEC ridotta). Payback: 4.5 anni. Beneficio principale: **la prova legale per cause future è ora crittografica e indipendente dal fornitore**. Per uno studio legale, questo è il valore primario, non il risparmio.

**Cosa è cambiato qualitativamente.** Lo studio ha incluso nel proprio contratto-cliente una clausola che dichiara che "ogni comunicazione importante è verificabile sul Block Explorer Lattice all'URL X". I clienti M&A — particolarmente sensibili alla riservatezza — hanno percepito questo come un differenziale competitivo. Lo studio ha acquisito tre nuovi clienti di fascia alta nel 2025 citando esplicitamente la sicurezza delle comunicazioni come motivo di scelta.

## 13.3 — Caso 3 — Comune di media dimensione, 280 dipendenti, Veneto

**Il contesto.** Comune capoluogo di provincia. 280 dipendenti tra uffici comunali, vigili urbani, servizi sociali. Stack: Microsoft 365 EDU (variante per PA), PEC Aruba, Protocollo informatico SPRECO (gestionale interno), archivi cartacei.

**Il trigger.** L'entrata in vigore del DLgs 138/2024 (NIS2) ha posto il Comune nella categoria di soggetti pubblici essenziali. L'ACN ha chiesto, nel febbraio 2025, una mappatura delle infrastrutture critiche e un piano di rafforzamento. La verifica ha rivelato che la quasi totalità della comunicazione del Comune con cittadini, fornitori e altri enti pubblici passava da fornitori esteri.

**Il rollout.** Per ragioni di budget (il Comune ha budget annuale fisso, non variabile come un'azienda privata), il rollout è stato lento: 18 mesi per la fase 1 (Sindaco + giunta + segretario generale + ufficio legale, 28 utenti), altri 18 mesi pianificati per estendere al resto.

**I numeri.** Investimento fase 1: 60.000 euro (HW + Lattice + consulenza). Costo Microsoft 365 ridotto del 30% sui 28 utenti. Costo PEC ridotto del 40% (Aruba mantenuta solo per comunicazioni con altri enti che ancora richiedono PEC italiana standard). Beneficio principale: **conformità NIS2 dimostrabile**, evitata sanzione potenziale fino al 2% delle entrate proprie del Comune.

**Cosa è cambiato qualitativamente.** Il Comune ha pubblicato una pagina "Comunicazioni sovrane" sul proprio sito, con link al Block Explorer Lattice, dove i cittadini possono verificare che le comunicazioni ufficiali (delibere, ordinanze, notifiche) sono firmate digitalmente con strumenti europei e verificabili pubblicamente. Questa trasparenza ha generato copertura stampa locale positiva.

## 13.4 — Caso 4 — Azienda manifatturiera, 120 dipendenti, Vicenza

**Il contesto.** Produttore di componenti meccaniche di precisione per automotive e aerospazio. 120 dipendenti, fatturato 35 milioni, export al 70%. Stack: Google Workspace (la scelta del fondatore, che voleva "qualcosa di diverso da Microsoft"), Slack per comunicazioni interne, Dropbox per disegni tecnici, PEC InfoCert.

**Il trigger.** Una proposta di acquisizione da parte di un gruppo cinese, nel 2024, è transitata via Gmail tra i due soci dell'azienda. Una mail interna delicata è poi finita "per errore" inoltrata a un broker concorrente. La trattativa è saltata e i soci sono in disputa interna sul chi ha inoltrato cosa. Senza prova crittografica del contenuto, la disputa è oggi al consulente tecnico — costo stimato 80.000 euro di parcelle legali e perdita della trattativa di acquisizione (valore: ~12 milioni).

**Il rollout.** I soci hanno chiesto a Lattice un setup d'emergenza in 4 settimane, focalizzato sulle comunicazioni dei vertici (15 utenti). Il resto dell'azienda continua su Google Workspace.

**I numeri.** Investimento fase iniziale: 55.000 euro. Beneficio: in futuri scenari M&A, le comunicazioni saranno crittograficamente attribuibili. Le dispute interne tra soci su "chi ha inoltrato cosa" diventano risolvibili in 30 secondi sul Block Explorer.

**Cosa è cambiato qualitativamente.** I soci hanno introdotto Lattice nelle comunicazioni interne strategiche e hanno deciso di estendere progressivamente a tutta l'azienda nel 2026-2027. Per loro, il valore principale non è la sostituzione di Google (che hanno tenuto) ma l'**isolamento di un perimetro ristretto di comunicazione critica** dove le regole sono diverse.

## 13.5 — Il pattern comune

Da questi quattro casi, emerge un pattern: **Lattice non sostituisce mai integralmente Microsoft/Google al primo giorno**. Sostituisce — con un beneficio enorme e misurabile — il **sottoinsieme di comunicazioni dove la sovranità conta davvero**. Il resto può rimanere su Microsoft/Google per pragmatismo.

Questo è il modello "ibrido controllato" che abbiamo descritto nel cap. 6.5 e che resta la raccomandazione per la grande maggioranza dei clienti.

L'errore tipico delle aziende che approcciano la sovranità è il "tutto o niente": o resto totalmente su Microsoft (e sono esposto), o devo migrare totalmente (e mi spavento, e non lo faccio mai). Il modello giusto è il triage: identifica il 10-30% di comunicazioni dove la sovranità è critica e mettilo al sicuro. Per il resto, valuta nel tempo.

## 13.6 — ROI e tempi di payback

In sintesi, dai quattro casi:

| Settore | Investimento | Risparmio annuo | Payback | Beneficio principale non monetario |
|---|---|---|---|---|
| Banca | 380.000 € | 270.000 €/anno | 14 mesi | Continuità operativa in caso di sospensione fornitore |
| Studio legale | 95.000 € | 22.000 €/anno | 4.5 anni | Prova crittografica indipendente |
| Comune | 60.000 € | 18.000 €/anno | 3.5 anni | Conformità NIS2 dimostrabile |
| Manifatturiero | 55.000 € | (non quantif.) | (a evento) | Risoluzione M&A future |

Il payback medio è di 2-4 anni per il TCO, ma il valore principale per ogni settore è quello non monetario: **continuità, prova, conformità, riservatezza**. Sono i valori che il consiglio non vorrebbe mai vedere quantificati a posteriori — perché significherebbe che è successo qualcosa.

## 13.7 — Domanda per il proprio settore

A prescindere dal settore della vostra azienda, una buona domanda è: **"Quale evento, nei prossimi cinque anni, ci porterebbe a desiderare di aver avuto un'infrastruttura di comunicazione sovrana? Cosa ci costerebbe quell'evento se accadesse oggi?"**

Per ogni settore la risposta è diversa. Ma la conclusione operativa è sempre la stessa: il momento giusto per costruire l'infrastruttura è prima dell'evento, non dopo.
