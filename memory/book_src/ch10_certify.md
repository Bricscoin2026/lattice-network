# CAPITOLO 10 — Certify: la posta con prova legale che funziona davvero.

## 10.0 — Apertura

Tutto il resto del libro converge qui: in **Certify**, il modulo di Lattice che gestisce la posta con valore legale. È il prodotto che sostituisce, contemporaneamente, le funzioni della PEC italiana, della mail business Microsoft 365 e dei servizi commerciali di firma digitale, con una promessa tecnica che nessuno di questi singolarmente offre: ogni mail è **firmata, cifrata, notarizzata, opponibile, verificabile pubblicamente**, e queste proprietà restano vere anche tra vent'anni, anche all'estero, anche se Lattice come azienda non esiste più.

Questo capitolo spiega cosa fa Certify, perché supera i limiti della PEC (capitolo 1.3), e come funziona dal punto di vista dell'utente e del legale.

## 10.1 — I quattro limiti della PEC, risolti

Ricapitoliamo i quattro limiti della PEC italiana e mettiamo a fianco la risposta di Certify.

[FIGURA 10.1 — Confronto PEC vs Certify]

**Limite 1 della PEC — Non vale all'estero.**
Una mail PEC verso una controparte tedesca o francese non ha valore legale specifico nei paesi di destinazione. La ricevuta che ricevi serve internamente in Italia, non in giudizio in Europa.

**Risposta di Certify.** Ogni mail Certify viene notarizzata sul ledger interno di Lattice con firma ML-DSA-65 e — opzionalmente — ancorata su Bitcoin via OpenTimestamps. La prova è **verificabile pubblicamente** dal Block Explorer (URL pubblico, accessibile da chiunque, in qualsiasi giurisdizione). La verifica è puramente crittografica: la controparte tedesca o francese ricalcola l'hash del documento ricevuto, confronta col Block Explorer, e ha la prova matematica che il documento è stato firmato in quella data da quella persona. Niente PEC, niente provider intermedio, niente confine giurisdizionale.

**Limite 2 della PEC — Non garantisce il contenuto.**
La PEC garantisce che la mail è stata consegnata, non che il contenuto è stato preservato integro. Se la mail viene modificata dopo l'invio (es. un dipendente disonesto modifica l'archivio Outlook), la PEC non lo rileva.

**Risposta di Certify.** L'hash SHA3-512 del contenuto viene calcolato al momento dell'invio e notarizzato on-chain. Qualsiasi modifica successiva del contenuto produce un hash diverso, che non corrisponde a quello registrato. La verifica dell'integrità è autonoma: il destinatario (o il giudice) ricalcola l'hash e confronta. Se coincidono, il contenuto è autenticamente quello originale.

**Limite 3 della PEC — Vivi e muori con il provider.**
La ricevuta PEC è verificabile finché il provider esiste e mantiene gli archivi. Se Aruba o InfoCert cambiano formato, cessano l'attività o vengono acquisite, la verifica diventa difficile o impossibile.

**Risposta di Certify.** La prova esiste sul ledger Lattice (immutabile, replicato su tutti i validatori della rete) e — opzionalmente — su Bitcoin. La durabilità non dipende da Lattice come azienda. Se Lattice fallisce, i validatori restano operativi presso le aziende che ne erano nodi (banche, notai, organi di vigilanza); l'archivio Bitcoin è gestito da decine di migliaia di nodi indipendenti in tutto il mondo. La verifica resta possibile per decenni.

**Limite 4 della PEC — Il provider vede tutto.**
Il provider PEC mantiene una copia in chiaro della mail per 30 mesi (per legge). Il personale del provider, in caso di incidenti o indagini, può accedervi.

**Risposta di Certify.** Il contenuto della mail Certify è cifrato end-to-end: mittente e destinatario lo vedono in chiaro, nessuno altro. Lattice come server vede solo l'hash del contenuto (non il contenuto stesso). Anche l'amministratore del sistema Lattice non può leggere le mail dei dipendenti. La privacy è garantita matematicamente, non contrattualmente.

## 10.2 — Cosa vede l'utente

Dal punto di vista di Mario, dipendente di Acme, Certify è semplicemente "la mia mail con valore legale". L'interfaccia è una mailbox web standard (componi, leggi, rispondi, allega), praticamente indistinguibile da Outlook o Gmail.

Sotto il cofano, succede quanto descritto nel capitolo 7.4. Mario non vede la complessità crittografica. Vede:

- Quando invia una mail, una piccola **icona di sigillo dorato** appare di fianco al messaggio per indicare che è notarizzata.
- Quando apre una mail in entrata, vede il **mittente verificato** (badge verde) e l'**ora certa** della firma.
- Cliccando su "Dettagli", può vedere: l'hash del documento, il numero di blocco di notarizzazione, l'eventuale ancora Bitcoin, un link al Block Explorer pubblico per la verifica.
- Per le mail "ufficiali" (oggetto contrattuale, allegato firmato), può richiedere una **ricevuta di apertura** che il destinatario firma all'apertura, generando un secondo evento on-chain.

Per la maggior parte dell'attività quotidiana, l'esperienza utente di Certify è "una mail normale, con l'aggiunta di un sigillo crittografico invisibile". Questo è voluto: la sicurezza deve essere by default, non un fastidio.

## 10.3 — Cosa vede il legale

Per l'ufficio legale dell'azienda o per un consulente esterno, Certify offre un livello di prova che è qualitativamente diverso da PEC, raccomandata, fax, o stampa di una Gmail.

**Per dimostrare l'invio di una mail in una certa data:**

