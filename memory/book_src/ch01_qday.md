# CAPITOLO 1 — Le comunicazioni aziendali sono fuori controllo.

## 1.0 — Apertura

*Roma, giovedì pomeriggio, 2026.*

La direttrice generale di una società italiana di consulenza fiscale riceve una notifica push sul telefono. Microsoft ha sospeso l'account 365 dell'azienda. Motivo: "rilevata attività anomala associata a uno o più utenti, in violazione dei termini di servizio". Le mail in ingresso vengono respinte con un bounce automatico. OneDrive non si apre. Teams non si connette. Le caselle dei 47 dipendenti, in pratica, non esistono più. Per ripristinare il servizio è necessario aprire un caso di supporto, attendere — secondo le best practice di Microsoft — tra le 24 e le 72 ore, e fornire documentazione "in lingua inglese" su ogni singola attività ritenuta sospetta.

Le quotazioni del mercoledì successivo erano già firmate. Le pratiche fiscali con scadenza il venerdì erano in bozza dentro OneDrive. La direttrice ha chiamato per primo l'avvocato, non l'IT manager. Aveva ragione. Il problema, in quel momento, non era informatico. Era contrattuale, reputazionale, operativo. *L'infrastruttura su cui correva la sua azienda non era sua.*

Questo capitolo racconta come è successo che tante aziende italiane si siano trovate in questa posizione. Non per cattiva fede, non per superficialità, ma per una somma di scelte ragionevoli prese una alla volta, ciascuna nel suo momento, da persone che non avevano modo di sapere dove sarebbero portate insieme.

## 1.1 — Come siamo arrivati qui

Nel 2010 una mail aziendale serviva a scambiarsi una bozza di contratto. Nel 2026 una mail aziendale è il principale strumento di registrazione delle decisioni di un'organizzazione. Nel mezzo, è cambiato tutto.

Sono cambiati i volumi: dieci-quindici mail al giorno per dipendente nel 2010, sessanta-ottanta nel 2026.

È cambiato il contenuto: nel 2010 le decisioni importanti si prendevano in riunione e si formalizzavano per via cartacea o con un fax. Nel 2026 le decisioni importanti si prendono, si registrano e si modificano tutte via mail e chat. Quasi nessuna lascia traccia fisica.

È cambiato il fornitore: nel 2010 la stragrande maggioranza delle aziende italiane aveva un server Exchange (o equivalente) in azienda, magari amministrato da un consulente esterno, ma fisicamente presente nei propri uffici. Nel 2026 la stessa azienda ha "migrato" tutto in cloud — quasi sempre Microsoft 365 o Google Workspace.

È cambiata la chat: nel 2010 la chat aziendale non esisteva. Nel 2026 ogni reparto ha un suo Slack o un suo canale Teams in cui passa una parte significativa del lavoro operativo. WhatsApp Business, formalmente vietato dalla maggior parte delle policy di sicurezza, è di fatto usato quotidianamente. La separazione tra "comunicazione personale" e "comunicazione aziendale" è collassata.

È cambiata la PEC: nel 2010 la PEC era una novità italiana che pochi usavano sul serio. Nel 2026 la PEC è obbligatoria per legge per imprese e professionisti, ma — paradossalmente — perde valore proprio mentre diventa più diffusa. Una controparte estera non la riconosce. Il provider PEC, anche se è italiano, è esposto agli stessi rischi di qualsiasi altro fornitore di mail (sospensione, cessazione, acquisizione da parte di gruppi esteri).

Ognuna di queste transizioni, presa singolarmente, era razionale. Nessuna è stata pensata in modo organico. Il risultato è una stratificazione: le mail importanti sono su Microsoft, le bozze sono su Google, le chat operative sono su Slack, le decisioni rapide sono su WhatsApp, le comunicazioni "ufficiali" sono in PEC, gli archivi storici sono su qualche NAS, le copie di sicurezza sono su un servizio cloud diverso ancora. Nessuno ne ha la mappa completa.

## 1.2 — Quattro dipendenze pericolose

Da questa stratificazione sono nate quattro dipendenze che oggi pochi consigli di amministrazione hanno messo a fuoco con chiarezza.

**Prima dipendenza: il fornitore può escluderti.**

