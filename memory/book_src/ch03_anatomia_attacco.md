# CAPITOLO 3 — Anatomia di una compromissione delle comunicazioni aziendali.

## 3.0 — Apertura

Nel capitolo 1 abbiamo descritto le dipendenze. Nel capitolo 2 il contesto italiano. Adesso guardiamo da vicino come, in pratica, una compromissione delle comunicazioni aziendali avviene davvero. Non lo scenario fantascientifico di un computer quantistico futuro — lo scenario reale, già accaduto a decine di aziende italiane negli ultimi cinque anni.

Ne descriviamo quattro: la sospensione del fornitore, l'attacco al fornitore stesso, la fuga di dati di un dipendente uscente, l'intercettazione passiva a lungo termine ("Harvest Now, Decrypt Later"). Per ciascuno, mostriamo come si svolge, cosa lascia di tracciabile, e cosa Lattice cambia.

## 3.1 — Scenario A — Sospensione del fornitore

**Il fatto.** Un mattino l'azienda non riesce più a inviare mail. Outlook restituisce errori di autenticazione. Il portale Microsoft 365 admin mostra il tenant in stato "Suspended — pending review". La causa è raramente un attacco informatico vero: nella casistica reale è più spesso un falso positivo dei sistemi automatici di abuse detection, una controversia su sanzioni internazionali, una contestazione contabile (fattura non pagata, billing dispute), o — più raramente — un'azione giudiziaria su istanza di un'autorità.

