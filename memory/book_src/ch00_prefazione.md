# PREFAZIONE

*Ogni epoca tecnologica ha un suo momento di soglia. Quello che separa il "prima" dal "dopo", il "credevamo" dal "ora sappiamo". Per la crittografia, quel momento ha un nome e — verosimilmente — anche una data approssimativa: si chiama Q-Day, ed è atteso tra il 2030 e il 2034.*

Quando ho letto per la prima volta la bozza di questo libro, ho avuto due reazioni in rapida successione. La prima è stata di sollievo: finalmente qualcuno racconta in italiano, e per un pubblico di decisori, ciò che a Brussels, a Bonn e a Washington si dice da almeno cinque anni. La seconda è stata di inquietudine: perché in Italia, nel 2026, dobbiamo ancora spiegare a un consiglio di amministrazione bancario che la crittografia che protegge gli archivi della sua clientela ha una data di scadenza.

Eppure è così. Il National Institute of Standards and Technology degli Stati Uniti — l'ente che da sessant'anni stabilisce gli standard crittografici che proteggono il mondo intero — ha pubblicato nel 2024 i primi tre standard di crittografia *post-quantistica*: FIPS 203, FIPS 204 e FIPS 205. Sono algoritmi liberi, open source, già implementati in librerie di riferimento (PQClean, libsodium, BoringSSL). La Germania, attraverso il BSI, ha emesso linee guida vincolanti per la pubblica amministrazione federale. La Francia, attraverso l'ANSSI, ha attivato una task force di transizione. La National Security Agency americana ha pubblicato la CNSA 2.0, che impone l'uso di crittografia post-quantistica per tutte le comunicazioni classificate entro il 2030.

E l'Italia? L'Agenzia per la Cybersicurezza Nazionale (ACN), nata nel 2021, ha pubblicato un documento di posizionamento generico nel 2023. Non esiste, nel momento in cui scrivo questa prefazione, una roadmap nazionale di migrazione. Non esiste un censimento dei sistemi critici che usano ancora RSA-2048 o ECDSA. Non esiste un budget pubblico stanziato per la transizione delle infrastrutture digitali essenziali.

L'autore di questo libro — uno degli ingegneri che ha costruito Lattice Network, la prima piattaforma italiana di cybersicurezza sovrana basata interamente su standard post-quantistici NIST — non si limita a documentare questa lacuna. Fa qualcosa di più importante: traduce, in un linguaggio leggibile da un dirigente, da un compliance officer, da un avvocato d'affari, la mappa delle scelte tecniche che ogni organizzazione italiana dovrà fare nei prossimi 36 mesi. Non lo fa in modo allarmistico. Lo fa in modo *operativo*. Ogni capitolo termina con una domanda che il lettore può portare nella prossima riunione del proprio comitato rischi.

Questo libro ha tre meriti che vale la pena segnalare in apertura.

Primo: prende sul serio la **sovranità digitale** come categoria tecnica, non come slogan politico. Le sei dimensioni della sovranità che l'autore propone nel capitolo 4 — codice, dati, chiavi, infrastruttura, aggiornamenti, catena di fornitura — sono uno strumento di valutazione che può essere applicato domani mattina a qualsiasi contratto di outsourcing che la vostra organizzazione abbia firmato. Provate. Vi farà uscire freddo lungo la schiena.

Secondo: non vende soluzioni. **Spiega come riconoscere quando una soluzione è davvero sovrana.** È una distinzione fondamentale. Negli ultimi tre anni il mercato europeo ha visto un proliferare di prodotti etichettati "sovrani" che, all'analisi, dipendono in modo cruciale da componenti, chiavi, certificati o aggiornamenti software che restano sotto il controllo di entità extra-europee. Il libro fornisce una checklist verificabile. Usatela.

Terzo, e forse il più importante: è un **libro italiano per l'Italia**, scritto da chi conosce intimamente il tessuto produttivo, normativo e culturale del Paese. Le quattro storie di caso d'uso del capitolo 13 — la banca, il comune, lo studio legale, l'azienda sanitaria — non sono storielle americane traslate. Sono situazioni realmente affrontate, con vincoli, fornitori, ostacoli e numeri italiani. È raro, in questo settore, leggere un testo che riesca a parlare contemporaneamente la lingua di Roma, di Milano e di Bruxelles. Questo libro ci riesce.

Resta una domanda implicita lungo tutte le pagine: *perché ci ostiniamo a dipendere da altri per la nostra sicurezza?* L'autore non offre una risposta moralistica. Offre, più semplicemente, gli strumenti per smettere. Sta a noi — manager, tecnologi, magistrati, politici, cittadini — decidere se usarli.

Quello che è certo è che il tempo non è dalla nostra parte. Q-Day arriverà. Quando accadrà, le organizzazioni che avranno migrato i propri sistemi alla crittografia post-quantistica continueranno a operare normalmente. Le altre dovranno spiegare ai propri clienti, ai propri pazienti, ai propri elettori, perché vent'anni di comunicazioni riservate sono diventate, in una notte, pubblicamente leggibili.

Questo libro vi dà tre, forse quattro anni di vantaggio. Usateli.

— *La prefazione è uno spazio. In questa edizione di prova è scritta in forma simulata da un curatore editoriale. Nell'edizione definitiva sarà firmata da una personalità di alto profilo del settore cybersecurity italiano o europeo: vedere la guida editoriale per le strategie di approccio.*
