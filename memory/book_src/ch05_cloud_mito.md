# CAPITOLO 5 — Cloud pubblico, SaaS estero e il mito del "private link".

## 5.0 — Apertura

La risposta più frequente che un fornitore di cloud pubblico (Microsoft, Google, AWS) dà a un CISO italiano preoccupato della sovranità è: "Abbiamo il private link / il datacenter europeo / la sovereignty option / il sovereign cloud announcement". È una risposta sofisticata e ben preparata, perché copre la domanda formale senza affrontare la sostanza tecnica.

In questo capitolo demoliamo, una alla volta, le quattro promesse standard che i grandi fornitori cloud fanno per sembrare "sovrani". Lo facciamo senza animosità: questi fornitori sono ottimi per ciò che fanno bene (scalare globalmente, offrire migliaia di servizi managed). Il punto è capire che non possono essere sovrani — è strutturalmente impossibile.

## 5.1 — Promessa 1 — "I dati sono in Europa"

Microsoft, Google, AWS hanno tutti datacenter in Irlanda, Olanda, Germania, Francia, Italia. Tecnicamente è vero che i dati possono essere localizzati nei datacenter europei.

Ma la localizzazione fisica del dato è solo uno dei sei requisiti di sovranità (capitolo 4). Restano fuori: sovranità del codice (il fornitore non ti mostra il sorgente), sovranità delle chiavi (Microsoft conserva le chiavi master, anche se tu hai una "customer-managed key" — c'è sempre una chiave di emergenza del fornitore), sovranità dell'infrastruttura (i server, gli ipervisori, le reti sono di Microsoft), sovranità degli aggiornamenti (Microsoft aggiorna quando vuole), sovranità della catena di fornitura (Microsoft compila e firma il software).

Più importante ancora: il **CLOUD Act statunitense** del 2018 impone a Microsoft, Google e AWS di consegnare i dati alle autorità americane su richiesta motivata, anche se i dati sono fisicamente in Europa. Non è una clausola contrattuale aggirabile: è una legge federale che obbliga questi fornitori. La sentenza Schrems II della Corte di Giustizia UE (2020) ha dichiarato questo regime incompatibile con il GDPR, ma sei anni dopo l'industria continua a usare gli stessi servizi.

Conclusione: "dati in Europa" è una metà dell'opera. Risolve la conformità GDPR formale (a fatica), non la sovranità sostanziale.

## 5.2 — Promessa 2 — "Private link / network isolation"

I private link (Azure Private Link, AWS PrivateLink, Google Private Service Connect) sono connessioni dedicate tra il datacenter del cliente e i servizi cloud, che evitano il transito su Internet pubblica. Sono utili per la sicurezza in transito, ma non per la sovranità.

Una volta che i dati arrivano nel datacenter del fornitore, sono nel suo ambiente. Il private link non cambia chi vede i dati a destinazione. Non cambia chi può sospendere il servizio. Non cambia chi possiede le chiavi.

Conclusione: il private link risolve un problema specifico (intercettazione del traffico Internet pubblica), non il problema della sovranità.

## 5.3 — Promessa 3 — "Customer-managed encryption keys"

Microsoft Azure Key Vault, AWS KMS e Google KMS offrono opzioni di "customer-managed keys" (CMK), dove il cliente può portare la propria chiave master invece di usare quella del fornitore.

In linea di principio è una bella idea. In pratica c'è un dettaglio nascosto: la chiave del cliente è comunque protetta da una chiave del fornitore (root-of-trust). Il fornitore non vede mai la chiave del cliente in chiaro, ma ha la capacità tecnica, in casi di emergenza dichiarati, di accedere alle chiavi della propria infrastruttura. Microsoft lo documenta esplicitamente come "Microsoft Recovery Key" nei propri whitepaper compliance.

Inoltre, anche se la chiave del cliente fosse perfettamente protetta, il fornitore può sempre sospendere il servizio (negazione del servizio anche se i dati sono cifrati con chiave del cliente). E può sempre ricevere un ordine giudiziario che richiede la consegna dei dati cifrati al cliente, lasciando al cliente l'onere di rifiutare di decifrarli (con costi legali notevoli).

Conclusione: la CMK è meglio delle chiavi del fornitore, ma non è equivalente a chiavi sotto il controllo esclusivo del cliente.

## 5.4 — Promessa 4 — "Sovereign cloud" recente (2024-2026)

Microsoft ha lanciato nel 2024 il "Microsoft Cloud for Sovereignty", Google ha annunciato un "Sovereign Controls" e AWS un "European Sovereign Cloud" previsto per il 2026. Sono offerte costruite specificamente per rispondere alla pressione regolatoria europea.

Da quello che è pubblicamente documentato, queste offerte garantiscono: (a) datacenter in Europa con personale solo europeo, (b) niente accesso da parte di personale del fornitore di paesi terzi senza approvazione del cliente, (c) procedure rinforzate di risposta a richieste extraterritoriali.

Sono passi avanti reali. Ma rimangono tre limiti strutturali: (i) il codice resta proprietario e non auditabile dal cliente, (ii) le chiavi crittografiche di root sono comunque sotto controllo del fornitore (anche se geograficamente isolate), (iii) il fornitore può ancora sospendere il servizio o uscire dal mercato europeo per decisione corporate.

Conclusione: il "sovereign cloud" è un miglioramento marginale del rischio, non una sovranità tecnica. Per dati realmente strategici (M&A, segreti industriali, comunicazioni legali, contenziosi) resta inadeguato.

## 5.5 — Cosa significa, in pratica, "sovrano davvero"

Ricapitolando dal capitolo 4: una piattaforma "sovrana davvero" deve essere:

1. Open source (almeno per le componenti crittografiche e di sicurezza) o, in alternativa, soggetta a escrow del codice presso un terzo affidabile.
2. Hostable on-premise o in un'infrastruttura europea che il cliente sceglie e audita (non in cui il cliente "è ospitato").
3. Con chiavi generate e conservate dal cliente, senza alcuna chiave di recovery del fornitore.
4. Aggiornabile su decisione del cliente (no auto-update forzato).
5. Buildabile in modo riproducibile.

Lattice è progettato per soddisfare tutti e cinque i criteri. Il prezzo è che richiede al cliente di gestire la propria infrastruttura (server fisici o cloud sovrano selezionato da lui). Non offriamo "Lattice as a Service" gestito da noi, perché — coerentemente con il nostro discorso — questo creerebbe un nuovo fornitore-monopolista. Offriamo il software e il know-how per metterlo in opera.

## 5.6 — Quando il cloud pubblico va benissimo

Per essere onesti: il cloud pubblico non è il diavolo. Per molte aziende e per molti servizi è la scelta giusta. Il punto del capitolo è che **non lo è per la comunicazione aziendale ad alto valore strategico o probatorio**.

Il cloud pubblico va benissimo per: ospitare il sito web aziendale, il CRM (per quanto: vedi anche qui), il CMS, le applicazioni interne non sensibili, gli ambienti di sviluppo e test, i workload massivi di calcolo (HPC, AI training), lo storage di dati pubblici o anonimizzati.

Il cloud pubblico va male per: la mail con valore legale, la chat interna con segreti industriali, l'archivio dei contratti firmati, le comunicazioni del consiglio di amministrazione, i contenziosi in corso, le pratiche M&A, i piani strategici di prodotto. Per queste cose, Lattice è la risposta razionale del 2026.

## 5.7 — Domanda per la prossima riunione

Portate questa domanda al CdA: **"Per quale singola informazione strategica della nostra azienda — segreto industriale, lista clienti chiave, trattativa in corso — saremmo davvero a nostro agio se Microsoft o Google la leggesse?"**

Se la risposta è "nessuna", allora avete identificato esattamente ciò che deve uscire dal cloud pubblico. Lattice serve a quello.