**Cosa succede operativamente.** Le mail in ingresso vengono respinte. Le caselle interne non si aprono. OneDrive non sincronizza più. Teams non si connette. Il supporto Microsoft (Premier per chi ha l'abbonamento, altrimenti Standard) impiega tra 4 e 48 ore per la prima risposta. La risoluzione completa, in media, richiede tra 24 e 72 ore.

**Il danno.** Per un'azienda media italiana (50-200 dipendenti, B2B) il danno diretto in fatturato è stimato tra 2 e 8 ore di operatività persa, più il danno reputazionale verso i clienti che non ricevono risposte tempestive, più il costo del personale fermo. Tipicamente parliamo di un impatto tra 25.000 e 150.000 euro per evento.

**La traccia.** Microsoft, dopo la risoluzione, fornisce un'email di "incident report" che generalmente non spiega in dettaglio cosa è successo. Le tue mail di quel periodo (eventuali tentativi di invio falliti) non sono recuperabili a meno che il tuo mail client locale (Outlook desktop) ne abbia conservato una copia. Le chat Teams di quel periodo, invece, sono effettivamente perse — Microsoft archivia le conversazioni in tempo reale e una sospensione del tenant cancella la finestra di scrittura.

**Cosa cambia con Lattice.** Lattice gira sui tuoi server (o in un cloud sovrano dedicato). Nessun fornitore esterno può sospenderlo. Per le comunicazioni con l'esterno (mail SMTP standard), Lattice può funzionare con un gateway intermedio: se quello esterno viene sospeso, Lattice continua a operare e accumula la coda di invio fino a quando il gateway non è ripristinato o sostituito. La sospensione del fornitore esterno diventa un fastidio, non un blocco totale.

## 3.2 — Scenario B — Attacco al fornitore

**Il fatto.** Il fornitore stesso viene compromesso. Esempi reali: violazione SolarWinds 2020 (che ha colpito anche Microsoft via aggiornamenti firmware), incidente Microsoft Exchange Online del luglio 2023 (Storm-0558, un gruppo cinese che ha avuto accesso alle mail di 25 organizzazioni governative occidentali tramite chiavi di firma trapelate), violazione Okta del 2022. In tutti questi casi, l'azienda cliente non aveva fatto nulla di sbagliato: era il fornitore a essere compromesso.

**Cosa succede operativamente.** L'azienda di solito non si accorge di niente in tempo reale. La compromissione viene scoperta dal fornitore stesso settimane o mesi dopo, e comunicata via avviso di sicurezza. Nel caso Storm-0558, alcune mail rubate sono comparse pubblicamente; in altri casi (es. SolarWinds) il danno è stato perlopiù di spionaggio occulto.

**Il danno.** È difficile da quantificare a priori. Per un'azienda con dati strategici (segreti industriali, M&A in corso, brevetti) il danno può essere materiale e non recuperabile. Per un'azienda con dati ordinari, il danno è più reputazionale (notifica obbligatoria GDPR Art. 33 se sono coinvolti dati personali) e di sforzo legale.

**La traccia.** Generalmente il fornitore fornisce indicazioni generiche su quali tenant sono stati toccati e quali dati ipoteticamente esposti, senza dettagli verificabili. Il cliente deve fidarsi della ricostruzione del fornitore.

**Cosa cambia con Lattice.** Lattice riduce la superficie di attacco perché elimina il fornitore intermedio. Il tuo ledger interno, le tue mail Certify, la tua chat Pulse girano su nodi che la tua azienda controlla. Un attacco a Lattice come azienda software (che scoprisse, ipoteticamente, una vulnerabilità nel codice) non ha conseguenze immediate finché il tuo nodo non è connesso a Internet con privilegi di amministrazione. Lattice è auditabile in codice sorgente: il rischio della "porta segreta" che un fornitore commerciale potrebbe aver lasciato in firma a un'agenzia di sicurezza estera è teoricamente eliminato.

## 3.3 — Scenario C — Il dipendente uscente

**Il fatto.** Il caso più frequente in assoluto, e quello che pochi consigli di amministrazione discutono in modo esplicito. Un dipendente con accesso a comunicazioni strategiche — un commerciale con la lista clienti, un avvocato d'azienda con i contenziosi in corso, un manager con la roadmap di prodotto — lascia l'azienda, in modo concordato o conflittuale, portando con sé copia di mail, allegati, chat. Tipicamente: download massivo nel mese precedente alle dimissioni, forward selettivo a casella personale, screenshot di chat sensibili.

**Cosa succede operativamente.** Nel modello Microsoft 365 / Google Workspace standard, il dipendente in fase di uscita ha accesso pieno fino al giorno della revoca. La revoca, anche quando immediata, non cancella retroattivamente i dati già scaricati sui suoi dispositivi personali (telefono privato sincronizzato, portatile non aziendale, NAS di casa). Le copie già esfiltrate restano fuori dal perimetro della tua azienda.

**Il danno.** Variabile e raramente immediato. Si materializza mesi o anni dopo: una proposta concorrenziale a un cliente con dettagli che solo l'ex dipendente poteva conoscere, una causa di lavoro con allegate mail interne, una fuga di trattative su giornali specializzati. La quantificazione del danno è quasi sempre contestata in giudizio.

**La traccia.** Microsoft e Google forniscono audit log degli ultimi 90-180 giorni che mostrano accessi, download e forward. Sono utilizzabili in giudizio ma con due limiti: (a) l'integrità del log dipende dal fornitore (che è giudice e parte), (b) il log non prova che le copie esfiltrate erano "originali" — il consulente tecnico di parte dell'ex dipendente può sempre sostenere che le mail sono state modificate dopo lo scaricamento.

**Cosa cambia con Lattice.** Ogni mail Lattice è firmata crittograficamente dal mittente al momento dell'invio. Una copia esfiltrata mantiene la firma originale: se il giudice chiede "questa mail è davvero stata scritta da Mario in quella data?", la risposta è verificabile dal Block Explorer, indipendentemente dalla cooperazione dell'ex dipendente o di un fornitore. Inoltre, la revoca dell'identità è immediata e definitiva: dal blocco N in avanti, ogni transazione firmata con la sua chiave viene rifiutata. Il dipendente non può più, dopo l'uscita, inviare mail "da dipendente" facendosi passare per l'azienda.

## 3.4 — Scenario D — Harvest Now, Decrypt Later

**Il fatto.** Lo scenario di lungo termine. Un attaccante con risorse statali — un'intelligence estera, un gruppo APT collegato a uno Stato — intercetta passivamente il traffico cifrato dell'azienda da anni. Non decifra in tempo reale: archivia. Quando, tra cinque o quindici anni, avrà un computer quantistico di capacità criptanaliticamente rilevante, decifrerà retroattivamente l'intero archivio.

**Cosa succede operativamente.** Niente, oggi. L'azienda non si accorge di nulla, perché l'intercettazione passiva non lascia tracce sui sistemi della vittima. È un'operazione di puro storage da parte dell'attaccante.

**Il danno.** Differito ma potenzialmente totale. Quando i dati vengono decifrati, l'attaccante (o chi li compra) può ricattare l'azienda, esporre comunicazioni interne, contestare contratti, pubblicare segreti industriali. Per organizzazioni con dati che hanno valore a 10-30 anni (banche, sanità, farmaceutica, ricerca, difesa, intelligence) questo è il rischio più consequenziale di tutti.

**La traccia.** Nessuna, fino al momento della decifrazione. Quando avviene, la traccia è il fatto stesso che i dati sono noti.

**Cosa cambia con Lattice.** Lattice è l'unico tra gli strumenti citati in questo libro che adotta nativamente, fin dal primo giorno, crittografia post-quantistica conforme NIST FIPS 203/204. Tutte le mail Certify, tutte le chat Pulse, tutte le firme on-chain sono protette con algoritmi che il computer quantistico non rompe. Il traffico Lattice intercettato oggi, archiviato per quindici anni, e decifrato con un computer quantistico nel 2041, **resta cifrato**. Questo è il valore tecnico distintivo di Lattice nei confronti dell'HNDL ed è dettagliato nel capitolo 8.

## 3.5 — Il punto in comune

I quattro scenari sono diversi tra loro ma hanno una proprietà in comune: in tutti e quattro, la tua azienda **dipende** da un soggetto terzo (fornitore, dipendente, fornitore-di-fornitori, intelligence estera) per la propria capacità di operare e di proteggere ciò che conta. In tutti e quattro, Lattice riduce drasticamente la dipendenza spostando il controllo dove deve essere: nelle mani di chi sopporta il rischio.

Questo è il senso di "Corporate Communication Control Layer". Non un acronimo tecnico. Un cambio di chi tiene la chiave.

## 3.6 — Domanda per la prossima riunione

Portate questa domanda al prossimo comitato rischi: **"Per quale dei quattro scenari descritti — sospensione del fornitore, attacco al fornitore, esfiltrazione del dipendente uscente, intercettazione passiva a lungo termine — abbiamo oggi un piano scritto, un test annuale e un budget allocato?"**

Se la risposta è "nessuno", il rischio non è ipotetico. È in attesa di materializzarsi.
