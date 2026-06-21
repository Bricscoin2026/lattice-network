# EXECUTIVE SUMMARY — Riprendi il controllo delle tue comunicazioni aziendali.

*Per CEO, CISO e Direzione Legale. Cinque pagine. Niente acronimi inutili.*

## Il problema in una frase

**Ogni giorno la tua azienda affida le sue comunicazioni più importanti — mail con i clienti, decisioni del consiglio, contratti, messaggi interni — a quattro fornitori americani: Microsoft 365, Google Workspace, Slack e, in Italia, alle PEC dei provider commerciali.** Tu non hai accesso ai loro server. Non puoi auditare i loro log. Non puoi opporti se decidono di sospenderti l'account. Non puoi dimostrare a un giudice, in modo indipendente, che una mail di quattro anni fa è stata effettivamente scritta dalla persona che dici. E non puoi impedire che un dipendente che esce dall'azienda porti con sé l'intero archivio nella sua cartella *Posta inviata* di Gmail.

Non è un problema di sicurezza informatica. È un problema di **controllo**.

## Quanto è grave, in numeri

Un'azienda italiana di medie dimensioni (50-500 dipendenti) gestisce in media:

- **5.000 mail al giorno** in entrata e uscita, di cui circa il 4% contiene allegati con valore legale (offerte, contratti, NDA, cedolini).
- **12.000 messaggi al giorno** su chat aziendali (Slack, Teams, WhatsApp Business), di cui una percentuale crescente — stimata sopra il 20% — contiene decisioni operative che, in caso di contenzioso, dovrebbero essere prodotte come prova.
- **3-5 fornitori cloud diversi** che vedono passare i contenuti aziendali in chiaro (Microsoft, Google, Slack, Dropbox, Zoom, eccetera).
- **0 archivi indipendenti dal fornitore** — se Microsoft cancella il tenant, le mail spariscono; se Slack chiude il workspace, le chat spariscono; se la PEC scade, le ricevute restano valide solo finché il provider esiste.

A questi numeri si aggiungono tre fatti che la maggior parte degli amministratori delegati italiani non ha ancora messo a fuoco:

1. **La PEC italiana ha valore legale solo in Italia.** Una controparte tedesca, francese o americana non riconosce la ricevuta PEC come prova di consegna. Quando lavori con clienti esteri, le tue comunicazioni "ufficiali" tornano a essere mail Gmail/Outlook senza valore probatorio specifico.
2. **Microsoft 365 e Google Workspace sono regolati dal CLOUD Act statunitense.** Significa che, su richiesta motivata del Department of Justice, Microsoft e Google sono obbligati a consegnare i tuoi dati alle autorità americane — anche se i datacenter sono fisicamente in Europa. La sentenza Schrems II della Corte di Giustizia UE (2020) ha dichiarato questo trasferimento incompatibile col GDPR, ma il problema operativo non è risolto: continui a usare gli stessi servizi.
3. **Quando licenzi un dipendente IT, lui ha potenzialmente accesso a tutto.** Gli account di servizio, le API key, le credenziali dei tenant Microsoft sono frequentemente condivisi. La revoca completa, in un'azienda media, richiede 3-7 giorni di lavoro e raramente è verificabile in modo crittografico.

## Quattro rischi materiali (non teorici)

**Rischio 1 — Sospensione operativa per decisione di un fornitore.**
Nel 2022 Microsoft ha sospeso temporaneamente, su sanzioni occidentali, gli account 365 di alcune entità russe. Negli ultimi due anni la stessa misura è stata applicata a clienti turchi, iraniani e — in casi noti — a piccole aziende europee per "violazione dei termini di servizio". La tua azienda non ha una clausola che ti protegga da questa eventualità. Il giorno in cui un fornitore decide di interrompere il servizio, la tua mail ufficiale, il tuo OneDrive, il tuo Teams smettono di funzionare. Niente recupero. Niente ricorso pratico in tempi utili.

**Rischio 2 — Dispersione del know-how aziendale.**
Decisioni strategiche, formule, codici sorgente, liste clienti viaggiano su Slack, Teams e WhatsApp Business. Quando un dipendente esce — sia in modo concordato che conflittuale — la separazione dei dati è quasi impossibile da garantire al 100%. Le sue copie locali, i suoi screenshot, i suoi backup personali restano fuori dal tuo controllo. Il segreto industriale, di fatto, ti è già sfuggito di mano prima ancora che lui firmi la lettera di dimissioni.