L'account Microsoft 365 della tua azienda è regolato da un contratto chiamato Microsoft Services Agreement che — sezione 3 — si riserva il diritto unilaterale di "sospendere o terminare il servizio in qualsiasi momento, con o senza preavviso, in caso di violazione dei termini o per ragioni di sicurezza, abuso o conformità a leggi". Lo stesso vale per Google Workspace. Lo stesso vale per Slack. Lo stesso vale, in forme più sfumate, per la maggior parte dei provider PEC italiani. Significa che la continuità delle tue comunicazioni aziendali, in ultima analisi, non è una tua proprietà. È una concessione che ti viene fatta finché rispetti i termini di un contratto che il fornitore può modificare quasi a piacimento.

Negli ultimi anni questa eventualità si è materializzata in modo crescente. Microsoft, su pressione delle sanzioni occidentali contro la Russia, ha sospeso account aziendali a clienti collegati a entità sanzionate. Negli Stati Uniti, sotto il Cloud Act e l'Executive Order 14117, è stato chiarito che le autorità americane possono richiedere a Microsoft, Google e Amazon la consegna o la sospensione di dati e account "ovunque memorizzati nel mondo", senza che il cliente europeo possa opporsi in modo efficace. La sentenza Schrems II della Corte di Giustizia UE del 2020 ha dichiarato questo regime incompatibile con il GDPR, ma a sei anni di distanza la maggior parte delle aziende italiane continua a usare gli stessi servizi senza alternative pratiche.

**Seconda dipendenza: il fornitore vede tutto.**

Quando una mail aziendale transita attraverso i server Microsoft o Google, il contenuto è in chiaro (anche se cifrato in transito) all'interno dell'infrastruttura del fornitore. Significa che Microsoft, Google e i loro subprocessori autorizzati hanno la capacità tecnica di leggere quei messaggi. Hanno anche, secondo i loro stessi termini di servizio, il diritto di scansionarli automaticamente per finalità di "spam protection", "personalizzazione del servizio", "compliance" e — nel caso di alcuni piani business — anche di training di modelli di intelligenza artificiale. Le clausole che escludono il training su contenuti aziendali esistono ma si applicano solo ai piani enterprise più costosi, e la loro effettiva implementazione tecnica è verificabile solo dal fornitore stesso.

Per la maggior parte delle aziende italiane sotto i 200 dipendenti, in pratica, le mail e i documenti aziendali sono leggibili da personale di Microsoft o Google nei loro datacenter, sebbene la probabilità di lettura effettiva sia bassa e regolata da procedure interne. La differenza tra "non vengono letti" e "non possono essere letti" è cruciale. *La fiducia non sostituisce la sovranità tecnica.*

**Terza dipendenza: il dipendente porta tutto con sé.**

Quando un dipendente lascia un'azienda — sia in modo amichevole, sia in modo conflittuale — la revoca degli accessi è teoricamente immediata. In pratica, in un'azienda media italiana, la revoca completa richiede tra 3 e 7 giorni di lavoro coordinato tra HR, IT e responsabili di reparto. Nel frattempo, il dipendente uscente ha tipicamente accesso (anche solo via mobile) a Outlook, OneDrive, Teams e a qualunque chat secondaria sia stata configurata. Le sue copie locali — sul portatile, sul telefono, sul tablet — restano fuori dal perimetro di revoca anche dopo il termine del rapporto.

Inoltre, l'archivio mail di quel dipendente — anni di corrispondenza con clienti, fornitori, controparti — non è cancellabile in modo crittografico. È disabilitabile (l'account smette di accedere), ma se il dipendente aveva fatto export, screenshot, forwarding a casella personale, quei dati esistono in copia. Per legge questo è perseguibile, ma il danno operativo è già fatto. Lattice non risolve magicamente il fattore umano (chi vuole rubare dati, può farlo), ma riduce drasticamente la superficie di attacco: identità revocabili in un clic, mail firmate dal mittente in modo che le copie successive siano dimostrabilmente "esfiltrazioni", non originali.

**Quarta dipendenza: la prova in giudizio è debole.**

Quando, in una causa, la tua azienda deve dimostrare che una certa mail è stata inviata in una certa data, con un certo contenuto, da una certa persona, la stampa cartacea o l'export PST di Outlook non basta. Il giudice — su istanza della controparte — può richiedere che la prova sia "tecnicamente verificabile". Significa, in pratica, attivare un consulente tecnico d'ufficio che verifichi gli header SMTP, le firme DKIM, l'integrità della catena di custodia. Questa verifica dipende interamente dalla cooperazione del fornitore di posta (Microsoft o Google) e dal fatto che gli archivi originali siano ancora disponibili in formato verificabile. Per mail di più di 5-7 anni, questa cooperazione è raramente garantita.

