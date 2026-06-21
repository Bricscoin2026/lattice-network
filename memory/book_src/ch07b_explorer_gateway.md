# CAPITOLO 7B — Block Explorer pubblico e Gateway Delegation.

*Due caratteristiche tecniche specifiche di Lattice che valgono un capitolo a parte, perché toccano due domande operative ricorrenti: "come dimostro a un terzo che la mail esiste davvero?" e "come fa un dipendente a firmare on-chain senza che il backend tenga la sua chiave?".*

## 7B.1 — Il Block Explorer pubblico: la prova senza fornitore

Una delle proprietà più importanti di Lattice, e una di quelle che la differenzia in modo netto dalle alternative SaaS, è che **chiunque, in qualsiasi momento, può verificare la validità di una transazione, di un blocco o dell'hash di un documento, senza dover passare attraverso il fornitore.**

Questa proprietà si materializza in uno strumento concreto chiamato **Block Explorer**. È un'applicazione web pubblica, accessibile da qualsiasi browser senza autenticazione, che mostra in tempo reale lo stato del ledger interno di Lattice: i blocchi finalizzati, le transazioni registrate, le identità (LNS) attive e revocate, le notarizzazioni di mail e documenti.

### A cosa serve, in pratica

Immagina questo scenario. La tua azienda, due anni fa, ha inviato un'offerta vincolante a un cliente via Lattice Certify. Il cliente, oggi, contesta il contenuto dell'offerta sostenendo che è stata "modificata dopo l'invio". Nella prassi italiana, questo significherebbe attivare un consulente tecnico d'ufficio che verifichi gli archivi del provider di posta. Se il provider non esiste più, o ha cambiato formato, o richiede tempi lunghi, la verifica diventa difficile.