**Rischio 3 — Inopponibilità in giudizio.**
Quando devi dimostrare che una mail è stata inviata in una certa data con un certo contenuto da una certa persona, la stampa cartacea di Gmail non basta. Una controparte può sempre sostenere che la mail è stata modificata, l'header alterato, l'account compromesso. La PEC offre una garanzia parziale (e solo per controparti italiane). Per il resto, il valore probatorio dipende dalla capacità del tuo perito di dimostrare l'integrità della catena di custodia. Nelle cause civili e di lavoro questo è uno dei punti più contestati dai consulenti tecnici di parte.

**Rischio 4 — Crittografia che invecchia.**
Tutta la sicurezza che oggi protegge mail, PEC, VPN, certificati TLS si basa su algoritmi (RSA, ECDSA) che il NIST americano stesso ha dichiarato non più adeguati per dati con vita superiore a dieci anni. Esistono dal 2024 standard sostitutivi (FIPS 203, FIPS 204, FIPS 205), ma l'industria italiana, in larga parte, non li ha ancora adottati. Vedi capitolo 8 per il dettaglio tecnico. Vedi anche il termine "Harvest Now, Decrypt Later": chi intercetta oggi il tuo traffico cifrato, lo decifrerà tra dieci anni.

## La conseguenza, raccontata semplice

Immaginate un consiglio di amministrazione, mercoledì pomeriggio, a Milano. Il direttore IT entra con una pila di stampe. Sono mail interne degli ultimi cinque anni che sono finite online — vendute, esposte, esfiltrate, a seconda dello scenario. Decisioni sulle remunerazioni dei top manager. Trattative con clienti in concorrenza tra loro. Una corrispondenza riservata con un avvocato su una causa che la stampa specializzata sta seguendo. Una nota interna su un prodotto difettoso che era stato risolto privatamente.

Niente di questo era illegale. Niente di questo, fino al giorno prima, era pubblico. **Diventa pubblico nel momento in cui la tua infrastruttura di comunicazione cede.** E quando la chiedi a Microsoft o a Google una versione "ufficiale" dell'archivio, ti dicono che possono fornirla — in 90 giorni, in formato proprietario, con un costo accessorio e zero garanzie sull'integrità rispetto a quanto era stato originariamente scritto.

Quel giorno il problema non è più tecnico. È un problema di reputazione, di esposizione contrattuale, di responsabilità degli amministratori. È il giorno in cui il consiglio capisce che le comunicazioni aziendali non erano mai state davvero "vostre".

## La soluzione: Corporate Communication Control Layer

Lattice è una **rete privata di comunicazione aziendale** che la tua azienda installa on-premise o in un cloud sovrano europeo, sotto il tuo controllo esclusivo. Non è "un altro SaaS in più". È il **livello di controllo** che oggi non hai: un'infrastruttura dove la mail interna, la mail con valore legale, la chat aziendale, i documenti firmati e l'audit di chi ha fatto cosa restano fisicamente sulla tua rete, indipendenti da Microsoft, Google, Slack e dai provider PEC esterni.

Cosa cambia, concretamente:

1. **Le identità aziendali le emetti tu.** Ogni dipendente, fornitore, consulente riceve un'identità crittografica firmata dalla tua azienda (Lattice Name Service). Quando lui esce, la revochi in un click — e ogni mail e messaggio futuri firmati con quella chiave vengono automaticamente rifiutati dal sistema. Senza dover chiedere niente a Microsoft.
2. **La mail con valore legale è verificabile da chiunque, per sempre.** Ogni mail Certify viene notarizzata sul ledger interno con firma digitale crittograficamente forte (post-quantum). Chiunque, in qualsiasi momento — anche tra vent'anni, anche se la tua azienda nel frattempo si è trasformata — può consultare il Block Explorer pubblico di Lattice e verificare matematicamente che quella mail è stata firmata da quella persona in quella data.
3. **La chat interna non lascia la tua rete.** Pulse è una messaggistica end-to-end stile Signal che gira sui tuoi server. Microsoft, Google, Slack, WhatsApp non vedono nulla. Le conversazioni sono ancorate periodicamente al ledger, così che — se necessario per un audit interno o un'indagine — si possa dimostrare l'integrità dello scambio senza dover credere al fornitore.
4. **Niente lock-in.** Il codice è open source ispezionabile, i protocolli sono pubblici, gli standard crittografici sono quelli del NIST americano. Se domani decidi di portare l'infrastruttura su un altro hosting o di gestirla in autonomia, lo fai senza chiedere il permesso a nessuno.