La PEC offre una garanzia molto migliore — la ricevuta di consegna ha valore di prova legale ai sensi del DPR 68/2005 — ma con tre limiti significativi: (a) vale solo verso destinatari PEC italiani; (b) garantisce la consegna ma non l'integrità del contenuto se questo è stato modificato dopo la spedizione; (c) la ricevuta è verificabile solo finché il provider PEC esiste e mantiene gli archivi.

Lattice Certify riprende il valore probatorio della PEC e lo estende: ogni mail è firmata crittograficamente, ancorata sul ledger interno con timestamp immutabile, ed è verificabile pubblicamente attraverso il Block Explorer — anche tra vent'anni, anche se la tua azienda non esiste più, anche per controparti estere che non hanno mai avuto un account PEC.

## 1.3 — La PEC: un mezzo strumento

Vale la pena soffermarsi sulla PEC italiana, perché è uno degli strumenti più frequentemente citati come "soluzione" al problema della comunicazione legale, ed è invece, in realtà, un mezzo strumento.

La PEC funziona benissimo per il suo scopo originale: dimostrare che una mail è stata inviata e ricevuta tra due caselle PEC italiane in una certa data. Per questo è regolata dal DPR 68/2005 e ha valore di raccomandata con ricevuta di ritorno. Per questo, da quando il governo italiano ne ha imposto l'uso, è diventata lo strumento standard per la corrispondenza con la pubblica amministrazione, per le notifiche legali tra avvocati, per le comunicazioni formali tra imprese italiane.

Ha però quattro limiti che pochi notano.

**Primo limite — non funziona all'estero.** Una mail PEC verso un cliente tedesco è, dal punto di vista del destinatario, una mail normale. La ricevuta che ti arriva non ha alcun valore legale in Germania, in Francia, nei Paesi Bassi. Se la tua azienda esporta — e in Italia esporta una percentuale crescente di PMI — la PEC copre solo le comunicazioni "verso interno". Tutte le altre comunicazioni importanti tornano a essere mail Gmail/Outlook senza protezione specifica.

**Secondo limite — non garantisce il contenuto.** La PEC garantisce che la mail è stata consegnata; non garantisce, in senso crittografico, che il contenuto della mail (o degli allegati) non sia stato modificato dopo l'invio. Le firme digitali europee (eIDAS) sopperiscono in parte a questo, ma richiedono che mittente e destinatario abbiano entrambi una firma digitale qualificata, cosa che nella pratica avviene per una piccola percentuale dei messaggi.

**Terzo limite — vivi e muori con il provider.** La ricevuta PEC è verificabile finché il provider PEC esiste, mantiene gli archivi e collabora. Se il provider chiude (è successo: Telecom Italia Trust Technologies è stata ceduta più volte), se cambia formato, se richiede un pagamento per accedere agli archivi storici, la ricevuta diventa progressivamente più difficile da spendere in giudizio. Per archivi sopra i 10 anni, in Italia, questo è un problema serio ma sottovalutato.

**Quarto limite — il provider PEC vede i tuoi messaggi.** Diversamente da una mail cifrata end-to-end, la mail PEC transita in chiaro attraverso il provider, che ne conserva una copia per legge per 30 mesi. Il provider è un soggetto privato, regolato da una direttiva (AgID), ma è un terzo che ha accesso ai contenuti. Per comunicazioni con valore strategico (M&A, contenziosi, investigazioni interne), questo è un punto delicato.

## 1.4 — Il rischio in fondo: la crittografia che invecchia (Q-Day)

C'è un quinto rischio che va citato, perché in prospettiva è il più radicale, ma che non è quello da cui partire nelle conversazioni di consiglio di amministrazione del 2026. Si chiama, in gergo, **Q-Day**: il giorno in cui un computer quantistico universale di capacità criptanaliticamente rilevante diventa operativo nelle mani di qualcuno — un governo, un'intelligence, una grande azienda.

Quel giorno, gli algoritmi che oggi proteggono la totalità delle comunicazioni TLS, PEC, VPN, certificati HTTPS e firme digitali commerciali — RSA-2048, ECDSA, Ed25519 — diventano vulnerabili in tempi pratici. Le stime di quando questo accadrà variano: NIST parla del 2030-2040, BSI tedesco del 2030, ANSSI francese del 2035 come scenario centrale.

Anche se la data esatta è incerta, una conseguenza è già in atto da anni: il **Harvest Now, Decrypt Later**. Un attaccante con risorse statali può, già oggi, intercettare e archiviare il tuo traffico cifrato (mail, VPN, PEC) per decifrarlo retroattivamente quando avrà la macchina. Tutte le aziende e gli enti che gestiscono dati con un orizzonte di rilevanza superiore a dieci anni — banche, sanità, pubblica amministrazione, studi legali, ricerca, difesa — sono già esposti a questo rischio. *Lo erano ieri, lo sono oggi, lo saranno domani.*

