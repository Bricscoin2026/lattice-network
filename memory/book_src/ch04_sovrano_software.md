# CAPITOLO 4 — Cosa significa davvero "sovrano" nel software.

## 4.0 — Apertura

La parola "sovrano" è diventata, negli ultimi cinque anni, una delle più abusate del marketing tecnologico italiano. C'è il "cloud sovrano", il "datacenter sovrano", la "PEC sovrana", la "AI sovrana". Ogni grande fornitore — anche quelli più estranei al concetto — ha ormai una linea di prodotto etichettata in questo modo, di solito a margine di una vera offerta basata su tecnologie americane o cinesi semplicemente rietichettate per il mercato europeo.

Per un CEO che deve decidere se affidare le comunicazioni aziendali a un fornitore "sovrano", è cruciale poter distinguere ciò che è veramente sotto controllo da ciò che è marketing. Questo capitolo propone uno strumento operativo per farlo: **sei dimensioni della sovranità**, ciascuna verificabile in modo concreto, applicabili a qualsiasi piattaforma software che gestisca comunicazioni aziendali.

## 4.1 — Le sei dimensioni della sovranità

[FIGURA 4.1 — Le sei dimensioni della sovranità del software]

**Sovranità del codice.** Il codice sorgente della piattaforma è pubblicamente ispezionabile o, almeno, contrattualmente accessibile? Hai modo di farlo auditare da un terzo di tua scelta? Le modifiche al codice sono tracciate in modo verificabile (commit firmati, audit pubblico) o restano nella scatola del fornitore? Un fornitore "sovrano" ma con codice chiuso non audibile è un ossimoro.

**Sovranità dei dati.** I dati gestiti dalla piattaforma sono fisicamente in territorio che la tua azienda controlla (on-premise) o, almeno, in un territorio giurisdizionale che escluda l'esposizione a regimi extra-UE (CLOUD Act, Executive Orders, NSL)? La criptazione at-rest e in-transit è applicata con chiavi che la tua azienda possiede o con chiavi del fornitore? Se il fornitore può tecnicamente accedere ai tuoi dati, non sono sovrani.

**Sovranità delle chiavi.** Le chiavi crittografiche delle identità aziendali (mittenti, destinatari, gateway) sono generate sui tuoi dispositivi o sui server del fornitore? Le chiavi possono essere esportate, riportate, revocate, ruotate da te senza dover chiedere il permesso a nessuno? In quale forma vengono conservate? Questa è probabilmente la dimensione più importante e più frequentemente disattesa.

**Sovranità dell'infrastruttura.** Le macchine fisiche, i datacenter, le reti di interconnessione sono sotto controllo della tua azienda o di terzi? Quali terzi (Microsoft Azure, AWS, Google Cloud, OVH, Aruba, Seeweb)? In quale giurisdizione operano? Le clausole contrattuali ti garantiscono la portabilità immediata in caso di rescissione? Spoiler: spesso non lo fanno.

**Sovranità degli aggiornamenti.** Chi decide quando e come la piattaforma viene aggiornata? Hai la facoltà di rifiutare un aggiornamento che modifica il modello di sicurezza? Gli aggiornamenti sono firmati da una chiave che riconosci come legittima? In ambito enterprise, gli aggiornamenti automatici imposti dal fornitore sono uno dei vettori più comuni di compromissione (vedi SolarWinds 2020).

**Sovranità della catena di fornitura.** Le librerie, i compilatori, i pacchetti software utilizzati per costruire la piattaforma vengono da fonti che la tua azienda controlla? La build è riproducibile (chiunque, dato lo stesso codice, ottiene lo stesso binario)? I rilasci sono firmati e verificabili pubblicamente? È un livello di paranoia che pochi clienti italiani richiedono, ma per chi gestisce dati realmente strategici è imprescindibile.

## 4.2 — Come Lattice si misura sulle sei dimensioni

Vediamo, in modo trasparente, come Lattice si posiziona su ciascuna.

**Codice.** Il core di Lattice è open source con licenza BSL 1.1 (Business Source License), che consente l'ispezione e l'audit da parte di chiunque. Le componenti commerciali (gateway PEC court-grade, ancoraggio Bitcoin opzionale, dashboard avanzata enterprise) sono chiuse ma soggette a una clausola di "source code escrow": il codice è depositato presso un notaio europeo e accessibile al cliente in caso di cessazione dell'azienda o di violazione del contratto. Verificabile: il commit hash di ogni rilascio è pubblicato nel Block Explorer.

**Dati.** Lattice gira on-premise (sui tuoi server fisici) o in un cloud sovrano europeo che hai scelto tu (OVH, Hetzner, Aruba, partner che la tua azienda audita). I dati a riposo sono cifrati con AES-256-GCM e una chiave di "envelope" derivata da una passphrase amministrativa Argon2id. Lattice come azienda non ha accesso ai contenuti — nemmeno tecnicamente.