Con Lattice, il procedimento è molto più diretto. Tu (o il giudice, o l'avvocato della controparte, o il consulente tecnico) apri il Block Explorer pubblico di Lattice, cerchi l'identificativo della mail (un hash SHA3-512 di 128 caratteri esadecimali) e ottieni una pagina con queste informazioni:

- **Hash del documento**: l'impronta crittografica del contenuto originale. Se ricalcoli l'hash della mail che tieni in archivio e ottieni lo stesso valore, hai dimostrato matematicamente che il contenuto non è stato modificato.
- **Firma digitale del mittente**: la firma ML-DSA-65 (post-quantum) applicata dalla chiave segreta del mittente al momento dell'invio. Se la verifica passa, hai dimostrato che il mittente è davvero la persona che dici.
- **Blocco e timestamp di notarizzazione**: il numero del blocco in cui la transazione è stata finalizzata, e il momento esatto (al secondo) in cui questo è avvenuto. Questo timestamp è opponibile in giudizio come ora certa, perché è stato concordato dai validatori QBFT che hanno firmato quel blocco — nessun singolo soggetto può alterarlo retroattivamente.
- **Ancoraggio esterno (opzionale)**: se la transazione è stata anche ancorata su Bitcoin tramite OpenTimestamps (vedi sezione 7B.3), il riferimento alla transazione Bitcoin è qui. Significa che la prova non dipende più nemmeno dalla rete Lattice: dipende dalla rete Bitcoin, che è una rete pubblica globale gestita da decine di migliaia di nodi indipendenti.

Tutto questo è verificabile **senza chiamare nessuno**. Senza dover credere a Lattice. Senza dover credere al provider PEC. La verifica è autonoma e crittografica.

### Cosa è pubblicamente visibile e cosa no

Una preoccupazione legittima dei clienti aziendali, in fase di valutazione, è: "Ma allora chiunque può leggere le mie mail nel Block Explorer?". **No, e questa è una distinzione critica.**

Il Block Explorer mostra solo l'**hash crittografico** del documento — un numero di 128 caratteri esadecimali che funge da "impronta" — non il contenuto. L'hash è una funzione unidirezionale: a partire dall'hash, è impossibile ricostruire il contenuto originale. Quello che la chain conserva è:

- L'hash del documento (impronta) — pubblico.
- L'identità del mittente in formato LNS (es. `mario.rossi.acme.lns`) — pubblico.
- L'identità del destinatario in formato LNS — pubblico.
- Il timestamp di notarizzazione — pubblico.
- La firma digitale — pubblica.
- **Il contenuto della mail e degli allegati — privato**, conservato cifrato sui server di Lattice della tua azienda, accessibile solo a mittente e destinatario.

Questo modello — *publish the proof, hide the payload* — è lo stesso adottato da OpenTimestamps su Bitcoin, da DocuSign per le firme digitali, da Certificate Transparency per i certificati TLS. È un modello consolidato.

Per i clienti che richiedono un livello superiore di riservatezza (es. studi legali con clientela ad alto profilo), Lattice offre un'opzione di **anonimizzazione delle identità on-chain**: invece di pubblicare `mario.rossi.acme.lns`, pubblica un hash dell'LNS che è verificabile solo da chi conosce la chiave. La proprietà di non-ripudio è preservata, ma la corrispondenza mittente-destinatario non è leggibile pubblicamente.

### Per il pubblico esterno: l'audit pubblico aziende

Oltre al Block Explorer di basso livello (transazioni e blocchi), Lattice offre un'interfaccia di livello superiore chiamata **Audit Pubblico** che mostra, per ogni azienda registrata sulla rete, alcune metriche aggregate:

- Numero di identità attive.
- Numero di mail certificate negli ultimi 30 giorni.
- Numero di messaggi Pulse scambiati.
- Eventuali eventi di revoca (con motivazione anonimizzata).
- Indicatore di salute della rete (validatori online, ultima ancora Bitcoin, eccetera).

Questa interfaccia non rivela contenuti né identità individuali, ma fornisce a un eventuale ispettore, certificatore o controparte un'idea immediata dell'attività e della governance della rete. È particolarmente utile per le aziende regolamentate (banche, assicurazioni) che devono dimostrare ai propri auditor che le comunicazioni interne sono effettivamente tracciate.

## 7B.2 — Gateway Delegation: come firmano i dipendenti

Una sfida ricorrente nelle infrastrutture di firma digitale è: **come fa un dipendente che ha perso il laptop, o che è in mobilità, a firmare un documento on-chain senza che le sue chiavi private siano memorizzate sul server?**

La risposta della maggior parte delle soluzioni commerciali è: "Le chiavi sono sul server, in cifratura at-rest". Questa risposta sembra ragionevole ma è insoddisfacente. Se il server è compromesso, le chiavi sono compromesse. Se il fornitore è obbligato per legge a consegnare le chiavi (CLOUD Act, ordinanza giudiziale), le chiavi sono consegnate. Se il provider chiude, le chiavi spariscono.

Lattice adotta un'architettura diversa, chiamata **Gateway Delegation**, che mantiene una proprietà fondamentale: **la chiave segreta dei singoli dipendenti non lascia mai i loro dispositivi**. Il backend di Lattice non ha mai accesso alla chiave segreta di Mario Rossi, neppure in forma cifrata.

### Come funziona

Ogni azienda registrata su Lattice possiede una propria chiave di gateway: `CERTIFY-GATEWAY-{tenant_id}`. Questa è una chiave ML-DSA-65 (post-quantum) emessa al momento dell'onboarding dell'azienda, conservata sul backend di Lattice e usata per firmare on-chain le transazioni che riguardano l'attività dei dipendenti.

Quando Mario Rossi vuole inviare una mail Certify, succede questo:

1. Mario compone la mail nel suo browser. Il contenuto resta nel suo browser.
2. Mario clicca "invia". Il browser calcola localmente l'hash SHA3-512 del contenuto.
3. Il browser firma l'hash con la chiave segreta di Mario (`mario.rossi.acme.lns.sk`). La firma dimostra che il contenuto proviene da Mario. **La chiave segreta non lascia il browser.**
4. Il browser invia al backend di Lattice: il contenuto cifrato, l'hash, la firma di Mario.
5. Il backend di Lattice verifica la firma di Mario (usando la chiave pubblica di Mario, che è registrata on-chain).
6. Se la verifica passa, il backend costruisce una transazione "NotarySeal" che contiene: hash del documento, identità di Mario, identità del destinatario, firma di Mario, timestamp.
7. Il backend firma questa transazione con la chiave di gateway dell'azienda di Mario (`CERTIFY-GATEWAY-acme.lns`).
8. La transazione viene inviata ai validatori QBFT che la finalizzano in un nuovo blocco.

Il risultato è una transazione che ha **due firme**:

- La firma di Mario, che prova "questo contenuto è di Mario".
- La firma del gateway aziendale, che prova "questa transazione è stata correttamente ricevuta e processata dall'infrastruttura aziendale, secondo le policy dell'azienda".

### Perché è importante questa separazione

La separazione tra "firma del dipendente" e "firma del gateway" risolve diversi problemi insieme.

**Per la sicurezza individuale.** Il backend non ha mai la chiave segreta di Mario. Se il backend è compromesso, l'attaccante non può impersonare Mario. Può, al massimo, costruire transazioni non firmate da Mario — ma queste verrebbero rifiutate dai validatori perché la firma di Mario sarebbe assente o falsa.

**Per il non-ripudio individuale.** Mario non può dire "non sono stato io" perché c'è la sua firma, applicata dalla sua chiave segreta che non ha mai lasciato il suo browser. Diversamente da Microsoft 365 (dove il fornitore potrebbe, in linea di principio, generare una mail "da Mario" senza la sua partecipazione), qui il fornitore non ha questa capacità.

**Per il controllo aziendale.** Allo stesso tempo, l'azienda mantiene il controllo: se Mario viene compromesso (ad esempio, viene revocato dall'azienda), tutte le firme future con la sua chiave verranno rifiutate dal sistema — perché il gateway aziendale controlla, prima di apporre la propria firma, che la chiave del mittente sia ancora attiva nel registro LNS.

**Per la mobilità.** Mario può firmare da qualunque dispositivo a patto di avere la sua chiave segreta. La chiave segreta è in un file `.keypair.json` che lui custodisce. Se la perde, c'è il **Key Recovery via Shamir Secret Sharing** (vedi capitolo 8).