La buona notizia è che la soluzione tecnica esiste e si chiama crittografia post-quantistica. Nel 2024 il NIST americano ha pubblicato gli standard FIPS 203, 204 e 205 che definiscono algoritmi resistenti ai computer quantistici (ML-KEM, ML-DSA, SLH-DSA). Sono liberi, open source, implementati in librerie di riferimento. La Germania (BSI) e la Francia (ANSSI) li hanno raccomandati. La NSA americana li sta imponendo per i sistemi classificati entro il 2030.

L'industria italiana, a fine 2025, non li aveva ancora adottati in modo sistematico. Lattice li usa di default fin dal primo giorno, e dal Capitolo 8 in poi spieghiamo perché e come. Ma — questo è il punto del capitolo — *il Q-Day non è il problema principale del 2026*. Il problema principale del 2026 sono le quattro dipendenze descritte nelle sezioni 1.2 e 1.3. Q-Day è un'amplificazione futura di un problema che è già qui, oggi, materialmente, e che impatta la tua azienda anche se nessun computer quantistico viene mai costruito.

## 1.5 — Cosa serve davvero a un'azienda nel 2026

Da queste analisi emerge una specifica funzionale che pochi fornitori di mail e di chat soddisfano in modo coerente. Una piattaforma di comunicazione aziendale, per essere realmente "sotto controllo", deve dare cinque cose:

**Sovranità.** L'infrastruttura deve girare su risorse che la tua azienda controlla — server fisici in sede oppure macchine virtuali in un cloud sovrano europeo che hai scelto tu. Nessun fornitore extra-UE deve poter accedere, modificare, sospendere il servizio senza la tua autorizzazione esplicita.

**Identità verificabile.** Ogni utente — dipendente, fornitore, consulente — deve avere un'identità crittografica firmata dall'azienda, revocabile in tempo reale, verificabile pubblicamente. Quando lui esce, la revoca è immediata e ha effetto su tutte le comunicazioni future. Le comunicazioni passate restano firmate e dimostrabilmente sue.

**Isolamento.** La chat interna e la mail interna non devono lasciare la rete aziendale. Nessun fornitore intermedio deve vedere i contenuti. La cifratura deve essere end-to-end e i metadati devono essere protetti (non solo i contenuti, ma anche "chi parla con chi" deve essere difficile da inferire).

**Prova opponibile.** Ogni mail con valore legale o documento ufficiale deve essere firmato e ancorato a un registro immutabile, verificabile pubblicamente da chiunque, anche a vent'anni di distanza, anche all'estero. La prova deve essere indipendente dal fornitore: non basta che Lattice dica "sì, questa mail esiste". Deve poterlo dire la matematica.

**Apertura.** Niente lock-in. Il codice deve essere ispezionabile, i protocolli pubblici, gli standard riconosciuti. Se domani decidi di portare l'infrastruttura altrove o di gestirla in autonomia, lo fai senza rinegoziare contratti.

Queste cinque proprietà non sono opinabili. Sono i requisiti minimi per una piattaforma di comunicazione aziendale che voglia essere, non solo "sicura" nel senso tecnico, ma **sotto controllo** nel senso operativo. Pochissimi prodotti sul mercato le offrono tutte e cinque insieme. Microsoft 365 ne offre zero. Google Workspace ne offre zero. Slack ne offre zero. La PEC italiana ne offre una e mezza. Lattice è stato costruito per offrirle tutte e cinque, in modo nativo, dal giorno uno.

Il resto del libro spiega come.

## 1.6 — Domanda per la prossima riunione

Se siete un amministratore delegato o un membro del consiglio, portate questa singola domanda al prossimo comitato esecutivo: **"Se Microsoft o Google sospendessero domani il nostro account 365 per qualunque motivo, quanto tempo impiegheremmo a ripristinare le comunicazioni aziendali essenziali, e su quale infrastruttura?"**

Se la risposta è "non lo so" — o "ci appoggeremmo al loro supporto" — il rischio è già materializzato. Non quantistico. *Materiale.* È il rischio che la continuità operativa della vostra azienda sia, di fatto, in concessione.

Il resto di questo libro spiega come riprendersi quella continuità, in dodici mesi, senza interrompere il lavoro, e a costi prevedibili.
