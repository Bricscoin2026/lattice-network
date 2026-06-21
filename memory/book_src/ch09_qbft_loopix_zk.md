# CAPITOLO 9 — QBFT, Loopix, Zero-Knowledge: i tre pilastri del consenso e dell'isolamento.

## 9.0 — Apertura

Tre componenti tecniche, oltre alla crittografia post-quantum del capitolo 8, distinguono Lattice come "rete di comunicazione aziendale" piuttosto che come "semplice mail server cifrato". Sono il **consenso QBFT** (che garantisce la finalità delle transazioni), il **mixnet Loopix** (che protegge i metadati della chat), e le **prove a conoscenza zero ZK-RLN** (che proteggono da abusi senza esporre identità). Questo capitolo li spiega uno per volta, dal punto di vista operativo e di sicurezza.

## 9.1 — QBFT: come si decide cosa è "ufficiale"

[FIGURA 9.1 — Il consenso QBFT a quorum]

Una blockchain aziendale come Lattice deve rispondere a una domanda apparentemente semplice: "quando una transazione è ufficialmente accettata?". In una blockchain pubblica (Bitcoin, Ethereum) la risposta è probabilistica: "quando un certo numero di blocchi successivi è stato minato sopra il blocco che la contiene". È lenta (10 minuti per Bitcoin, 12 secondi per Ethereum) e non offre garanzie deterministiche.

In Lattice — dove i validatori sono identificati, contrattuali, sotto SLA — usiamo un consenso a quorum: **QBFT** (Quorum Byzantine Fault Tolerant), evoluzione del classico PBFT (Castro & Liskov, 1999). Le proprietà:

**Quorum di voto.** Le decisioni richiedono almeno **2f+1** voti su un totale di **3f+1** validatori (dove f è il numero massimo di guasti tollerati). Una rete con 4 validatori tollera 1 guasto (3 voti su 4); una rete con 10 validatori tollera 3 guasti; una con 21 ne tollera 6. Le configurazioni tipiche di Lattice usano 4 o 7 validatori per le PMI, 21 per le grandi enterprise.

**Finalità deterministica.** Quando un blocco riceve i voti sufficienti, è finalizzato **per sempre**. Non c'è la possibilità di un fork retroattivo (come in Bitcoin con i 51% attack). Una transazione che è nel blocco finalizzato N può essere considerata definitivamente registrata.

**Velocità.** La finalizzazione richiede tipicamente 1-3 secondi su reti di 4-21 nodi su WAN. Non ci sono i ritardi probabilistici delle blockchain pubbliche.

**Resistenza agli attaccanti.** L'attaccante deve compromettere più di f validatori per rompere il consenso. Con la scelta dei validatori (banche dell'azienda, partner contrattuali, notai, organi di vigilanza) questo è una garanzia operativa molto forte.

Il limite di QBFT è la scalabilità a centinaia di validatori (la comunicazione cresce quadraticamente). Per Lattice questo non è un problema perché le reti aziendali raramente superano i 21 validatori.

## 9.2 — Loopix: come si proteggono i metadati della chat

Una conversazione cifrata end-to-end protegge il **contenuto** dei messaggi. Non protegge i **metadati**: chi parla con chi, quando, con quale frequenza. Per applicazioni aziendali ordinarie i metadati sono già sufficienti a inferire informazioni strategiche (es. "il CFO ha chattato per 2 ore col CFO della società target prima dell'annuncio dell'acquisizione").

Lattice Pulse usa il protocollo **Loopix** (Piotrowska et al., USENIX Security 2017) per nascondere i metadati. Loopix è un mixnet — una rete di relay che rimescola messaggi in modo che osservatori esterni non possano correlare un messaggio in entrata a uno in uscita.

[FIGURA 9.2 — Loopix mixnet a 3-hop]

**Come funziona, semplificato.** Quando Mario invia un messaggio a Paolo:

1. Il messaggio viene cifrato a strati (cifratura "a cipolla"), con tre strati ciascuno destinato a un relay diverso.
2. Mario invia il messaggio al **primo relay**, che decifra lo strato esterno (vede che deve inoltrare a un secondo relay, non vede il contenuto né il destinatario finale) e lo inoltra dopo una piccola attesa casuale.
3. Il **secondo relay** decifra il secondo strato e inoltra al terzo, di nuovo con una piccola attesa.
4. Il **terzo relay** decifra l'ultimo strato e vede il destinatario (Paolo) ma non vede il mittente (Mario). Consegna il messaggio.

**Cover traffic.** Per prevenire l'analisi statistica (un osservatore che conta i messaggi può ancora correlare), Loopix introduce traffico finto: messaggi "esca" che girano nella rete e che gli osservatori non possono distinguere dai messaggi reali. Il risultato è che, anche un attaccante con visibilità globale sulla rete, non può determinare chi parla con chi.

**Trade-off.** Loopix introduce latenza (qualche centinaio di millisecondi per i tre hop). Per la chat è accettabile (la conversazione umana non è una corsa al millisecondo). Per applicazioni real-time strette (es. trading ad alta frequenza) non sarebbe adatto — ma non è quel tipo di applicazione.

