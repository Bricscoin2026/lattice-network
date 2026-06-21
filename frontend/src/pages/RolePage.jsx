import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useLang } from "@/i18n/LangProvider";
import {
  Shield, ShieldCheck, ArrowRight, ArrowLeft, Briefcase, ShieldAlert, Scale,
  MessageCircle, Check, AlertTriangle, Eye, Lock,
} from "lucide-react";
import { toast } from "sonner";

// Role-specific content. Pitch phrases are ChatGPT verbatim from the positioning brief.
const ROLES = {
  ceo: {
    Icon: Briefcase,
    eyebrow: "PER CEO / FOUNDER",
    h1a: "Riduci il rischio",
    h1b: "di fuga dati.",
    quote: "«Lattice rende ogni comunicazione aziendale verificabile, isolata e sotto controllo.»",
    hero: "Smetti di affidare le decisioni più importanti della tua azienda a Microsoft, Google o Slack. Lattice è una rete privata di comunicazione che gestisci tu, dove ogni mail e ogni decisione importante è verificabile crittograficamente — anche tra vent'anni, anche all'estero, anche se cambi fornitore.",
    pitch: "Riduci il rischio di fuga dati e hai prove verificabili di ogni comunicazione importante.",
    painTitle: "Il problema reale",
    pains: [
      { Icon: AlertTriangle, title: "Sospensione del fornitore", body: "Se Microsoft o Google decidono di sospendere il tuo account 365 — capitato a centinaia di aziende EU negli ultimi 24 mesi — la tua mail, OneDrive e Teams si fermano. Tu non hai voce in capitolo. Risoluzione tipica: 24-72 ore di stop operativo." },
      { Icon: Eye, title: "Dati strategici in chiaro a terzi", body: "M&A, decisioni strategiche, segreti industriali viaggiano oggi via mail su server extra-UE soggetti al CLOUD Act statunitense. Schrems II li dichiara incompatibili col GDPR, ma in pratica continui a usarli." },
      { Icon: AlertTriangle, title: "Dispersione quando un dipendente esce", body: "Liste clienti, contratti, decisioni interne finiscono nelle copie locali di chi lascia. La revoca completa, secondo le best practice, richiede 3-7 giorni. Le copie esfiltrate restano fuori dal tuo controllo." },
    ],
    benefitsTitle: "Cosa cambia con Lattice",
    benefits: [
      { Icon: Shield, title: "Sovranità reale", body: "Infrastruttura on-premise o cloud sovrano EU. Nessun fornitore extra-UE può escluderti, sospenderti, leggerti." },
      { Icon: ShieldCheck, title: "Continuità operativa", body: "Lattice gira sui tuoi server. La continuità della tua azienda smette di essere una concessione del fornitore." },
      { Icon: Lock, title: "Prova matematica, sempre", body: "Ogni mail importante è verificabile sul Block Explorer pubblico — anche tra 20 anni, anche in giudizio all'estero, senza dipendere da Lattice come azienda." },
    ],
    formTitle: "Vediamoci 30 minuti.",
    formSub: "Senza obblighi. Ti facciamo vedere cosa cambia per la tua azienda nello specifico.",
  },
  ciso: {
    Icon: ShieldAlert,
    eyebrow: "PER CISO / IT SECURITY",
    h1a: "Isoliamo la comunicazione,",
    h1b: "verificabile end-to-end.",
    quote: "«Isoliamo completamente la comunicazione aziendale e la rendiamo verificabile crittograficamente end-to-end, con infrastruttura sotto tuo controllo.»",
    hero: "Identità aziendali centralizzate (LNS), comunicazioni interne isolate da Internet aperta, audit trail crittografico indipendente, revoca immediata di chi esce. Il perimetro torna definibile. Crittografia post-quantum NIST FIPS 203/204 by default.",
    pitch: "Identità centralizzate. Crittografia post-quantum. Audit indipendente. Revoca in un click.",
    painTitle: "I rischi che gestisci ogni giorno",
    pains: [
      { Icon: AlertTriangle, title: "Shadow IT su WhatsApp e Gmail personali", body: "Le tue policy lo vietano, ma il personale usa comunque WhatsApp Business e Gmail private per parlare di lavoro. Nessuna visibilità. Nessuna revoca. Audit log inesistenti." },
      { Icon: Eye, title: "Dipendenza dall'auditato", body: "Gli audit log Microsoft 365 sono forniti dal fornitore stesso che dovresti auditare. La cooperazione in giudizio dipende da Microsoft. La catena di custodia è debole." },
      { Icon: AlertTriangle, title: "Q-Day e Harvest Now, Decrypt Later", body: "Tutto il traffico TLS aziendale intercettato oggi potrà essere decifrato retroattivamente quando arriveranno i computer quantistici. Per dati con vita >10 anni, la crittografia attuale è già un rischio strutturale." },
    ],
    benefitsTitle: "Cosa Lattice fa nativamente",
    benefits: [
      { Icon: Shield, title: "Identità aziendali (LNS)", body: "Ogni dipendente, fornitore, consulente ha un'identità ML-DSA-65 firmata dalla tua azienda. Revoca crittografica immediata: dal blocco N in avanti, ogni firma viene rifiutata." },
      { Icon: Lock, title: "Crittografia post-quantum by default", body: "FIPS 203 (ML-KEM-768) per scambio chiavi, FIPS 204 (ML-DSA-65) per firme. Gli stessi standard NSA usa per le comunicazioni classificate USA." },
      { Icon: ShieldCheck, title: "Audit indipendente", body: "Ledger QBFT con finalità deterministica. Block Explorer pubblico per la verifica esterna. Nessuna dipendenza dal vendor che dovresti auditare." },
    ],
    formTitle: "Parliamone in dettaglio.",
    formSub: "Una sessione tecnica di 45 minuti con il nostro CTO. Architettura, threat model, integrazione AD/IAM.",
  },
  legal: {
    Icon: Scale,
    eyebrow: "PER LEGAL / COMPLIANCE",
    h1a: "Prova opponibile",
    h1b: "che vale anche fra 20 anni.",
    quote: "«Ogni comunicazione aziendale può essere verificata nel tempo come prova immutabile, senza dipendere da provider esterni.»",
    hero: "La PEC vale solo in Italia, dipende dal provider, espone i contenuti. Le mail Gmail/Outlook hanno valore probatorio debole. Lattice Certify produce prove crittografiche verificabili pubblicamente, opponibili in giudizio in Italia e all'estero, durevoli nel tempo indipendentemente dal fornitore.",
    pitch: "Prova opponibile, verificabile pubblicamente, indipendente dal fornitore. GDPR · NIS2 · DORA · eIDAS 2.0.",
    painTitle: "I limiti degli strumenti attuali",
    pains: [
      { Icon: AlertTriangle, title: "La PEC ha 4 limiti strutturali", body: "Vale solo in Italia. Non garantisce il contenuto. Vive e muore col provider. Il provider vede tutto in chiaro per 30 mesi. Per comunicazioni con controparti estere o con vita >10 anni, è un mezzo strumento." },
      { Icon: Eye, title: "Le mail Gmail/Outlook hanno valore probatorio debole", body: "In causa, la controparte può sempre contestare l'integrità della catena di custodia. La verifica richiede consulente tecnico d'ufficio e cooperazione del fornitore. Per archivi >5 anni, raramente garantita." },
      { Icon: AlertTriangle, title: "DORA / NIS2 chiedono più di quanto i fornitori standard offrano", body: "Mappatura dei fornitori critici ICT (Art. 28 DORA), notifica incidenti (NIS2 Art. 23), audit ricostruibile. Microsoft/Google offrono compliance certificates, non verifica indipendente." },
    ],
    benefitsTitle: "Cosa Lattice Certify ti dà",
    benefits: [
      { Icon: ShieldCheck, title: "Verifica pubblica sul Block Explorer", body: "Hai una disputa? Il giudice o l'avvocato della controparte aprono il Block Explorer, inseriscono l'hash del documento, ottengono in 30 secondi la prova matematica di firma, mittente, data." },
      { Icon: Lock, title: "Opponibile cross-border", body: "Diversamente dalla PEC, la prova Certify è verificabile in qualunque giurisdizione. Solo matematica, niente provider intermedio, niente formato proprietario." },
      { Icon: Shield, title: "Durabilità a 20+ anni", body: "Ancoraggio Bitcoin opzionale via OpenTimestamps: la prova sopravvive anche se Lattice come azienda non esiste più. La rete Bitcoin è gestita da decine di migliaia di nodi indipendenti." },
    ],
    formTitle: "Vediamoci con il vostro legale.",
    formSub: "Una sessione di 30 minuti dedicata a come Certify produce prova opponibile nella vostra giurisdizione di riferimento.",
  },
};

