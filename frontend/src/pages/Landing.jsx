import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useLang } from "@/i18n/LangProvider";
import { Shield, ShieldCheck, Clock, Lock, Building2, Check, ArrowRight, Mail, Phone, User, MessageCircle } from "lucide-react";
import { toast } from "sonner";

const COPY = {
  it: {
    eyebrow: "LATTICE NETWORK · SOVEREIGN INFRASTRUCTURE",
    h1a: "Comunicazioni aziendali",
    h1b: "sotto il tuo controllo.",
    hero: "Lattice è una rete privata aziendale: identità verificate (LNS), posta legale (Certify), chat interna (Pulse) e audit immutabile, tutto su una blockchain QBFT con firme post-quantistiche ML-DSA-65. La gestisci tu, on-premise o in un cloud sovrano europeo.",
    ctaDemo: "Richiedi una demo",
    ctaLogin: "Ho già un account",
    ctaLoginTop: "Ho già un account",
    ctaDemoTop: "Richiedi demo",
    benefitsTitle: "Tre cose che otteniamo",
    forWho: "Per chi è",
    howWorks: "Come funziona",
    step1: "Ci parli",
    step1d: "Capiamo cosa ti serve. Una call di 30 minuti, senza obblighi.",
    step2: "Ti consegniamo le chiavi",
    step2d: "Installiamo la rete on-premise o in un cloud sovrano europeo. In 5 giorni lavorativi.",
    step3: "Comunichi sicuro",
    step3d: "I tuoi colleghi accedono via app o web. Tutto è cifrato e notarizzato senza che debbano pensarci.",
    formTitle: "Richiedi una demo",
    formSub: "Compila i dati. Ti contattiamo entro 24 ore.",
    fCompany: "Nome azienda",
    fContact: "Nome contatto",
    fEmail: "Email aziendale",
    fPhone: "Telefono",
    fEmployees: "Dipendenti",
    fSector: "Settore",
    fNotes: "Note (opzionale)",
    fSubmit: "Invia richiesta",
    formSuccess: "Grazie! Ti contatteremo entro 24 ore.",
    formError: "Errore invio. Riprova oppure scrivici su WhatsApp +39 351 961 8068",
    footerCTO: "Per CTO/CISO · vista tecnica →",
    benefits: [
      { title: "Controllo, non sicurezza", body: "Ogni messaggio aziendale viaggia sulla TUA rete: chi può entrare, chi può uscire, chi vede cosa — lo decidi tu. Non un'altra suite cloud da fidarsi: la decidi tu." },
      { title: "Isolamento totale", body: "Ogni azienda vive in un perimetro tenant separato sulla stessa rete sovrana. I tuoi dati non lasciano l'infrastruttura che gestisci tu. Sovranità reale, non marketing." },
      { title: "Prova verificabile nel tempo", body: "Ogni comunicazione importante (mail, contratto, decisione) lascia una traccia crittografica indipendente dal fornitore. Chiunque, in qualsiasi momento, può verificare matematicamente che è stata firmata dalla persona giusta nel momento giusto." },
    ],
    forWhoList: [
      "Banche e assicurazioni che gestiscono dati regolamentati",
      "Studi legali con corrispondenza riservata",
      "Cliniche e RSA con cartelle sanitarie",
      "Pubbliche amministrazioni con scambi inter-ente",
      "Aziende con segreti industriali da proteggere",
    ],
  },
  en: {
    eyebrow: "LATTICE NETWORK · SOVEREIGN INFRASTRUCTURE",
    h1a: "Corporate communications,",
    h1b: "under your control.",
    hero: "Lattice is a private corporate network: verified identities (LNS), legal-grade mail (Certify), internal chat (Pulse) and immutable audit, all on a QBFT blockchain with post-quantum ML-DSA-65 signatures. You operate it, on-premise or on a sovereign European cloud.",
    ctaDemo: "Request a demo",
    ctaLogin: "I already have an account",
    ctaLoginTop: "I have an account",
    ctaDemoTop: "Request demo",
    benefitsTitle: "Three things we deliver",
    forWho: "Built for",
    howWorks: "How it works",
    step1: "Tell us about you",
    step1d: "A 30-minute scoping call. No commitment.",
    step2: "We hand you the keys",
    step2d: "On-premise or European sovereign cloud deployment in 5 business days.",
    step3: "Communicate securely",
    step3d: "Your team logs in via web or mobile. Everything is encrypted and notarised — invisibly.",
    formTitle: "Request a demo",
    formSub: "Fill in the form. We'll get back within 24 hours.",
    fCompany: "Company name",
    fContact: "Contact name",
    fEmail: "Business email",
    fPhone: "Phone",
    fEmployees: "Employees",
    fSector: "Sector",
    fNotes: "Notes (optional)",
    fSubmit: "Send request",
    formSuccess: "Thank you! We'll contact you within 24 hours.",
    formError: "Submission failed. WhatsApp us at +39 351 961 8068",
    footerCTO: "For CTOs/CISOs · technical view →",
    benefits: [
      { title: "Your data stays yours", body: "Sovereign infrastructure, on-premise or European private cloud deployment. No outsourcing, no third-party access. Your company runs on your own network." },
      { title: "Future-proof", body: "Post-quantum cryptography certified by NIST (ML-DSA-65, ML-KEM-768). When the quantum computer arrives, your data from today will still be safe." },
      { title: "Opposable evidence", body: "Every message and email is digitally signed and notarised on the internal blockchain. Cryptographic proof — verifiable as long as the network is live, with optional anchoring to public chains for indefinite durability." },
    ],
    forWhoList: [
      "Banks and insurers managing regulated data",
      "Law firms with confidential correspondence",
      "Clinics and care homes with health records",
      "Public administrations with inter-agency exchanges",
      "Enterprises with industrial secrets to protect",
    ],
  },
};

