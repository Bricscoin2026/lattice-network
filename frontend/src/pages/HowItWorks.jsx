import { Shield, MailCheck, Radio, KeyRound, Network, ArrowRight, Lock, Building2, Server } from "lucide-react";
import { Link } from "react-router-dom";

/**
 * /how — "Come funziona Lattice" pensato per persone normali, non ingegneri.
 * Niente jargon crittografico: solo cosa fa, perché serve, come si usa.
 */
function BigCard({ icon: Icon, title, what, why, tid }) {
  return (
    <div className="surface-elev border hairline px-6 py-6 relative" data-testid={tid}>
      <div className="absolute top-0 left-0 right-0 h-px gold-line opacity-60" />
      <div className="flex items-start gap-4">
        <div className="border hairline w-12 h-12 flex items-center justify-center shrink-0">
          <Icon size={20} className="text-[var(--lattice-gold)]" />
        </div>
        <div className="min-w-0">
          <h3 className="font-display text-2xl text-white">{title}</h3>
          <p className="text-[13px] text-[var(--lattice-text-2)] mt-2 leading-relaxed">{what}</p>
          {why && (
            <p className="text-[12px] text-[var(--lattice-text-3)] mt-3 leading-relaxed italic">
              {why}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function Step({ n, title, body, tid }) {
  return (
    <div className="surface-elev border hairline px-5 py-5 relative" data-testid={tid}>
      <div className="font-display text-5xl text-[var(--lattice-gold)] opacity-25 absolute top-3 right-5 leading-none">{n}</div>
      <h3 className="font-display text-xl text-white mb-2">{title}</h3>
      <p className="text-[13px] text-[var(--lattice-text-2)] leading-relaxed">{body}</p>
    </div>
  );
}

export default function HowItWorks() {
  return (
    <div className="space-y-12 max-w-5xl" data-testid="how-it-works-page">
      {/* Hero semplice */}
      <div>
        <div className="eyebrow flex items-center gap-2 mb-1">
          <Shield size={11} className="text-[var(--lattice-gold)]" /> COME FUNZIONA · IN PAROLE SEMPLICI
        </div>
        <h1 className="font-display text-4xl sm:text-5xl text-white leading-tight">
          Lattice in <span className="text-[var(--lattice-gold)]">due minuti</span>
        </h1>
        <p className="text-[15px] text-[var(--lattice-text-2)] mt-4 leading-relaxed max-w-3xl">
          Lattice è una rete privata per le comunicazioni della tua azienda. Le mail e i messaggi che mandi
          ai tuoi colleghi sono <strong className="text-white">cifrati</strong>, <strong className="text-white">firmati</strong> e
          <strong className="text-white"> archiviati</strong> in modo da poter essere usati come prova legale anche tra dieci anni.
        </p>
      </div>

      {/* Le 3 cose che fa */}
      <section>
        <div className="eyebrow mb-4">CHE COSA FA</div>

        {/* Disclaimer legale PEC — visibile, permanente */}
        <div
          data-testid="how-pec-disclaimer"
          className="surface-elev border border-amber-500/40 bg-amber-500/5 px-5 py-4 mb-4 flex items-start gap-3"
        >
          <div className="border border-amber-400/60 w-9 h-9 flex items-center justify-center shrink-0 bg-amber-500/10">
            <Shield size={15} className="text-amber-300" />
          </div>
          <div>
            <div className="eyebrow text-amber-300 mb-1">DISCLAIMER LEGALE</div>
            <p className="text-[13px] text-[var(--lattice-text-2)] leading-relaxed">
              <strong className="text-white">Lattice Certify NON sostituisce la PEC</strong> dove la legge italiana
              la impone (notifiche giudiziarie ex art. 16 L. 53/1994, raccomandate digitali ex art. 1 D.L. 76/2020,
              comunicazioni alle PA su domicilio digitale). Per le comunicazioni B2B contrattuali e di compliance
              fornisce una garanzia crittografica superiore, ma il riconoscimento come prova legale dipende dalla
              natura del rapporto contrattuale tra le parti.
            </p>
          </div>
        </div>

        <div className="grid gap-4">
          <BigCard
            tid="how-card-certify"
            icon={MailCheck}
            title="Certify — posta certificata di nuova generazione"
            what="Le mail ufficiali della tua azienda viaggiano cifrate end-to-end e ricevono una notarizzazione crittografica sulla blockchain interna. Solo mittente e destinatario possono leggere il contenuto."
            why="Ogni invio produce una prova di esistenza opponibile a terzi: data certa, integrità del documento, identità del firmatario. Verificabile finché la rete resta attiva."
          />
          <BigCard
            tid="how-card-pulse"
            icon={Radio}
            title="Pulse — messaggistica interna sovrana"
            what="Conversazioni dei dipendenti cifrate end-to-end e instradate attraverso una mixnet a tre rimbalzi: l&apos;infrastruttura non sa chi parla con chi, né quando, né con quale frequenza."
            why="Le comunicazioni operative sensibili — HR, M&A, ricerca, segreti industriali — restano dentro il perimetro dell&apos;azienda. Nessun metadato finisce su sistemi terzi."
          />
          <BigCard
            tid="how-card-audit"
            icon={Building2}
            title="Audit pubblico"
            what="Ogni azienda della rete ha una pagina pubblica con il numero di transazioni firmate e l'ora dell'ultima attività. Niente contenuti, solo prove esistenza."
            why="I tuoi clienti o partner possono verificare in autonomia che la tua azienda è davvero attiva su Lattice — senza chiederti niente."
          />
        </div>
      </section>

      {/* Come funziona dentro - 4 step semplici */}
      <section>
        <div className="eyebrow mb-4">COME FUNZIONA · IN 4 PASSAGGI</div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <Step
            n="1"
            title="Hai una chiave"
            body="Quando l'azienda ti registra, scarichi un file (.keypair.json). È la tua identità. Tienilo come la chiave di casa."
            tid="how-step-1"
          />
          <Step
            n="2"
            title="Firmi ciò che mandi"
            body="Quando invii una mail o un messaggio, il tuo browser lo firma con la tua chiave. La firma è impossibile da contraffare, anche con un computer quantistico."
            tid="how-step-2"
          />
          <Step
            n="3"
            title="La rete archivia"
            body="La rete (4 nodi indipendenti) controlla che la firma sia valida e archivia un'impronta della mail/messaggio. Il contenuto NON viene mai pubblicato."
            tid="how-step-3"
          />
          <Step
            n="4"
            title="Prova verificabile"
            body="L'impronta resta sulla blockchain finché la rete è attiva. Chiunque può chiederti il documento originale e verificare crittograficamente che è esattamente quello firmato in quel momento. Per durata indefinita, è disponibile un ancoraggio opzionale a blockchain pubbliche."
            tid="how-step-4"
          />
        </div>
      </section>

      {/* Identità */}
      <section className="surface-elev border hairline px-6 py-6">
        <div className="absolute -mt-6 -ml-6 w-32 h-32 rounded-full opacity-[0.04]" style={{ background: "radial-gradient(circle, var(--lattice-gold), transparent 60%)" }} />
        <div className="flex items-start gap-4">
          <div className="border hairline w-12 h-12 flex items-center justify-center shrink-0">
            <KeyRound size={20} className="text-[var(--lattice-gold)]" />
          </div>
          <div>
            <h2 className="font-display text-3xl text-white">La tua identità su Lattice</h2>
            <p className="text-[14px] text-[var(--lattice-text-2)] mt-3 leading-relaxed">
              Ogni dipendente ha un nome breve nella forma{" "}
              <code className="text-[var(--lattice-gold)] font-mono-data">nome.cognome.azienda.lns</code>.
              <br />
              Esempio: in Acme SpA, Mario Bianchi è <code className="text-[var(--lattice-gold)] font-mono-data">mario.bianchi.acme.lns</code>.
            </p>
            <p className="text-[13px] text-[var(--lattice-text-3)] mt-3 leading-relaxed">
              È l&apos;unico modo per essere indirizzato sulla rete. Non c&apos;è un account email, niente password. Tutto si basa sulla tua chiave privata.
            </p>
          </div>
        </div>
      </section>

      {/* Hosting sovrano */}
      <section className="surface-elev border hairline relative overflow-hidden" data-testid="how-onpremise">
        <div className="absolute top-0 left-0 right-0 h-px gold-line" />
        <div className="absolute -right-32 -top-32 w-96 h-96 rounded-full opacity-[0.05] pointer-events-none" style={{ background: "radial-gradient(circle, var(--lattice-gold) 0%, transparent 65%)" }} />
        <div className="px-6 py-7 relative">
          <div className="flex items-start gap-4">
            <div className="border hairline w-12 h-12 flex items-center justify-center shrink-0 bg-[rgba(212,175,55,0.04)]">
              <Server size={20} className="text-[var(--lattice-gold)]" />
            </div>
            <div className="flex-1">
              <div className="eyebrow text-[var(--lattice-gold)]">INFRASTRUTTURA · ON-PREMISE</div>
              <h2 className="font-display text-3xl text-white mt-1">Lattice gira sui tuoi server</h2>
              <p className="text-[14px] text-[var(--lattice-text-2)] mt-3 leading-relaxed">
                L&apos;intero stack — applicazione, blockchain, validatori, mixnet, archivio cifrato —
                viene <strong className="text-white">installato dentro il data center della tua azienda</strong> (oppure
                in un cloud sovrano europeo di tua scelta). Una sola riga di comando, un solo file
                <code className="font-mono-data text-[var(--lattice-gold)]"> docker-compose.yml</code>.
              </p>
              <p className="text-[13px] text-[var(--lattice-text-3)] mt-3 leading-relaxed">
                Da quel momento in poi, <strong className="text-white">nessun dato della tua azienda lascia il tuo perimetro</strong>:
                non passa da AWS, Azure, Google Cloud, né da server gestiti da noi. Le chiavi, i blocchi,
                i log, le mail, i messaggi — tutto resta nel tuo controllo fisico e legale.
              </p>
              <div className="mt-5 grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="border hairline px-3 py-3">
                  <div className="eyebrow text-[10px] text-[var(--lattice-gold)] mb-1">SOVRANITÀ</div>
                  <div className="text-[12px] text-[var(--lattice-text-2)] leading-snug">
                    Possiedi tu la macchina, il filesystem cifrato e le chiavi root della rete.
                  </div>
                </div>
                <div className="border hairline px-3 py-3">
                  <div className="eyebrow text-[10px] text-[var(--lattice-gold)] mb-1">COMPLIANCE</div>
                  <div className="text-[12px] text-[var(--lattice-text-2)] leading-snug">
                    GDPR, NIS2, DORA. I dati non transitano fuori dall&apos;UE.
                  </div>
                </div>
                <div className="border hairline px-3 py-3">
                  <div className="eyebrow text-[10px] text-[var(--lattice-gold)] mb-1">VENDOR LOCK-IN</div>
                  <div className="text-[12px] text-[var(--lattice-text-2)] leading-snug">
                    Zero. Se domani vuoi spegnerci, basta che spegni i container.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Se perdi la chiave */}
      <section className="surface-elev border hairline px-6 py-6">
        <div className="flex items-start gap-4">
          <div className="border hairline w-12 h-12 flex items-center justify-center shrink-0">
            <Lock size={20} className="text-[var(--lattice-gold)]" />
          </div>
          <div className="flex-1">
            <h2 className="font-display text-3xl text-white">Se perdi la chiave</h2>
            <p className="text-[14px] text-[var(--lattice-text-2)] mt-3 leading-relaxed">
              L&apos;amministratore della tua azienda sceglie <strong className="text-white">3 colleghi fidati</strong> come
              &quot;garanti&quot;. Se un giorno perde il suo file <code className="text-[var(--lattice-gold)] font-mono-data">.keypair.json</code>,
              ne bastano <strong className="text-white">2 su 3</strong> per ricostruire la chiave.
            </p>
            <p className="text-[13px] text-[var(--lattice-text-3)] mt-3 leading-relaxed">
              Importante: i 3 garanti NON conoscono mai la chiave intera. Ognuno ha solo un pezzo cifrato che da solo è inutile.
              Solo quando 2 di loro si mettono d&apos;accordo, il sistema ricompone la chiave nel browser di chi la sta recuperando.
            </p>
            <Link
              to="/recovery"
              data-testid="how-recovery-link"
              className="inline-flex items-center gap-2 mt-4 px-3 py-2 border border-[var(--lattice-gold)] text-[var(--lattice-gold)] font-mono-data text-[11px] tracking-[0.18em] uppercase hover:bg-[rgba(212,175,55,0.08)]"
            >
              Configura i 3 garanti <ArrowRight size={12} />
            </Link>
          </div>
        </div>
      </section>

      {/* Rassicurazioni — quello che NON facciamo */}
      <section className="surface-elev border hairline px-6 py-6">
        <div className="flex items-start gap-4">
          <div className="border hairline w-12 h-12 flex items-center justify-center shrink-0">
            <Network size={20} className="text-[var(--lattice-gold)]" />
          </div>
          <div>
            <h2 className="font-display text-3xl text-white">Cosa NON facciamo</h2>
            <ul className="mt-3 space-y-2 text-[13px] text-[var(--lattice-text-2)] leading-relaxed">
              <li className="flex items-start gap-2">
                <ArrowRight size={13} className="text-[var(--lattice-gold)] mt-0.5 shrink-0" />
                <span>Non ospitiamo i tuoi dati. L&apos;infrastruttura gira dentro il tuo data center o su un nodo che controlli direttamente.</span>
              </li>
              <li className="flex items-start gap-2">
                <ArrowRight size={13} className="text-[var(--lattice-gold)] mt-0.5 shrink-0" />
                <span>Non leggiamo il contenuto delle tue mail o dei messaggi. Sono cifrati prima di lasciare il dispositivo del mittente.</span>
              </li>
              <li className="flex items-start gap-2">
                <ArrowRight size={13} className="text-[var(--lattice-gold)] mt-0.5 shrink-0" />
                <span>Non vendiamo dati, non c&apos;è pubblicità, non c&apos;è profilazione.</span>
              </li>
              <li className="flex items-start gap-2">
                <ArrowRight size={13} className="text-[var(--lattice-gold)] mt-0.5 shrink-0" />
                <span>Non possiamo &quot;spegnere&quot; il tuo accesso da remoto. L&apos;infrastruttura è tua, le chiavi sono tue.</span>
              </li>
            </ul>
          </div>
        </div>
      </section>

      {/* CTA finale */}
      <section className="text-center py-8 border-t hairline">
        <p className="text-[14px] text-[var(--lattice-text-2)]">
          Vuoi approfondire i dettagli tecnici?
        </p>
        <Link
          to="/whitepaper"
          data-testid="how-whitepaper-link"
          className="inline-flex items-center gap-2 mt-4 px-4 py-2 border border-[var(--lattice-gold)] text-[var(--lattice-gold)] font-mono-data text-[11px] tracking-[0.18em] uppercase hover:bg-[rgba(212,175,55,0.08)]"
        >
          Leggi il whitepaper <ArrowRight size={12} />
        </Link>
      </section>
    </div>
  );
}