function LeadForm({ role, T }) {
  const [form, setForm] = useState({
    company_name: "", contact_name: "", email: "", phone: "",
    employees_range: "11-50", industry: "Finanza",
    notes: `[ruolo: ${role}] ${T.pitch}`,
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
      toast.error(err?.response?.data?.detail || "Errore invio");
    } finally { setBusy(false); }
  };

  if (done) {
    return (
      <div className="surface-elev px-8 py-10 text-center" data-testid="role-lead-success">
        <ShieldCheck size={36} className="mx-auto text-[var(--lattice-gold)]" />
        <h3 className="font-display text-3xl text-white mt-4">Richiesta ricevuta</h3>
        <p className="text-[14px] text-[var(--lattice-text-2)] mt-3 max-w-md mx-auto">
          Grazie {form.contact_name.split(" ")[0]}. Ti contattiamo entro 24 ore lavorative.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="surface-elev p-8 space-y-4 relative" data-testid={`role-lead-form-${role}`}>
      <div className="absolute top-0 left-0 right-0 h-px gold-line" />
      <div>
        <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] tracking-[0.3em] uppercase">RICHIEDI UNA DEMO</div>
        <h3 className="font-display text-3xl text-white mt-2">{T.formTitle}</h3>
        <p className="text-[13px] text-[var(--lattice-text-2)] mt-2">{T.formSub}</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
        <div>
          <label className="font-mono-data text-[10px] text-[var(--lattice-text-3)] uppercase tracking-wider block mb-1.5">Azienda *</label>
          <input required data-testid="role-lead-company" className="input-sovereign" placeholder="ACME SpA"
                 value={form.company_name} onChange={(e) => setForm({...form, company_name: e.target.value})} />
        </div>
        <div>
          <label className="font-mono-data text-[10px] text-[var(--lattice-text-3)] uppercase tracking-wider block mb-1.5">Nome *</label>
          <input required data-testid="role-lead-name" className="input-sovereign" placeholder="Mario Rossi"
                 value={form.contact_name} onChange={(e) => setForm({...form, contact_name: e.target.value})} />
        </div>
        <div>
          <label className="font-mono-data text-[10px] text-[var(--lattice-text-3)] uppercase tracking-wider block mb-1.5">Email *</label>
          <input required type="email" data-testid="role-lead-email" className="input-sovereign" placeholder="mario@acme.it"
                 value={form.email} onChange={(e) => setForm({...form, email: e.target.value})} />
        </div>
        <div>
          <label className="font-mono-data text-[10px] text-[var(--lattice-text-3)] uppercase tracking-wider block mb-1.5">Telefono</label>
          <input data-testid="role-lead-phone" className="input-sovereign" placeholder="+39 ..."
                 value={form.phone} onChange={(e) => setForm({...form, phone: e.target.value})} />
        </div>
        <div>
          <label className="font-mono-data text-[10px] text-[var(--lattice-text-3)] uppercase tracking-wider block mb-1.5">Dipendenti</label>
          <select data-testid="role-lead-employees" className="input-sovereign"
                  value={form.employees_range} onChange={(e) => setForm({...form, employees_range: e.target.value})}>
            {["1-10","11-50","51-200","201-1000","1000+"].map((r) => (
              <option key={r} value={r} style={{ background: "#0a1020" }}>{r}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="font-mono-data text-[10px] text-[var(--lattice-text-3)] uppercase tracking-wider block mb-1.5">Settore</label>
          <select data-testid="role-lead-industry" className="input-sovereign"
                  value={form.industry} onChange={(e) => setForm({...form, industry: e.target.value})}>
            {["Finanza","Sanità","Legale","Pubblica Amministrazione","Manifatturiero","Energia","Difesa","Altro"].map((i) => (
              <option key={i} value={i} style={{ background: "#0a1020" }}>{i}</option>
            ))}
          </select>
        </div>
      </div>
      <button type="submit" disabled={busy} data-testid="role-lead-submit" className="btn-gold w-full inline-flex items-center justify-center gap-2 mt-2" style={{ padding: "14px 24px", fontSize: 13 }}>
        {busy ? "Invio in corso…" : <>Richiedi demo gratuita <ArrowRight size={14} /></>}
      </button>
      <p className="text-center font-mono-data text-[10px] text-[var(--lattice-text-4)]">
        Risposta entro 24 ore lavorative · Nessun contratto · Nessun impegno
      </p>
    </form>
  );
}

export default function RolePage({ role }) {
  const T = ROLES[role];
  const { lang, setLang } = useLang();
  const navigate = useNavigate();
  if (!T) {
    navigate("/");
    return null;
  }
  const Icon = T.Icon;
  const otherRoles = Object.entries(ROLES).filter(([k]) => k !== role);

  return (
    <div className="min-h-screen text-white" style={{ background: "var(--lattice-bg)" }} data-testid={`role-page-${role}`}>
      {/* Top bar */}
      <header className="border-b hairline">
        <div className="max-w-6xl mx-auto px-6 lg:px-10 py-5 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3" data-testid="role-logo">
            <img src="/lattice-logo.jpeg" alt="Lattice" style={{ width: 32, height: 32, objectFit: "contain", borderRadius: 4 }} />
            <span className="font-display text-lg tracking-tight">Lattice Network</span>
          </Link>
          <div className="flex items-center gap-2">
            <div className="flex items-center border hairline-strong" data-testid="role-lang-toggle">
              <button onClick={() => setLang("it")} className={`px-2 py-1 font-mono-data text-[10px] tracking-wider ${lang === "it" ? "bg-[var(--lattice-gold)] text-[var(--lattice-bg)]" : "text-[var(--lattice-text-3)] hover:text-white"}`}>IT</button>
              <button onClick={() => setLang("en")} className={`px-2 py-1 font-mono-data text-[10px] tracking-wider border-l hairline-strong ${lang === "en" ? "bg-[var(--lattice-gold)] text-[var(--lattice-bg)]" : "text-[var(--lattice-text-3)] hover:text-white"}`}>EN</button>
            </div>
            <Link to="/" data-testid="role-back-home" className="btn-ghost inline-flex items-center gap-1.5" style={{ height: 34, padding: "0 14px", fontSize: 11 }}>
              <ArrowLeft size={12} /> Home
            </Link>
            <Link to="/login" data-testid="role-login" className="btn-ghost inline-flex items-center gap-1.5" style={{ height: 34, padding: "0 14px", fontSize: 11 }}>Login</Link>
            <a href="#demo" data-testid="role-demo-top" className="btn-gold inline-flex items-center gap-1.5" style={{ height: 34, padding: "0 14px", fontSize: 11 }}>Richiedi demo</a>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="border-b hairline">
        <div className="max-w-6xl mx-auto px-6 lg:px-10 py-20 lg:py-24">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div>
              <div className="inline-flex items-center gap-2 font-mono-data text-[10px] text-[var(--lattice-gold)] tracking-[0.3em] uppercase mb-6">
                <Icon size={14} /> {T.eyebrow}
              </div>
              <h1 className="font-display leading-[1.0] text-white" style={{ fontSize: "clamp(40px, 5.5vw, 64px)" }}>
                {T.h1a} <span className="text-[var(--lattice-gold)]">{T.h1b}</span>
              </h1>
              <div data-testid="role-pitch-quote" className="mt-6 border-l-2 border-[var(--lattice-gold)] pl-5 max-w-xl">
                <p className="text-[17px] text-white font-display leading-[1.4] italic">{T.quote}</p>
              </div>
              <p className="text-[15px] text-[var(--lattice-text-2)] leading-relaxed mt-6 max-w-xl">
                {T.hero}
              </p>
              <div className="mt-8 flex flex-wrap items-center gap-3">
                <a href="#demo" data-testid="role-cta-demo" className="btn-gold inline-flex items-center gap-2" style={{ padding: "14px 22px", fontSize: 13 }}>
                  Richiedi demo dedicata <ArrowRight size={14} />
                </a>
              </div>
            </div>
            <div className="lg:pl-8">
              <div id="demo">
                <LeadForm role={role} T={T} />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Pain */}
      <section className="border-b hairline" style={{ background: "#060b15" }}>
        <div className="max-w-6xl mx-auto px-6 lg:px-10 py-20">
          <div className="text-center mb-12">
            <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] tracking-[0.3em] uppercase mb-3">PROBLEMA</div>
            <h2 className="font-display text-4xl text-white leading-tight">{T.painTitle}</h2>
          </div>
          <div className="grid md:grid-cols-3 gap-5">
            {T.pains.map((p, i) => {
              const PIcon = p.Icon;
              return (
                <div key={i} className="surface px-6 py-7" data-testid={`role-pain-${role}-${i}`}>
                  <PIcon size={22} className="text-rose-300" />
                  <h3 className="font-display text-xl text-white mt-4">{p.title}</h3>
                  <p className="text-[13px] text-[var(--lattice-text-2)] mt-3 leading-relaxed">{p.body}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Benefits */}
      <section className="border-b hairline">
        <div className="max-w-6xl mx-auto px-6 lg:px-10 py-20">
          <div className="text-center mb-12">
            <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] tracking-[0.3em] uppercase mb-3">SOLUZIONE</div>
            <h2 className="font-display text-4xl text-white leading-tight">{T.benefitsTitle}</h2>
          </div>
          <div className="grid md:grid-cols-3 gap-5">
            {T.benefits.map((b, i) => {
              const BIcon = b.Icon;
              return (
                <div key={i} className="surface px-6 py-7" data-testid={`role-benefit-${role}-${i}`}>
                  <BIcon size={22} className="text-[var(--lattice-gold)]" />
                  <h3 className="font-display text-xl text-white mt-4">{b.title}</h3>
                  <p className="text-[13px] text-[var(--lattice-text-2)] mt-3 leading-relaxed">{b.body}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Cross-link to other roles */}
      <section className="border-b hairline" style={{ background: "#060b15" }}>
        <div className="max-w-5xl mx-auto px-6 lg:px-10 py-16">
          <div className="text-center mb-8">
            <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] tracking-[0.3em] uppercase mb-3">ALTRE PROSPETTIVE</div>
            <h2 className="font-display text-3xl text-white leading-tight">Vedi Lattice anche dal punto di vista di…</h2>
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            {otherRoles.map(([k, r]) => {
              const RIcon = r.Icon;
              return (
                <Link
                  key={k}
                  to={`/per-il-${k}`}
                  data-testid={`role-crosslink-${k}`}
                  className="surface px-6 py-6 group hover:border-[var(--lattice-gold)] transition-all"
                >
                  <div className="flex items-start gap-4">
                    <RIcon size={26} className="text-[var(--lattice-gold)] mt-1 shrink-0" />
                    <div className="flex-1">
                      <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] uppercase tracking-[0.18em] mb-1">{r.eyebrow}</div>
                      <h3 className="font-display text-xl text-white">{r.h1a} <span className="text-[var(--lattice-gold)]">{r.h1b}</span></h3>
                      <p className="text-[12px] text-[var(--lattice-text-3)] mt-2 leading-relaxed">{r.pitch}</p>
                      <div className="mt-3 inline-flex items-center gap-1 font-mono-data text-[11px] text-[var(--lattice-text-2)] group-hover:text-[var(--lattice-gold)]">
                        Apri <ArrowRight size={11} />
                      </div>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="border-b hairline" style={{ background: "linear-gradient(180deg, #070d18 0%, #0a1322 100%)" }}>
        <div className="max-w-3xl mx-auto px-6 lg:px-10 py-20 text-center">
          <h2 className="font-display text-4xl text-white leading-tight">
            Parliamone in concreto.
          </h2>
          <p className="text-[15px] text-[var(--lattice-text-2)] mt-5 max-w-xl mx-auto">
            Una call di 30 minuti dedicata al tuo ruolo. Niente slide, niente pitch generico. Cosa cambia nella tua azienda, in dettaglio.
          </p>
          <a href="#demo" data-testid="role-cta-final" className="btn-gold inline-flex items-center gap-2 mt-9" style={{ padding: "14px 28px", fontSize: 13 }}>
            Richiedi demo gratuita <ArrowRight size={14} />
          </a>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <a
              href="https://wa.me/393519618068?text=Ciao%2C%20vorrei%20una%20demo%20di%20Lattice%20Network"
              target="_blank"
              rel="noopener noreferrer"
              data-testid={`role-whatsapp-${role}`}
              className="inline-flex items-center gap-2 px-5 py-3 border border-emerald-400/60 text-emerald-300 font-mono-data text-[11px] tracking-[0.18em] uppercase hover:bg-emerald-500/10"
            >
              <MessageCircle size={13} /> WhatsApp · +39 351 961 8068
            </a>
          </div>
        </div>
      </section>

      <footer className="px-6 lg:px-10 py-10">
        <div className="max-w-6xl mx-auto flex flex-wrap items-center justify-between gap-4 font-mono-data text-[10px] text-[var(--lattice-text-3)] tracking-wider">
          <div className="flex items-center gap-2">
            <Shield size={12} className="text-[var(--lattice-gold)]" /> LATTICE NETWORK · © 2026 · SOVEREIGN COMMUNICATIONS INFRASTRUCTURE
          </div>
          <div className="flex items-center gap-5">
            <Link to="/" className="hover:text-[var(--lattice-gold)]">Home</Link>
            <Link to="/per-il-ceo" className="hover:text-[var(--lattice-gold)]">CEO</Link>
            <Link to="/per-il-ciso" className="hover:text-[var(--lattice-gold)]">CISO</Link>
            <Link to="/per-il-legal" className="hover:text-[var(--lattice-gold)]">Legal</Link>
            <Link to="/explorer" className="hover:text-[var(--lattice-gold)]">Block Explorer</Link>
            <Link to="/privacy-policy" className="hover:text-[var(--lattice-gold)]">Privacy</Link>
            <Link to="/cookie-policy" className="hover:text-[var(--lattice-gold)]">Cookie</Link>
            <Link to="/login" className="hover:text-white">Login</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