function LeadForm({ lang = "it" }) {
  const T = lang === "en" ? {
    eyebrow: "REQUEST A DEMO",
    title: "Let's talk for 30 minutes.",
    sub: "No commitment. We'll show you how it works on your data.",
    company: "Company",
    name: "Your name",
    email: "Email",
    phone: "Phone",
    employees: "Employees",
    sector: "Sector",
    notes: "What would you like to protect?",
    submit: "Request free demo",
    submitting: "Sending…",
    successTitle: "Request received",
    successBody: "Thank you. We'll contact you within 24 business hours to schedule a personalised demo.",
    fineprint: "Response within 24 business hours · No contract · No commitment",
    placeholderNotes: "Internal communications, mail with clients, sensitive data...",
  } : {
    eyebrow: "RICHIEDI UNA DEMO",
    title: "Vediamoci 30 minuti.",
    sub: "Niente impegno. Ti facciamo vedere come funziona sulla tua azienda.",
    company: "Azienda",
    name: "Il tuo nome",
    email: "Email",
    phone: "Telefono",
    employees: "Dipendenti",
    sector: "Settore",
    notes: "Cosa vorresti proteggere?",
    submit: "Richiedi demo gratuita",
    submitting: "Invio in corso…",
    successTitle: "Richiesta ricevuta",
    successBody: "Grazie. Ti contattiamo entro 24 ore lavorative per organizzare una demo personalizzata.",
    fineprint: "Risposta entro 24 ore lavorative · Nessun contratto · Nessun impegno",
    placeholderNotes: "Comunicazioni interne, mail con clienti, dati sensibili...",
  };
  const [form, setForm] = useState({
    company_name: "", contact_name: "", email: "", phone: "",
    employees_range: "11-50", industry: "Finanza", notes: "",
  });
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/leads", form);
      setDone(true);
      toast.success("Richiesta inviata! Ti contattiamo entro 24h.");
    } catch (err) {
      toast.error(err?.response?.data?.detail?.[0]?.msg || err?.response?.data?.detail || "Errore invio");
    } finally { setBusy(false); }
  };

  if (done) {
    return (
      <div className="surface-elev px-8 py-10 text-center" data-testid="lead-form-success">
        <ShieldCheck size={36} className="mx-auto text-[var(--lattice-gold)]" />
        <h3 className="font-display text-3xl text-white mt-4">Richiesta ricevuta</h3>
        <p className="text-[14px] text-[var(--lattice-text-2)] mt-3 max-w-md mx-auto">
          Grazie {form.contact_name.split(" ")[0]}. Ti contattiamo entro 24 ore lavorative per organizzare una demo personalizzata di Lattice per {form.company_name}.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="surface-elev p-8 space-y-4" data-testid="lead-form">
      <div className="absolute top-0 left-0 right-0 h-px gold-line" />
      <div>
        <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] tracking-[0.3em] uppercase">{T.eyebrow}</div>
        <h3 className="font-display text-3xl text-white mt-2">{T.title}</h3>
        <p className="text-[13px] text-[var(--lattice-text-2)] mt-2">{T.sub}</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
        <div>
          <label className="font-mono-data text-[10px] text-[var(--lattice-text-3)] uppercase tracking-wider block mb-1.5">{T.company} *</label>
          <input required data-testid="lead-company" className="input-sovereign" placeholder="ACME SpA"
                 value={form.company_name} onChange={(e) => setForm({...form, company_name: e.target.value})} />
        </div>
        <div>
          <label className="font-mono-data text-[10px] text-[var(--lattice-text-3)] uppercase tracking-wider block mb-1.5">{T.name} *</label>
          <input required data-testid="lead-name" className="input-sovereign" placeholder="Mario Rossi"
                 value={form.contact_name} onChange={(e) => setForm({...form, contact_name: e.target.value})} />
        </div>
        <div>
          <label className="font-mono-data text-[10px] text-[var(--lattice-text-3)] uppercase tracking-wider block mb-1.5">{T.email} *</label>
          <input required type="email" data-testid="lead-email" className="input-sovereign" placeholder="mario@acme.it"
                 value={form.email} onChange={(e) => setForm({...form, email: e.target.value})} />
        </div>
        <div>
          <label className="font-mono-data text-[10px] text-[var(--lattice-text-3)] uppercase tracking-wider block mb-1.5">{T.phone}</label>
          <input data-testid="lead-phone" className="input-sovereign" placeholder="+39 ..."
                 value={form.phone} onChange={(e) => setForm({...form, phone: e.target.value})} />
        </div>
        <div>
          <label className="font-mono-data text-[10px] text-[var(--lattice-text-3)] uppercase tracking-wider block mb-1.5">{T.employees}</label>
          <select data-testid="lead-employees" className="input-sovereign"
                  value={form.employees_range} onChange={(e) => setForm({...form, employees_range: e.target.value})}>
            {["1-10","11-50","51-200","201-1000","1000+"].map((r) => (
              <option key={r} value={r} style={{ background: "#0a1020" }}>{r}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="font-mono-data text-[10px] text-[var(--lattice-text-3)] uppercase tracking-wider block mb-1.5">{T.sector}</label>
          <select data-testid="lead-industry" className="input-sovereign"
                  value={form.industry} onChange={(e) => setForm({...form, industry: e.target.value})}>
            {["Finanza","Sanità","Legale","Pubblica Amministrazione","Manifatturiero","Energia","Difesa","Altro"].map((i) => (
              <option key={i} value={i} style={{ background: "#0a1020" }}>{i}</option>
            ))}
          </select>
        </div>
      </div>
      <div>
        <label className="font-mono-data text-[10px] text-[var(--lattice-text-3)] uppercase tracking-wider block mb-1.5">{T.notes}</label>
        <textarea data-testid="lead-notes" rows={3} className="input-sovereign" placeholder="Comunicazioni interne, mail con clienti, dati sensibili..."
                  value={form.notes} onChange={(e) => setForm({...form, notes: e.target.value})} />
      </div>
      <button type="submit" disabled={busy} data-testid="lead-submit" className="btn-gold w-full inline-flex items-center justify-center gap-2 mt-2" style={{ padding: "14px 24px", fontSize: 13 }}>
        {busy ? T.submitting : <>{T.submit} <ArrowRight size={14} /></>}
      </button>
      <p className="text-center font-mono-data text-[10px] text-[var(--lattice-text-4)]">
        {T.fineprint}
      </p>
    </form>
  );
}

export default function Landing() {
  const { lang, setLang } = useLang();
  const c = COPY[lang] || COPY.it;
  const [stats, setStats] = useState({ qbft: null, mix: null, ledger: null, certify: null });
  useEffect(() => {
    let alive = true;
    const fetchAll = async () => {
      try {
        const [q, m, l, c] = await Promise.all([
          api.get("/qbft/status").catch(() => null),
          api.get("/mixnet/status").catch(() => null),
          api.get("/ledger/stats").catch(() => null),
          api.get("/certify/stats").catch(() => null),
        ]);
        if (alive) setStats({ qbft: q?.data, mix: m?.data, ledger: l?.data, certify: c?.data });
      } catch (e) { /* ignore */ }
    };
    fetchAll();
    const id = setInterval(fetchAll, 8000);
    return () => { alive = false; clearInterval(id); };
  }, []);
  const live = {
    validators: stats.qbft ? `${stats.qbft.live_count}/${stats.qbft.total_count}` : "—",
    relays: stats.mix ? `${stats.mix.live_count}/${stats.mix.total_count}` : "—",
    blocks: stats.ledger ? Number(stats.ledger.block_height).toLocaleString("it-IT") : "—",
    mails24: stats.certify ? Number(stats.certify.last_24h).toLocaleString("it-IT") : "—",
  };
  return (
    <div className="min-h-screen text-white" style={{ background: "var(--lattice-bg)" }} data-testid="landing-root">
      {/* Top bar */}
      <header className="border-b hairline">
        <div className="max-w-6xl mx-auto px-6 lg:px-10 py-5 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3" data-testid="landing-logo">
            <img src="/lattice-logo.jpeg" alt="Lattice" style={{ width: 32, height: 32, objectFit: "contain", borderRadius: 4 }} />
            <span className="font-display text-lg tracking-tight">Lattice Network</span>
          </Link>
          <div className="flex items-center gap-2">
            <div className="flex items-center border hairline-strong" data-testid="landing-lang-toggle">
              <button onClick={() => setLang("it")} className={`px-2 py-1 font-mono-data text-[10px] tracking-wider ${lang === "it" ? "bg-[var(--lattice-gold)] text-[var(--lattice-bg)]" : "text-[var(--lattice-text-3)] hover:text-white"}`}>IT</button>
              <button onClick={() => setLang("en")} className={`px-2 py-1 font-mono-data text-[10px] tracking-wider border-l hairline-strong ${lang === "en" ? "bg-[var(--lattice-gold)] text-[var(--lattice-bg)]" : "text-[var(--lattice-text-3)] hover:text-white"}`}>EN</button>
            </div>
            <Link to="/security" data-testid="landing-cta-security-top" className="btn-ghost hidden sm:inline-flex items-center gap-1.5" style={{ height: 34, padding: "0 14px", fontSize: 11 }}>Security &amp; Audit</Link>
            <Link to="/dashboard" data-testid="landing-cta-console-top" className="btn-ghost hidden md:inline-flex items-center gap-1.5" style={{ height: 34, padding: "0 14px", fontSize: 11 }}>Console operatore</Link>
            <Link to="/login" data-testid="landing-cta-login-top" className="btn-ghost inline-flex items-center gap-1.5" style={{ height: 34, padding: "0 14px", fontSize: 11 }}>{c.ctaLoginTop}</Link>
            <a href="#demo" data-testid="landing-cta-demo-top" className="btn-gold inline-flex items-center gap-1.5" style={{ height: 34, padding: "0 14px", fontSize: 11 }}>{c.ctaDemoTop}</a>
          </div>
        </div>
      </header>

      {/* Hero — semplice e diretto */}
      <section className="border-b hairline">
        <div className="max-w-6xl mx-auto px-6 lg:px-10 py-20 lg:py-28">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div>
              <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] tracking-[0.3em] uppercase mb-6">{c.eyebrow}</div>
              <h1 className="font-display leading-[1.0] text-white" style={{ fontSize: "clamp(40px, 5.5vw, 68px)" }}>
                {c.h1a} <span className="text-[var(--lattice-gold)]">{c.h1b}</span>
              </h1>
              <div
                data-testid="landing-positioning-tagline"
                className="mt-6 border-l-2 border-[var(--lattice-gold)] pl-5 max-w-xl"
              >
                <p className="text-[18px] lg:text-[19px] text-white font-display leading-[1.4] italic">
                  {lang === "en"
                    ? '"Lattice makes every corporate communication verifiable, isolated and under your control."'
                    : '«Lattice rende ogni comunicazione aziendale verificabile, isolata e sotto controllo.»'}
                </p>
              </div>
              <p className="text-[15px] text-[var(--lattice-text-2)] leading-relaxed mt-6 max-w-xl">
                {c.hero}
              </p>
              <div className="flex flex-wrap items-center gap-3 mt-9">
                <a href="#demo" data-testid="landing-cta-demo" className="btn-gold inline-flex items-center gap-2" style={{ padding: "14px 22px", fontSize: 13 }}>
                  {c.ctaDemo} <ArrowRight size={14} />
                </a>
                <Link to="/onboarding" data-testid="landing-cta-onboarding" className="btn-ghost inline-flex items-center gap-2" style={{ padding: "14px 22px", fontSize: 13 }}>
                  <Building2 size={14} /> Registra subito
                </Link>
              </div>
              <div className="mt-10 pt-6 border-t hairline flex items-center gap-6 font-mono-data text-[10px] text-[var(--lattice-text-3)] tracking-widest uppercase flex-wrap">
                <span>GDPR</span><span>·</span><span>NIS2</span><span>·</span><span>NIST FIPS 204</span><span>·</span><span>EU only</span>
              </div>
              <div className="mt-3 font-mono-data text-[10px] text-[var(--lattice-text-3)] tracking-wider leading-relaxed" data-testid="landing-replaces">
                <span className="text-[var(--lattice-gold)]">{lang === "en" ? "Includes" : "Include"}:</span>{" "}
                LNS Identity · Certify Mail · Pulse Chat · {lang === "en" ? "Immutable Audit · Block Explorer" : "Audit Immutabile · Block Explorer"}
              </div>
              <div className="mt-4 flex items-center gap-2 font-mono-data text-[10px] text-[var(--lattice-text-3)] tracking-wider" data-testid="landing-live-strip">
                <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]" />
                <span>rete live · validator <span className="text-[var(--lattice-gold)]">{live.validators}</span> · relay <span className="text-[var(--lattice-gold)]">{live.relays}</span> · blocchi <span className="text-[var(--lattice-gold)]">{live.blocks}</span> · mail oggi <span className="text-[var(--lattice-gold)]">{live.mails24}</span></span>
              </div>
            </div>
            <div className="lg:pl-8">
              <div id="demo">
                <LeadForm lang={lang} />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 3 benefit semplici */}
      <section className="border-b hairline" style={{ background: "#060b15" }}>
        <div className="max-w-6xl mx-auto px-6 lg:px-10 py-20">
          <div className="text-center max-w-2xl mx-auto mb-14">
            <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] tracking-[0.3em] uppercase mb-3">{c.benefitsTitle}</div>
            <h2 className="font-display text-4xl lg:text-5xl text-white leading-tight">{lang === "en" ? "Three problems. One answer." : "Tre problemi. Una soluzione."}</h2>
          </div>
          <div className="grid md:grid-cols-3 gap-5">
            {c.benefits.map((b, i) => {
              const Icon = [ShieldCheck, Lock, Clock][i] || ShieldCheck;
              return (
                <div key={i} className="surface px-6 py-8" data-testid={`landing-benefit-${i}`}>
                  <Icon size={26} className="text-[var(--lattice-gold)]" />
                  <h3 className="font-display text-2xl text-white mt-5">{b.title}</h3>
                  <p className="text-[14px] text-[var(--lattice-text-2)] mt-3 leading-relaxed">{b.body}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Per chi */}
      <section className="border-b hairline">
        <div className="max-w-6xl mx-auto px-6 lg:px-10 py-20 grid md:grid-cols-2 gap-12 items-center">
          <div>
            <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] tracking-[0.3em] uppercase mb-3">{c.forWho}</div>
            <h2 className="font-display text-4xl text-white leading-tight">{lang === "en" ? "Built for those who have something to protect." : "Costruito per chi ha qualcosa da perdere."}</h2>
            <p className="text-[14px] text-[var(--lattice-text-2)] mt-6 leading-relaxed">
              {lang === "en"
                ? "If your business handles confidential data, regulated communications or industrial secrets, Lattice is for you. When your emails carry real value, give them an infrastructure to match."
                : "Se la tua azienda gestisce dati riservati, comunicazioni regolamentate o segreti industriali, Lattice è per te. Quando le tue mail contano davvero, meritano un'infrastruttura all'altezza."}
            </p>
            <div className="mt-6 flex flex-wrap gap-2" data-testid="landing-role-links">
              <Link to="/per-il-ceo" data-testid="landing-role-ceo" className="btn-ghost inline-flex items-center gap-2" style={{ padding: "10px 16px", fontSize: 12 }}>
                Per CEO →
              </Link>
              <Link to="/per-il-ciso" data-testid="landing-role-ciso" className="btn-ghost inline-flex items-center gap-2" style={{ padding: "10px 16px", fontSize: 12 }}>
                Per CISO →
              </Link>
              <Link to="/per-il-legal" data-testid="landing-role-legal" className="btn-ghost inline-flex items-center gap-2" style={{ padding: "10px 16px", fontSize: 12 }}>
                Per Legal →
              </Link>
            </div>
          </div>
          <ul className="space-y-3">
            {c.forWhoList.map((w, i) => (
              <li key={i} className="flex items-start gap-3 surface px-5 py-3" data-testid={`landing-forwho-${i}`}>
                <Check size={16} className="text-[var(--lattice-gold)] mt-0.5 shrink-0" />
                <span className="text-[14px] text-white">{w}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Come si parte — 3 step semplici */}
      <section className="border-b hairline" style={{ background: "#060b15" }}>
        <div className="max-w-5xl mx-auto px-6 lg:px-10 py-20">
          <div className="text-center mb-14">
            <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] tracking-[0.3em] uppercase mb-3">{c.howWorks}</div>
            <h2 className="font-display text-4xl text-white leading-tight">{lang === "en" ? "Three steps and you're operational." : "In tre passaggi sei operativo."}</h2>
          </div>
          <div className="grid md:grid-cols-3 gap-4">
            {[
              { n: 1, t: c.step1, b: c.step1d },
              { n: 2, t: c.step2, b: c.step2d },
              { n: 3, t: c.step3, b: c.step3d },
            ].map((s) => (
              <div key={s.n} className="surface px-6 py-7 relative" data-testid={`landing-step-${s.n}`}>
                <div className="absolute top-5 right-6 font-display text-6xl text-[var(--lattice-gold)] opacity-20 leading-none">{s.n}</div>
                <h3 className="font-display text-2xl text-white">{s.t}</h3>
                <p className="text-[13px] text-[var(--lattice-text-2)] mt-3 leading-relaxed">{s.b}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA finale */}
      <section className="border-b hairline" style={{ background: "linear-gradient(180deg, #070d18 0%, #0a1322 100%)" }}>
        <div className="max-w-3xl mx-auto px-6 lg:px-10 py-24 text-center">
          <h2 className="font-display text-4xl lg:text-5xl text-white leading-tight">
            Tre cose, una telefonata.
          </h2>
          <p className="text-[15px] text-[var(--lattice-text-2)] mt-5 max-w-xl mx-auto">
            Vediamoci 30 minuti. Ti facciamo vedere come Lattice protegge davvero la tua azienda. Senza slide. Solo cose reali.
          </p>
          <a href="#demo" data-testid="landing-cta-final" className="btn-gold inline-flex items-center gap-2 mt-9" style={{ padding: "14px 28px", fontSize: 13 }}>
            Richiedi demo gratuita <ArrowRight size={14} />
          </a>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <a
              href="https://wa.me/393519618068?text=Ciao%2C%20vorrei%20una%20demo%20di%20Lattice%20Network"
              target="_blank"
              rel="noopener noreferrer"
              data-testid="landing-whatsapp-cta"
              className="inline-flex items-center gap-2 px-5 py-3 border border-emerald-400/60 text-emerald-300 font-mono-data text-[11px] tracking-[0.18em] uppercase hover:bg-emerald-500/10"
            >
              <MessageCircle size={13} /> WhatsApp · +39 351 961 8068
            </a>
          </div>
        </div>
      </section>

      {/* Tech link discreto in fondo */}
      <footer className="px-6 lg:px-10 py-10">
        <div className="max-w-6xl mx-auto flex flex-wrap items-center justify-between gap-4 font-mono-data text-[10px] text-[var(--lattice-text-3)] tracking-wider">
          <div className="flex items-center gap-2">
            <Shield size={12} className="text-[var(--lattice-gold)]" /> LATTICE NETWORK · © 2026
          </div>
          <div className="flex items-center gap-5">
            <Link to="/whitepaper" className="hover:text-[var(--lattice-gold)]" data-testid="landing-whitepaper-link">Whitepaper</Link>
            <Link to="/audit" className="hover:text-[var(--lattice-gold)]" data-testid="landing-audit-link">Audit pubblico</Link>
            <Link to="/explorer" className="hover:text-[var(--lattice-gold)]" data-testid="landing-explorer-link">Block Explorer</Link>
            <Link to="/security" className="hover:text-[var(--lattice-gold)]" data-testid="landing-security-link">Security &amp; Audit</Link>
            <Link to="/privacy-policy" className="hover:text-[var(--lattice-gold)]" data-testid="landing-privacy-link">Privacy</Link>
            <Link to="/cookie-policy" className="hover:text-[var(--lattice-gold)]" data-testid="landing-cookie-link">Cookie</Link>
            <Link to="/login" className="hover:text-white">Login</Link>
            <Link to="/network" className="hover:text-[var(--lattice-gold)]" data-testid="landing-tech-link">Per CTO/CISO →</Link>
            <a href="https://wa.me/393519618068?text=Ciao%2C%20vorrei%20informazioni%20su%20Lattice%20Network" target="_blank" rel="noopener noreferrer" className="hover:text-white" data-testid="landing-whatsapp-footer">WhatsApp +39 351 961 8068</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
