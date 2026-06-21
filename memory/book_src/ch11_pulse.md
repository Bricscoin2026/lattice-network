# CAPITOLO 11 — Pulse: la chat aziendale che non esce dalla tua rete.

## 11.0 — Apertura

Dopo Certify (mail con valore legale), il secondo modulo applicativo di Lattice è **Pulse**: la chat aziendale interna. Sostituisce, in tutto o in parte, le funzioni di Slack, Microsoft Teams e — soprattutto — WhatsApp Business che oggi è il vero canale principale, anche se ufficiosamente proibito, delle comunicazioni operative in moltissime aziende italiane.

Pulse è la risposta a una domanda specifica: **come fare in modo che la chat interna dell'azienda non lasci la rete aziendale, sia leggibile solo dai partecipanti, e — quando serve — possa essere verificata in giudizio senza dipendere da un fornitore esterno?**

## 11.1 — Il problema specifico della chat aziendale

La chat aziendale ha tre caratteristiche che la rendono particolarmente vulnerabile rispetto alla mail:

**Velocità e volume.** Le aziende generano molte più conversazioni di chat che mail. Una squadra di 20 persone produce facilmente 500 messaggi al giorno. Il volume rende difficile sottoporre ogni messaggio a controlli di sicurezza individuali; in pratica si applicano controlli a livello di applicazione (cifratura globale) e si spera per il meglio.

**Informalità e franchezza.** Le persone scrivono in chat in modo più informale di quanto facciano in mail. Discutono di strategia, di concorrenza, di problemi interni, di clienti, in modo che — se la chat fosse pubblicata — risulterebbe imbarazzante o legalmente problematico. Le chat aziendali contengono spesso le decisioni "vere", quelle prima che diventino formalizzate.

**Sovrapposizione con dispositivi personali.** WhatsApp Business gira sul telefono personale del dipendente. Slack gira sul portatile aziendale che il dipendente porta a casa. Le chat sopravvivono sui dispositivi anche dopo la cessazione del rapporto lavorativo. La separazione "dato aziendale / dato personale" è di fatto collassata.

Per tutte queste ragioni, la chat aziendale è il punto di superficie più ampio della comunicazione aziendale: quello dove avvengono più cose, in modo meno sorvegliato, con più dispersione. Risolvere la chat significa risolvere il 60-80% del problema "comunicazioni aziendali fuori controllo".

## 11.2 — Cosa fa Pulse

Pulse è progettato sul modello tecnico di Signal (Signal Protocol con Double Ratchet) ma con quattro adattamenti per uso aziendale.

**Adattamento 1 — Identità aziendali, non numeri di telefono.** In Pulse, gli utenti sono identificati dal loro LNS aziendale (`mario.acme.lns`), non da numeri di telefono personali. Una conversazione Pulse è sempre tra identità aziendali. Quando un dipendente lascia, la sua identità viene revocata: il sistema rifiuta automaticamente nuovi messaggi e segnala chiaramente alle controparti che il numero non è più attivo.

**Adattamento 2 — Crittografia post-quantum.** Lo scambio di chiavi del Double Ratchet usa ML-KEM-768 (al posto di X25519 di Signal). Tutte le chiavi e tutte le firme sono PQC.

**Adattamento 3 — Notarizzazione periodica on-chain.** Ogni 3 messaggi della conversazione, un "anchor hash" della stessa viene registrato come transazione QBFT sul ledger. Questo permette di dimostrare, in futuro, che una conversazione è esistita, quante volte è stata aggiornata, e che il suo stato non è stato manipolato retrospettivamente. Il contenuto resta privato.

**Adattamento 4 — Routing via mixnet Loopix.** Per nascondere chi parla con chi anche a osservatori interni, Pulse instrada i messaggi attraverso 3 hop di mixnet. Anche un sysadmin con accesso ai log del server di Lattice non può ricostruire le coppie mittente-destinatario.

## 11.3 — L'esperienza utente

Mario apre Pulse nel browser o dall'app mobile. Vede:

- **Lista delle sue conversazioni**, con badge di stato (attivo, archiviato, in attesa di risposta).
- **Indicatore di consegna e lettura** per ogni messaggio (consegnato / letto), come in Signal o WhatsApp.
- **Conferma di identità** del destinatario (badge verde se la sua chiave è verificata).
- **Banner "ancorato on-chain"** che lampeggia ogni 3 messaggi per ricordare visivamente che la conversazione è notarizzata.
- **Conversazioni di gruppo** (canali aziendali, gruppi di reparto) con la stessa cifratura end-to-end (PQXDH multi-party).
- **Allegati** (file fino a 100 MB) cifrati end-to-end.
- **Ricerca** nei messaggi (locale al dispositivo, non sul server — il server non vede il contenuto).
- **Notifiche** push, anch'esse "sealed sender" (non rivelano il mittente alla rete del telefono).