## Cosa ottieni in pratica

**Per il CEO.** Sovranità reale. La tua azienda smette di dipendere da quattro fornitori extra-UE per le comunicazioni più importanti. Continui a usare le tue mail e le tue chat come sempre — solo che girano su una rete che gestisci tu. Quando qualcuno (cliente, controparte, autorità) ti chiede una prova, gliela mostri direttamente dal Block Explorer pubblico, senza intermediari.

**Per il CISO.** Perimetro definibile. Ogni comunicazione aziendale ha un'identità verificata, una firma crittografica, un audit trail indipendente. La revoca di chi esce è immediata e tracciabile. Il GDPR e la NIS2 sono soddisfatti senza dover compilare moduli su moduli per giustificare il trasferimento dati extra-UE.

**Per il Legale.** Prova opponibile. La mail Certify ha valore probatorio molto più forte della stampa di una Gmail e — diversamente dalla PEC italiana — è verificabile anche all'estero, da chiunque, senza dover chiamare un perito di fiducia del fornitore. Il ledger immutabile elimina la discussione su "questa mail è stata alterata oppure no?".

## Come si parte

Tre passaggi. Cinque giorni lavorativi. Nessun contratto pluriennale richiesto.

1. **Una call di 30 minuti**, senza obblighi, per capire la dimensione e i bisogni specifici della tua azienda.
2. **Installazione della rete** on-premise (sui tuoi server fisici) o in un cloud sovrano europeo dedicato. Test di un sottogruppo di dipendenti — tipicamente la direzione, il legale, il finance — per 30 giorni.
3. **Roll-out completo** sui dipendenti restanti. Migrazione progressiva delle comunicazioni più sensibili da Microsoft/Google a Lattice. Le comunicazioni meno critiche possono restare dove sono — Lattice non vuole sostituire tutto, vuole sostituire ciò che davvero conta.

## La parte tecnica (in fondo, e apposta)

Il resto del libro — dal Capitolo 7 in poi — descrive in dettaglio gli strumenti crittografici che permettono a Lattice di mantenere queste promesse. Sono strumenti pubblici e verificabili: gli standard NIST FIPS 203 e 204 per la crittografia post-quantistica, il consenso QBFT per la finalizzazione del ledger interno, il protocollo Loopix per l'anonimizzazione della chat, il modello PEC court-grade per il valore probatorio della posta.

Se ti interessa la parte tecnica, troverai tutto. Se non ti interessa, non è obbligatorio leggerla. **Ciò che conta è che la promessa funziona perché la matematica funziona, non perché te lo diciamo noi.** E la matematica è la stessa che oggi protegge le comunicazioni classificate del Dipartimento della Difesa americano e dell'agenzia di sicurezza tedesca BSI.

## In sintesi

| Domanda | Risposta |
|---|---|
| Cosa è Lattice? | Una rete privata aziendale per mail, chat e archiviazione legale, che gestisci tu. |
| Chi sostituisce? | Microsoft 365, Google Workspace, Slack, PEC esterne, in tutto o in parte. |
| Dove gira? | On-premise (tuoi server) oppure cloud sovrano EU. Mai datacenter extra-UE. |
| Quanto ci si mette? | 5 giorni lavorativi per la prima messa in opera. 30 giorni per il pilota. |
| Quanto costa? | Modello a fascia di dipendenti, costo predicibile, niente lock-in. |
| Chi ne risponde tecnicamente? | Lattice Network. Codice open source. Audit di sicurezza pubblico. |

Il resto del libro ti dice esattamente cosa c'è dietro queste sei risposte, e perché — secondo l'autore — è una delle scelte più consequenziali che un consiglio di amministrazione italiano possa fare nei prossimi diciotto mesi.

Buona lettura.