### Cosa succede se il dipendente perde la chiave

Se Mario perde il file `.keypair.json` (laptop rubato, telefono perso, distruzione accidentale), non può più firmare. **Nessuno può impersonarlo**, neppure l'azienda — questa è una proprietà voluta.

Per recuperare l'accesso, Mario passa attraverso un procedimento di **Shamir Secret Sharing**: al momento dell'enrolment, il founder dell'azienda di Mario ha nominato tre "guardiani" (tipicamente: il founder stesso, un dirigente di fiducia, un avvocato esterno). Quando Mario chiede il recupero, due dei tre guardiani devono cooperare per ricostruire la chiave. Il procedimento è tracciato on-chain (richiesta, contributo dei guardiani, finalizzazione) ed è verificabile pubblicamente nel Block Explorer.

Se Mario non perde la chiave ma viene compromesso (esce dall'azienda in conflitto, sospetto di esfiltrazione), il founder non lo "recupera" — lo **revoca**: emette una transazione `IdentityRevoke` che dichiara la chiave di Mario non più valida dal blocco N in avanti. Il gateway aziendale, da quel momento, rifiuta ogni transazione firmata con la chiave di Mario. Le firme passate restano valide e verificabili (Mario *aveva* il diritto di firmare al momento in cui l'ha fatto), ma le future no.

Questa distinzione tra "recupero" (chi ha perso la chiave) e "revoca" (chi ha tradito) è gestita esplicitamente da Lattice in due flussi separati nell'interfaccia utente. Non è un dettaglio cosmetico: legalmente è la differenza tra un evento accidentale (per cui esiste un protocollo di recovery firmato) e un evento disciplinare (per cui esiste una decisione amministrativa firmata dal founder).

## 7B.3 — Ancoraggio Bitcoin (opzionale)

Per i clienti che richiedono un livello di durabilità superiore — tipicamente: studi legali con archivi che devono valere oltre la vita del fornitore, banche con archivi regolatori a 10+ anni, ricerca farmaceutica con brevetti — Lattice offre un'opzione di **ancoraggio Bitcoin** tramite il protocollo OpenTimestamps.

Funziona così: ogni 24 ore (o ogni N blocchi, configurabile per cliente), Lattice calcola un hash riassuntivo (Merkle root) di tutte le transazioni notarizzate in quel periodo. Questo hash, di 32 byte, viene inserito in una transazione Bitcoin tramite OpenTimestamps. La transazione Bitcoin è gratuita per Lattice (OpenTimestamps aggrega migliaia di prove in una sola transazione condivisa) e ha una latenza tipica di 1-6 ore prima di essere confermata su Bitcoin.

A confermazione avvenuta, ogni transazione Lattice "ancorata" diventa **opponibile anche se la rete Lattice cessasse di esistere**: la prova dell'esistenza di quella mail in quella data è ora registrata sulla blockchain Bitcoin, che è una rete pubblica globale gestita da decine di migliaia di nodi indipendenti e che, ragionevolmente, esisterà per molti decenni a venire.

Per il cliente questo significa una cosa molto concreta: **la durabilità della prova non dipende più da Lattice come azienda**. Se Lattice domani fallisse, se i suoi server fossero distrutti, se il codice fosse abbandonato, la prova matematica che quella tua mail è stata firmata in quella data resterebbe verificabile tramite il Block Explorer di Bitcoin e il client OpenTimestamps (entrambi open source, indipendenti, gestiti da comunità separate).

Questa opzione si attiva con un flag in configurazione e ha un costo aggiuntivo trascurabile (frazioni di euro per transazione Bitcoin, ammortizzati su migliaia di notarizzazioni Lattice). È raccomandata per tutti i clienti regolamentati.

## 7B.4 — In sintesi

Le due caratteristiche descritte in questo capitolo — Block Explorer pubblico e Gateway Delegation — sono ciò che rende Lattice **operativamente diverso** da un sistema di posta certificata commerciale o da un servizio mail aziendale tradizionale.

Il Block Explorer trasforma "credimi sulla parola" in "verifica con la matematica". Chiunque, in qualsiasi momento, in qualsiasi giurisdizione, può verificare l'integrità di una transazione Lattice senza dover passare per Lattice stessa. È la stessa proprietà che ha reso Bitcoin uno strumento legale opponibile in molti paesi: non perché qualcuno garantisca, ma perché chiunque può controllare.

Il Gateway Delegation risolve la tensione tra "le chiavi non devono lasciare il dispositivo dell'utente" e "l'azienda deve poter controllare le comunicazioni aziendali". Lo risolve introducendo due firme distinte — quella personale del dipendente, quella istituzionale del gateway aziendale — entrambe verificabili separatamente, ciascuna con il suo ruolo specifico.

Sono dettagli tecnici che, alla fine, si traducono in una proprietà di business molto semplice: **quando un cliente, un giudice o un'autorità ti chiede una prova, la mostri direttamente dal Block Explorer, in trenta secondi, senza chiamare nessuno**. Per chi gestisce comunicazioni con valore legale, questa è una differenza fondamentale.
