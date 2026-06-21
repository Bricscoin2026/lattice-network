import { Link } from "react-router-dom";
import { Shield, ArrowLeft } from "lucide-react";
import { reopenCookieBanner } from "@/components/CookieBanner";

/**
 * Legal pages — Privacy Policy & Cookie Policy
 *
 * Italian-first content, GDPR + ePrivacy + Garante Privacy 2021 compliant.
 * Titolare: editable via env or hardcoded below for this single-tenant deploy.
 */

const TITOLARE = {
  ragioneSociale: "Lattice Network",
  legaleRappresentante: "Fabio Astorino",
  indirizzo: "Italia",
  email: "info@lattice-network.it",
  dpoEmail: "privacy@lattice-network.it",
};

function Page({ title, eyebrow, children }) {
  return (
    <div className="min-h-screen text-white" style={{ background: "var(--lattice-bg)" }}>
      <header className="border-b hairline">
        <div className="max-w-4xl mx-auto px-6 lg:px-10 py-5 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3" data-testid="legal-logo">
            <img src="/lattice-logo.jpeg" alt="Lattice" style={{ width: 32, height: 32, objectFit: "contain", borderRadius: 4 }} />
            <span className="font-display text-lg tracking-tight">Lattice Network</span>
          </Link>
          <Link to="/" className="btn-ghost inline-flex items-center gap-1.5" data-testid="legal-back-home" style={{ height: 34, padding: "0 14px", fontSize: 11 }}>
            <ArrowLeft size={12} /> Home
          </Link>
        </div>
      </header>
      <section className="max-w-4xl mx-auto px-6 lg:px-10 py-16">
        <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] tracking-[0.3em] uppercase mb-3">{eyebrow}</div>
        <h1 className="font-display text-4xl lg:text-5xl text-white leading-tight">{title}</h1>
        <div className="legal-content mt-10 space-y-6 text-[14px] text-[var(--lattice-text-2)] leading-relaxed">
          {children}
        </div>
      </section>
      <footer className="px-6 lg:px-10 py-10 border-t hairline">
        <div className="max-w-4xl mx-auto flex flex-wrap items-center justify-between gap-4 font-mono-data text-[10px] text-[var(--lattice-text-3)] tracking-wider">
          <div className="flex items-center gap-2">
            <Shield size={12} className="text-[var(--lattice-gold)]" /> LATTICE NETWORK · © 2026
          </div>
          <div className="flex items-center gap-5">
            <Link to="/" className="hover:text-[var(--lattice-gold)]">Home</Link>
            <Link to="/privacy-policy" className="hover:text-[var(--lattice-gold)]">Privacy</Link>
            <Link to="/cookie-policy" className="hover:text-[var(--lattice-gold)]">Cookie</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

const H2 = ({ children }) => <h2 className="font-display text-2xl text-white mt-10 mb-3">{children}</h2>;
const H3 = ({ children }) => <h3 className="font-display text-lg text-white mt-6 mb-2">{children}</h3>;
const P = ({ children }) => <p className="leading-relaxed">{children}</p>;
const Strong = ({ children }) => <strong className="text-white">{children}</strong>;
const Box = ({ children }) => (
  <div className="border-l-2 border-[var(--lattice-gold)] pl-4 py-2 my-4 text-[13px]">
    {children}
  </div>
);
const Updated = () => (
  <p className="font-mono-data text-[10px] text-[var(--lattice-text-3)] tracking-wider uppercase">
    Ultimo aggiornamento: 18 giugno 2026 · Versione 1.0
  </p>
);

export function PrivacyPolicy() {
  return (
    <Page title="Informativa sulla Privacy" eyebrow="GDPR · REG. UE 2016/679 · INFORMATIVA">
      <Updated />

      <H2>1. Titolare del trattamento</H2>
      <P>
        Il titolare del trattamento dei dati personali raccolti tramite questo sito è{" "}
        <Strong>{TITOLARE.ragioneSociale}</Strong>, nella persona del legale rappresentante{" "}
        <Strong>{TITOLARE.legaleRappresentante}</Strong>.
      </P>
      <Box>
        <P>📧 Contatto generale: <Strong>{TITOLARE.email}</Strong></P>
        <P>📧 Contatto Privacy / DPO: <Strong>{TITOLARE.dpoEmail}</Strong></P>
      </Box>

      <H2>2. Dati personali raccolti</H2>
      <P>
        Raccogliamo i dati personali che ci comunichi direttamente attraverso il <Strong>modulo
        "Richiedi una demo"</Strong> presente sul sito e nelle pagine dedicate (es. <code className="text-[var(--lattice-gold)]">/per-il-ceo</code>,{" "}
        <code className="text-[var(--lattice-gold)]">/per-il-ciso</code>, <code className="text-[var(--lattice-gold)]">/per-il-legal</code>):
      </P>
      <ul className="list-disc pl-6 space-y-1">
        <li>Nome dell'azienda</li>
        <li>Nome e cognome del referente</li>
        <li>Indirizzo email aziendale</li>
        <li>Numero di telefono (facoltativo)</li>
        <li>Numero di dipendenti (fascia)</li>
        <li>Settore di attività</li>
        <li>Note / esigenze specifiche (facoltativo)</li>
      </ul>
      <P>
        Raccogliamo inoltre, in modo aggregato e con il tuo consenso, dati di utilizzo del sito (pagine
        visitate, tempo di permanenza, sorgente di provenienza) tramite la nostra istanza di analisi
        statistica (PostHog) — vedi <Link to="/cookie-policy" className="text-[var(--lattice-gold)] underline">Cookie Policy</Link>.
      </P>

      <H2>3. Finalità e base giuridica del trattamento</H2>
      <table className="w-full border-collapse text-[12px] mt-3">
        <thead>
          <tr className="border-b hairline">
            <th className="text-left py-2 pr-4 font-mono-data text-[10px] text-[var(--lattice-gold)] uppercase tracking-wider">Finalità</th>
            <th className="text-left py-2 pr-4 font-mono-data text-[10px] text-[var(--lattice-gold)] uppercase tracking-wider">Base giuridica</th>
            <th className="text-left py-2 font-mono-data text-[10px] text-[var(--lattice-gold)] uppercase tracking-wider">Conservazione</th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-b hairline">
            <td className="py-3 pr-4">Risposta alla richiesta di demo e contatti commerciali</td>
            <td className="py-3 pr-4">Art. 6(1)(b) GDPR — esecuzione di misure precontrattuali</td>
            <td className="py-3">24 mesi</td>
          </tr>
          <tr className="border-b hairline">
            <td className="py-3 pr-4">Newsletter e comunicazioni commerciali sul prodotto</td>
            <td className="py-3 pr-4">Art. 6(1)(a) GDPR — consenso (opt-in)</td>
            <td className="py-3">Fino a revoca</td>
          </tr>
          <tr className="border-b hairline">
            <td className="py-3 pr-4">Analisi statistica aggregata del sito</td>
            <td className="py-3 pr-4">Art. 6(1)(a) GDPR — consenso</td>
            <td className="py-3">12 mesi</td>
          </tr>
          <tr>
            <td className="py-3 pr-4">Adempimenti di legge (fiscali, contabili)</td>
            <td className="py-3 pr-4">Art. 6(1)(c) GDPR — obbligo legale</td>
            <td className="py-3">10 anni</td>
          </tr>
        </tbody>
      </table>

      <H2>4. Destinatari dei dati</H2>
      <P>
        I dati personali sono trattati esclusivamente da <Strong>{TITOLARE.ragioneSociale}</Strong> e dai
        suoi collaboratori autorizzati. <Strong>Non vendiamo, condividiamo o trasferiamo dati a terze
        parti</Strong> per finalità di marketing.
      </P>
      <P>
        I dati possono essere comunicati a:
      </P>
      <ul className="list-disc pl-6 space-y-1">
        <li><Strong>Hetzner Online GmbH</Strong> (fornitore di infrastruttura server, datacenter Germania/Finlandia) — in qualità di responsabile del trattamento ex art. 28 GDPR.</li>
        <li><Strong>Aruba S.p.A.</Strong> (fornitore del dominio e delle caselle email amministrative italiane) — in qualità di responsabile del trattamento ex art. 28 GDPR.</li>
      </ul>
      <P>
        <Strong>Nessun trasferimento dati extra-UE</Strong>. Tutta l'infrastruttura di Lattice Network
        opera esclusivamente all'interno dello Spazio Economico Europeo (SEE), coerentemente con la
        sentenza Schrems II della Corte di Giustizia UE.
      </P>

      <H2>5. Diritti dell'interessato</H2>
      <P>
        Ai sensi degli articoli 15-22 del GDPR, hai il diritto di:
      </P>
      <ul className="list-disc pl-6 space-y-1">
        <li><Strong>Accedere</Strong> ai tuoi dati personali (Art. 15)</li>
        <li><Strong>Rettificare</Strong> dati inesatti o incompleti (Art. 16)</li>
        <li><Strong>Cancellare</Strong> i dati ("diritto all'oblio", Art. 17)</li>
        <li><Strong>Limitare</Strong> il trattamento (Art. 18)</li>
        <li><Strong>Ricevere i dati in formato portabile</Strong> (JSON / CSV strutturato, Art. 20)</li>
        <li><Strong>Opporti al trattamento</Strong> per motivi legittimi (Art. 21)</li>
        <li><Strong>Revocare il consenso</Strong> in qualsiasi momento, senza che ciò pregiudichi la liceità del trattamento precedente</li>
      </ul>
      <P>
        Per esercitare questi diritti, scrivi a <Strong>{TITOLARE.dpoEmail}</Strong>. Risponderemo entro
        30 giorni come previsto dall'art. 12(3) GDPR.
      </P>

      <H2>6. Reclamo al Garante</H2>
      <P>
        Hai sempre il diritto di proporre reclamo all'<Strong>Autorità Garante per la Protezione dei Dati
        Personali</Strong> se ritieni che il trattamento dei tuoi dati violi il GDPR.
      </P>
      <Box>
        <P>🏛️ Piazza Venezia 11, 00187 Roma · garante@gpdp.it · <a href="https://www.garanteprivacy.it" target="_blank" rel="noopener noreferrer" className="text-[var(--lattice-gold)] underline">garanteprivacy.it</a></P>
      </Box>

      <H2>7. Modifiche all'informativa</H2>
      <P>
        Ci riserviamo il diritto di aggiornare questa informativa per riflettere modifiche legislative o
        operative. La versione più recente è sempre disponibile a questa pagina. Modifiche sostanziali
        saranno comunicate tramite banner sul sito.
      </P>
    </Page>
  );
}

export function CookiePolicy() {
  return (
    <Page title="Cookie Policy" eyebrow="ePRIVACY · GARANTE PRIVACY · POLICY">
      <Updated />

      <H2>Cosa sono i cookie</H2>
      <P>
        I cookie sono piccoli file di testo che i siti visitati salvano sul tuo dispositivo per
        memorizzare informazioni di sessione, preferenze o per finalità statistiche. Il presente sito
        utilizza <Strong>esclusivamente cookie di prima parte</Strong> (gestiti direttamente da{" "}
        <Strong>{TITOLARE.ragioneSociale}</Strong>) e nessun cookie pubblicitario o di profilazione di terze parti.
      </P>

      <H2>Tipologie di cookie utilizzati</H2>

      <H3>1. Cookie tecnici (necessari)</H3>
      <P>
        Necessari al funzionamento del sito. Non richiedono consenso ai sensi dell'art. 122 del Codice
        Privacy italiano e delle linee guida del Garante del 10 giugno 2021.
      </P>
      <table className="w-full border-collapse text-[12px] mt-3">
        <thead>
          <tr className="border-b hairline">
            <th className="text-left py-2 pr-4 font-mono-data text-[10px] text-[var(--lattice-gold)] uppercase tracking-wider">Nome</th>
            <th className="text-left py-2 pr-4 font-mono-data text-[10px] text-[var(--lattice-gold)] uppercase tracking-wider">Scopo</th>
            <th className="text-left py-2 font-mono-data text-[10px] text-[var(--lattice-gold)] uppercase tracking-wider">Durata</th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-b hairline">
            <td className="py-3 pr-4 font-mono-data text-[11px]">lattice_lang</td>
            <td className="py-3 pr-4">Preferenza lingua (IT/EN)</td>
            <td className="py-3">1 anno</td>
          </tr>
          <tr className="border-b hairline">
            <td className="py-3 pr-4 font-mono-data text-[11px]">lattice_cookie_consent_v1</td>
            <td className="py-3 pr-4">Memorizza le tue scelte sui cookie</td>
            <td className="py-3">12 mesi</td>
          </tr>
          <tr>
            <td className="py-3 pr-4 font-mono-data text-[11px]">lattice_session</td>
            <td className="py-3 pr-4">Mantiene la sessione utente autenticata</td>
            <td className="py-3">Sessione</td>
          </tr>
        </tbody>
      </table>

      <H3>2. Cookie statistici (previo consenso)</H3>
      <P>
        Utilizzati per analizzare in forma <Strong>aggregata e anonima</Strong> il comportamento degli
        utenti sul sito (pagine viste, tempo di permanenza, origine del traffico). I dati restano in
        Europa.
      </P>
      <table className="w-full border-collapse text-[12px] mt-3">
        <thead>
          <tr className="border-b hairline">
            <th className="text-left py-2 pr-4 font-mono-data text-[10px] text-[var(--lattice-gold)] uppercase tracking-wider">Provider</th>
            <th className="text-left py-2 pr-4 font-mono-data text-[10px] text-[var(--lattice-gold)] uppercase tracking-wider">Scopo</th>
            <th className="text-left py-2 font-mono-data text-[10px] text-[var(--lattice-gold)] uppercase tracking-wider">Durata</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td className="py-3 pr-4 font-mono-data text-[11px]">PostHog (EU region)</td>
            <td className="py-3 pr-4">Analisi statistica aggregata, gestione errori</td>
            <td className="py-3">12 mesi</td>
          </tr>
        </tbody>
      </table>
      <P>
        Senza il tuo consenso questi cookie non vengono attivati. Puoi modificare le tue preferenze in
        qualsiasi momento cliccando sul link sottostante.
      </P>

      <H2>Come gestire il consenso</H2>
      <P>
        Al primo accesso ti mostriamo un banner per scegliere quali cookie accettare. Puoi modificare la
        tua scelta in qualsiasi momento:
      </P>
      <button
        onClick={() => reopenCookieBanner()}
        data-testid="cookie-policy-reopen-banner"
        className="btn-gold inline-flex items-center gap-2 mt-2"
        style={{ padding: "10px 18px", fontSize: 12 }}
      >
        Modifica preferenze cookie
      </button>

      <H2>Disabilitare i cookie dal browser</H2>
      <P>
        In alternativa, puoi disabilitare o eliminare i cookie direttamente dalle impostazioni del tuo browser:
      </P>
      <ul className="list-disc pl-6 space-y-1">
        <li><a href="https://support.google.com/chrome/answer/95647" target="_blank" rel="noopener noreferrer" className="text-[var(--lattice-gold)] underline">Google Chrome</a></li>
        <li><a href="https://support.mozilla.org/it/kb/Gestione%20dei%20cookie" target="_blank" rel="noopener noreferrer" className="text-[var(--lattice-gold)] underline">Mozilla Firefox</a></li>
        <li><a href="https://support.apple.com/it-it/guide/safari/sfri11471/mac" target="_blank" rel="noopener noreferrer" className="text-[var(--lattice-gold)] underline">Safari</a></li>
        <li><a href="https://support.microsoft.com/it-it/microsoft-edge" target="_blank" rel="noopener noreferrer" className="text-[var(--lattice-gold)] underline">Microsoft Edge</a></li>
      </ul>
      <P>
        Nota: disabilitando i cookie tecnici alcune funzionalità del sito potrebbero non funzionare correttamente.
      </P>

      <H2>Riferimenti</H2>
      <ul className="list-disc pl-6 space-y-1">
        <li><Strong>Regolamento UE 2016/679</Strong> (GDPR)</li>
        <li><Strong>Direttiva ePrivacy 2002/58/CE</Strong> e successivi aggiornamenti</li>
        <li><Strong>D.Lgs. 196/2003</Strong> (Codice Privacy italiano)</li>
        <li><Strong>Linee guida Garante Privacy del 10 giugno 2021</Strong> sui cookie</li>
      </ul>

      <P className="mt-8 pt-6 border-t hairline">
        Per dubbi o esercizio dei tuoi diritti, scrivi a <Strong>{TITOLARE.dpoEmail}</Strong>. Vedi la{" "}
        <Link to="/privacy-policy" className="text-[var(--lattice-gold)] underline">Privacy Policy</Link> completa.
      </P>
    </Page>
  );
}

// Default export as Privacy for lazy routing; CookiePolicy is named export.
export default PrivacyPolicy;