**Anti-bot via ZK-RLN.** Nello specifico, per evitare che un attaccante usi i relay per spam o DoS (Denial of Service), Pulse implementa un sistema di rate-limiting via **Zero-Knowledge Rate-Limiting Nullifiers** (ZK-RLN). Ogni utente può inviare al massimo N messaggi per "epoch" (finestra di 10 secondi). Se prova a inviarne di più, genera due prove con lo stesso nullifier — e questo permette di identificarlo crittograficamente (slashing). Lo zero-knowledge garantisce che, in condizioni normali, il sistema non sappia chi sta inviando i messaggi.

## 9.3 — Zero-Knowledge: dimostrare senza rivelare

Le prove a conoscenza zero (Zero-Knowledge Proofs) sono uno strumento crittografico che permette a una parte di dimostrare la verità di un'affermazione **senza rivelare niente oltre il fatto che l'affermazione è vera**.

Esempio: posso dimostrare di conoscere una password senza rivelare la password. O di essere maggiorenne senza rivelare la mia data di nascita. O di avere uno stipendio sopra una soglia senza rivelare lo stipendio esatto.

In Lattice le ZK sono usate in tre punti specifici:

**1. ZK-RLN per Pulse (anti-spam).** Come descritto sopra: provo di essere un utente legittimo e di non aver superato la quota, senza rivelare la mia identità.

**2. Audit pubblico aziende.** Una banca, per soddisfare requisiti normativi, può voler dimostrare che ha emesso almeno N mail Certify firmate dai suoi dirigenti senza rivelare quali siano. Lo fa pubblicando una prova ZK sul Block Explorer. L'auditor verifica la prova senza accedere ai contenuti.

**3. Recupero chiavi con privacy.** Quando un guardiano contribuisce alla ricostruzione di una chiave Shamir, può farlo con una prova ZK che dimostra "ho calcolato il mio share correttamente" senza rivelare il valore del share fino al momento finale della ricostruzione.

Le ZK in Lattice sono basate su **PLONK** (Gabizon et al., 2019) con curva ellittica BLS12-381. Le prove sono compatte (~200 byte) e verificabili in pochi millisecondi.

## 9.4 — Come questi tre componenti si combinano

Per rendere concreta la combinazione, vediamo cosa succede in un'azione aziendale tipica.

**Scenario:** Mario di Acme apre una nuova conversazione Pulse con Paolo di Acme per discutere un tema riservato.

1. **Identità verificata (ML-DSA-65).** Mario apre l'app e la sua identità viene verificata via challenge-response ML-DSA-65 client-side. Il server di Lattice riconosce Mario come autenticato senza che la sua chiave segreta lasci il browser.

2. **Setup conversazione (ML-KEM-768).** Mario crea una nuova conversazione. Il suo client esegue uno scambio di chiavi PQXDH (Post-Quantum X3DH) basato su ML-KEM-768 con Paolo, stabilendo una chiave radice della conversazione (Double Ratchet pattern).

3. **Invio messaggio (Loopix).** Mario scrive "Vediamoci stasera". Il messaggio viene cifrato end-to-end con la chiave del ratchet, e poi instradato attraverso 3 relay Loopix in onion routing.

4. **Anti-spam (ZK-RLN).** Mario prova di non aver superato la quota di 5 messaggi/10 secondi via ZK-RLN. La prova è verificata dal primo relay.

5. **Notarizzazione periodica (QBFT).** Ogni 3 messaggi della conversazione, Pulse calcola un "anchor hash" e lo invia come transazione QBFT. Il blocco si finalizza in 1-3 secondi. Da quel momento, la conversazione è ancorata on-chain in modo che qualunque modifica retrospettiva sarebbe dimostrabile.

6. **Verifica pubblica (Block Explorer).** L'azienda di Mario può, in un audit interno, dimostrare che la conversazione è esistita e quanti messaggi conteneva (senza rivelare il contenuto). Il Block Explorer mostra l'anchor hash. La verifica è indipendente da Lattice.

## 9.5 — Le proprietà di sicurezza combinate

Combinando QBFT + Loopix + ZK + crittografia post-quantum, Lattice ottiene:

- **Contenuti illeggibili** a chiunque tranne mittente e destinatario.
- **Metadati offuscati** rispetto a osservatori esterni (chi parla con chi è nascosto).
- **Identità verificabile** quando serve (per audit, per non-ripudio).
- **Ora certa** crittograficamente per ogni anchor.
- **Finalità deterministica** per ogni transazione registrata.
- **Resistenza al quantum**.

Sono proprietà che, fino al 2024, erano disponibili solo in sistemi militari classificati o in implementazioni di ricerca accademica. Lattice le rende disponibili in un'infrastruttura aziendale italiana del 2026 — questo è, tecnicamente, lo stato dell'arte.

## 9.6 — Per chi vuole approfondire

Le tre referenze tecniche essenziali per i lettori che vogliono andare a fondo:

- **QBFT:** Castro & Liskov, "Practical Byzantine Fault Tolerance" (OSDI 1999); Ethereum Foundation, "IBFT 2.0 / QBFT specification" (2021).
- **Loopix:** Piotrowska, Hayes, Elahi, Meiser, Danezis, "The Loopix Anonymity System" (USENIX Security 2017).
- **ZK-PLONK:** Gabizon, Williamson, Ciobotaru, "PLONK: Permutations over Lagrange-bases for Oecumenical Noninteractive arguments of Knowledge" (IACR 2019).

I sorgenti delle implementazioni Lattice di questi componenti sono pubblicati su GitHub sotto BSL 1.1 e ispezionabili.