**Chiavi.** Le chiavi segrete dei singoli utenti vengono generate localmente nel loro browser durante l'onboarding e consegnate solo all'utente in un file `.keypair.json`. Il backend non ne conserva copia. La chiave di gateway aziendale (`CERTIFY-GATEWAY-{tenant_id}`) viene generata localmente al momento del setup e conservata sul tuo server. Il recupero in caso di perdita avviene via Shamir Secret Sharing a soglia 2-di-3, con guardiani che scegli tu.

**Infrastruttura.** Tu scegli i server. Lattice fornisce il software, le istruzioni di setup, e — opzionalmente — il supporto operativo. Non fornisce hosting. Questa è una scelta consapevole: il momento in cui Lattice gestisse anche l'hosting, la sovranità dell'infrastruttura passerebbe in larga misura nelle nostre mani, e saremmo noi a essere un nuovo "fornitore unico" come quelli che critichiamo.

**Aggiornamenti.** Lattice rilascia aggiornamenti firmati con una chiave ML-DSA-65 pubblica, verificabile. Tu decidi quando installarli. Non c'è auto-update forzato. Esiste un canale "security advisories" per gli aggiornamenti critici, ma anche questi devono essere applicati da te.

**Catena di fornitura.** Lattice è scritto in Rust (per le componenti crittografiche) e Python (per il backend FastAPI). Le librerie crittografiche utilizzate sono quelle di riferimento del NIST (PQClean, libsodium, ring), tutte open source ispezionabili. La build è riproducibile su qualunque macchina Linux/macOS. Il binario di rilascio ha un hash SHA-256 pubblicato e firmato.

## 4.3 — Sovranità di concetto vs sovranità di marketing

Ci sono fornitori — anche italiani — che si presentano come "sovrani" ma soddisfano solo una o due delle sei dimensioni. Vale la pena dare alcuni esempi anonimi per allenare l'occhio.

**Esempio 1.** Provider PEC italiano che ospita su Azure (datacenter in Irlanda). Sovranità dei dati: ridotta (Microsoft può tecnicamente accedere). Sovranità dell'infrastruttura: zero (l'hosting è di Microsoft). Sovranità delle chiavi: zero (le chiavi sono del provider, non del cliente). Marketing: "PEC italiana sovrana".

**Esempio 2.** Cloud "sovrano europeo" che è in realtà una rivendita di Google Cloud con una clausola contrattuale sulle giurisdizioni. Sovranità del codice: zero. Sovranità dell'infrastruttura: nominale. Sovranità delle chiavi: gestita dal provider. Marketing: "cloud sovrano".

**Esempio 3.** Piattaforma di messaggistica "made in Italy" che usa server Microsoft Azure West Europe, codice chiuso, chiavi gestite dal provider. Soddisfa la dimensione "dati nominalmente in Europa", nient'altro. Marketing: "messaggistica sovrana italiana".

Il punto non è demonizzare questi prodotti. Il punto è capire che "sovrano" senza specificazione tecnica non vuol dire niente. La sei-dimensioni è uno strumento di valutazione che un CISO può applicare in fase di RFP per separare le proposte serie da quelle puramente di marketing.

## 4.4 — La sovranità non è solo per le aziende paranoiche

C'è un'obiezione tipica al ragionamento sulla sovranità: "Ma sono cose da governi, da intelligence, da settori critici. La mia azienda media non ne ha bisogno". Vale la pena rispondere brevemente.

Primo: la sovranità è cumulativa. Più cose dipendono dallo stesso fornitore, più una sua compromissione propaga danno. Un'azienda media che ha mail su Microsoft, chat su Microsoft Teams, archivio su OneDrive, autenticazione su Azure AD e backup su Microsoft Azure ha — in pratica — un unico point of failure per l'intera capacità di operare. La sua "non paranoia" è un'esposizione strutturale.

Secondo: i regolatori, in Europa e in Italia, stanno spostando l'attenzione verso il requisito di sovranità anche per le aziende ordinarie. NIS2 richiede misure di resilienza che, di fatto, presuppongono alternative di emergenza al fornitore primario. DORA impone, per il settore finanziario, una mappatura completa delle dipendenze ICT con piano di sostituzione. eIDAS 2.0 spinge verso identità digitali europee non controllate da fornitori americani.

Terzo: il differenziale di costo tra una soluzione "ovunque sia il fornitore" e una soluzione sovrana si è ridotto drasticamente. Lattice, on-premise, ha un costo total cost of ownership confrontabile a quello di Microsoft 365 per aziende medie, ed è significativamente più basso per aziende sopra i 200 dipendenti.

Per chi vuole approfondire il calcolo TCO, c'è il capitolo 13. Per ora, prendete questo: la sovranità non è più un costo aggiuntivo da CISO paranoici, è una condizione di operatività normale per il 2026.

## 4.5 — Domanda per la prossima riunione

Portate questa domanda al prossimo CdA: **"Su quante delle sei dimensioni — codice, dati, chiavi, infrastruttura, aggiornamenti, catena di fornitura — abbiamo controllo effettivo per la nostra infrastruttura di comunicazione?"**

Se la risposta è "zero o una", siete dipendenti totali. Se è "due o tre", siete dipendenti con qualche margine di manovra. Se è "quattro o più", complimenti — siete tra le poche aziende italiane veramente sovrane.