L'esperienza, per la maggior parte degli utenti, è "una chat moderna come Slack, ma più veloce e con un piccolo indicatore di sigillo dorato".

## 11.4 — Cosa Pulse risolve, concretamente

**Per il CISO.** Non c'è più "shadow IT" sulle chat. WhatsApp Business e similari si possono vietare con sicurezza, sapendo che esiste un'alternativa interna che soddisfa i bisogni operativi. La superficie di esposizione si riduce drasticamente.

**Per il legale.** Le conversazioni interne hanno valore probatorio: il sistema può, su richiesta giudiziaria documentata, fornire la chat completa (con consenso del giudice) o la prova della sua esistenza senza il contenuto. In una causa di lavoro, in un'inchiesta interna, in un'indagine antiriciclaggio, Pulse fornisce strumenti che Slack/Teams non offrono in modo nativo.

**Per il dipendente.** L'esperienza è migliore: cifratura by default, niente cookie tracker di Microsoft/Google, niente pubblicità, niente interruzioni "il tuo abbonamento sta scadendo". L'app è veloce, funziona offline, sincronizza su più dispositivi.

**Per l'azienda nel complesso.** La proprietà delle conversazioni è chiara: sono dell'azienda, sono cifrate, sono sui server dell'azienda. Quando il dipendente lascia, l'archivio resta — sotto la responsabilità del legale dell'azienda, non in mano al dipendente o al fornitore esterno.

## 11.5 — Quando Pulse, quando ancora no

Per onestà operativa, Pulse oggi (febbraio 2026) ha alcuni limiti che vale la pena nominare.

**Limite 1 — Voce/video non integrati.** Pulse al momento è testo + allegati. Per chiamate voce/video aziendali è necessario un sistema dedicato (es. Jitsi self-hosted, BigBlueButton). L'integrazione voce in Pulse è prevista per la roadmap 2026-2027 sull'estensione SFrame del Signal Protocol.

**Limite 2 — Bot e integrazioni.** Slack ha un ecosistema di migliaia di bot e integrazioni con sistemi terzi. Pulse, come piattaforma giovane, ha solo le integrazioni native con i moduli Lattice (Certify, LNS) e API REST per integrazioni custom. Per aziende che dipendono fortemente da bot Slack, la migrazione richiede valutazione caso per caso.

**Limite 3 — Numero di utenti.** Pulse è testato fino a 5.000 utenti per tenant. Per realtà sopra questa soglia, la configurazione richiede customizzazione (sharding, validatori multipli). Le aziende sopra i 5.000 dipendenti sono comunque una minoranza nel mercato italiano.

Per le PMI italiane (la maggior parte del tessuto produttivo), questi limiti sono irrilevanti. Per gruppi industriali grandi, vanno discussi in fase di pre-progettazione.

## 11.6 — Migrazione progressiva

Come per Certify (cap. 10.6), Pulse si presta a una migrazione progressiva piuttosto che a un cut-over secco.

**Mese 1.** Si attiva Pulse per il team di direzione (5-15 persone). Si verificano usabilità, performance, integrazione con Active Directory. Si misurano latenze.

**Mese 2-3.** Si estende a un reparto pilota (es. legale, commerciale, R&D — quello che ha più sensibilità sui dati). Si raccolgono feedback. Si aggiustano policy di retention.

**Mese 4-6.** Si estende all'intera azienda. Slack o Teams restano attivi in parallelo per integrazioni residue (bot, sistemi legacy) ma le conversazioni interne nuove vanno su Pulse.

**Mese 6-12.** Slack/Teams viene gradualmente ridotto a un uso secondario (canali pubblici, hub HR, knowledge base). Pulse è la chat principale.

L'esperienza dei clienti che hanno completato questa migrazione è che, dopo 6-9 mesi, l'80-90% della chat aziendale è su Pulse e nessuno desidera tornare indietro. La differenza percepita non è tanto la sicurezza (che è invisibile) quanto la velocità, l'assenza di interruzioni commerciali, e la sensazione concreta di possedere il proprio archivio.

## 11.7 — Domanda per il direttore HR

Portate questa domanda al direttore HR (o, in aziende piccole, al fondatore): **"Quante volte, negli ultimi sei mesi, ci siamo trovati a non poter dimostrare cosa era stato detto in una conversazione di lavoro perché era su WhatsApp personale del dipendente? E quante volte, allo stesso tempo, abbiamo dovuto ricostruire informazioni perse perché il dipendente uscente aveva il dispositivo?"**

La risposta tipica è "più di una". Pulse risolve esattamente questo: la chat è dell'azienda, sempre, anche quando il dipendente non c'è più.