1. Mostra la mail (o l'allegato) nel suo formato originale (file `.txt`, `.pdf`, ecc.).
2. Calcola l'hash SHA3-512 del file (comando standard: `sha3sum -a 512 file.pdf`).
3. Apri il Block Explorer pubblico di Lattice (URL pubblico, es. `https://explorer.lattice.network`).
4. Incolla l'hash nella ricerca.
5. Il Block Explorer mostra: numero di blocco, timestamp finalizzato, firma del mittente, identità LNS del mittente (es. `mario.rossi.acme.lns`) e del destinatario, eventuale ancora Bitcoin.

Il giudice, l'avvocato della controparte, il consulente tecnico d'ufficio possono ripetere autonomamente questa verifica. Non devono fidarsi di Lattice. Non devono fidarsi del cliente. La matematica è sufficiente.

**Per dimostrare l'apertura/lettura:**

L'evento `DeliveryReceipt` è anch'esso firmato dal destinatario al momento dell'apertura e registrato on-chain. La prova di "Paolo ha aperto questa mail il giorno X alle ore Y:Z" è verificabile come sopra.

**Per dimostrare la non-alterazione nel tempo:**

L'ancora Bitcoin (se attivata) certifica che l'hash della mail esisteva in una transazione Bitcoin con un certo blocco. Il blocco Bitcoin è verificabile da chiunque, in qualsiasi momento, indefinitamente. Per cause future a 10-20 anni di distanza, questa è la garanzia di sopravvivenza della prova.

## 10.4 — La "ricevuta legale" di Certify

Per le comunicazioni più importanti, Certify produce una **Ricevuta Legale** dedicata: un PDF formattato (firmato digitalmente con eIDAS-compatible signature) che contiene:

- Mittente, destinatario, oggetto, data, ora.
- Hash SHA3-512 del documento allegato.
- Firma ML-DSA-65 del mittente, in base64.
- Numero di blocco di notarizzazione + hash del blocco.
- Riferimento alla transazione Bitcoin di ancoraggio (se attivato).
- URL del Block Explorer per la verifica autonoma.
- Istruzioni in italiano + inglese per la verifica da parte di terzi.

Questo PDF è opponibile in giudizio in Italia come "documento informatico con firma elettronica qualificata" (Art. 21 CAD) e all'estero come "qualified electronic signature" ai sensi del Regolamento eIDAS 910/2014 (modificato eIDAS 2.0). Per le giurisdizioni extra-UE, la prova matematica intrinseca dell'hash + blockchain costituisce un elemento di forte presunzione di autenticità.

## 10.5 — Quando usare Certify e quando no

Per onestà, non tutte le mail aziendali hanno bisogno di Certify. Una richiesta interna di "puoi mandarmi il file X" non richiede notarizzazione on-chain.

Le categorie tipiche di mail che **dovrebbero** passare per Certify:

- Contratti, NDA, accordi commerciali.
- Offerte commerciali vincolanti.
- Comunicazioni del consiglio di amministrazione.
- Mail con valore probatorio (decisioni HR, sanzioni disciplinari, rotture contrattuali).
- Diffide e risposte a diffide.
- Notifiche legali (es. di scadenze contrattuali, di mancato pagamento).
- Trasmissione di documenti firmati (a PA, controparti, organi di vigilanza).
- Conferme di ordine ad alto valore.

Le mail che **non** richiedono Certify:

- Comunicazioni interne ordinarie.
- Mail di coordinamento operativo.
- Mail di richiesta informazioni non vincolanti.
- Newsletter, mail marketing.

Una buona pratica aziendale è etichettare le mail importanti come "Certify" già al momento dell'invio, con una policy chiara su quali categorie di mail vi rientrano. Lattice supporta questa segmentazione lato interfaccia utente.

## 10.6 — Migrazione dalla PEC esistente

Per le aziende italiane che hanno già una PEC attiva, la migrazione a Certify può essere progressiva:

**Mese 1-3.** Si attiva Certify in parallelo alla PEC. Le comunicazioni più strategiche (consiglio, M&A, contenziosi) passano già da Certify. La PEC resta per il resto.

**Mese 4-9.** Si forma il personale legale e amministrativo all'uso di Certify per la maggior parte delle comunicazioni con valore probatorio.

**Mese 10-12.** Si valuta se mantenere la PEC solo per comunicazioni verso PA italiane che la richiedono per legge, o se attivare un gateway PEC-Certify (Lattice ne fornisce uno opzionale).

**Anno 2.** Per la maggior parte dei clienti, la PEC viene ridotta al minimo necessario, mentre Certify diventa lo standard per le comunicazioni interne ed esterne con valore.

Il risparmio economico è significativo: una PEC business costa tra 50 e 300 euro/anno per casella. Per un'azienda di 50 dipendenti con 30 caselle PEC, parliamo di 3.000-10.000 euro/anno. Certify ha un costo a fascia di dipendenti molto più favorevole e — più importante — copre la chat, gli archivi documentali, e l'audit, non solo la mail.

## 10.7 — Domanda per il legale aziendale

Portate questa domanda al vostro ufficio legale o al consulente esterno: **"Se dovessimo dimostrare in giudizio, fra 7 anni, che una mail importante è stata effettivamente inviata da Mario in una certa data con un certo contenuto, quanto tempo, denaro e dipendenza dal fornitore ci costerebbe oggi, e quanto con Certify?"**

Tipicamente la risposta del legale è "settimane di lavoro e dipendenza totale da Microsoft/Aruba". Con Certify: trenta secondi sul Block Explorer.
