import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader, SectionPanel } from "@/components/Primitives";
import { Building2, Shield, ChevronRight, Check, KeyRound, Briefcase, ShieldAlert, Scale } from "lucide-react";
import { toast } from "sonner";

function StepBadge({ n, active, done }) {
  return (
    <span className={`inline-flex items-center justify-center w-7 h-7 border rounded-full font-mono-data text-[12px] ${
      done ? "bg-[var(--lattice-gold)] text-[#0a1020] border-[var(--lattice-gold)]"
           : active ? "border-[var(--lattice-gold)] text-[var(--lattice-gold)]" : "border-[var(--lattice-border-strong)] text-[var(--lattice-text-3)]"
    }`}>
      {done ? <Check size={13} strokeWidth={3} /> : n}
    </span>
  );
}

export default function Onboarding() {
  const [tenants, setTenants] = useState([]);
  const [currentTenant, setCurrentTenant] = useState(null);
  const [step, setStep] = useState(1);

  // step 1 form
  const [name, setName] = useState("");
  const [prefix, setPrefix] = useState("");
  const [adminPrefix, setAdminPrefix] = useState("");
  const [adminDisplay, setAdminDisplay] = useState("");
  const [busy, setBusy] = useState(false);

  const loadTenants = async () => {
    try {
      const r = await api.get("/tenants");
      setTenants(r.data);
    } catch (e) { console.warn(e); }
  };

  useEffect(() => { loadTenants(); }, []);

  const submitTenant = async () => {
    setBusy(true);
    try {
      const r = await api.post("/tenants/register", {
        name: name.trim(),
        domain_prefix: prefix.trim().toLowerCase(),
        admin_lns_prefix: adminPrefix.trim().toLowerCase(),
        admin_display_name: adminDisplay.trim(),
      }, { headers: { "X-Lattice-Role": "sovereign" } });
      toast.success(`Azienda registrata! Domain: ${r.data.domain}`);
      setCurrentTenant(r.data);
      setStep(2);
      await loadTenants();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Errore registrazione");
    } finally { setBusy(false); }
  };

  const [seedBusy, setSeedBusy] = useState(false);
  const [showSeedPicker, setShowSeedPicker] = useState(false);

  // Demo prefixes used by the seed endpoint — when ALL on-chain tenants match
  // one of these, we know the chain holds only demo data and the "Cambia
  // profilo" button is safe to enable (it will wipe + reseed).
  const DEMO_PREFIXES = ["bancademo", "studiolegaledemo", "pademo", "industriademo"];
  const allTenantsAreDemo = tenants.length > 0 &&
    tenants.every((t) => DEMO_PREFIXES.some((p) => (t.domain || "").startsWith(p + ".")));

  const DEMO_PROFILES = [
    { key: "bancaria",    label: "Bancario",      sub: "Banca / Compliance / AML", icon: "🏦", desc: "AML · UIF · Vigilanza · TARGET2 · stress test EBA" },
    { key: "legale",      label: "Legale",        sub: "Studio Legale / Avvocatura", icon: "⚖️", desc: "Cause civili · NDA · M&A · ricorsi TAR" },
    { key: "pa",          label: "PA / Comune",   sub: "Amministrazione Pubblica", icon: "🏛️", desc: "Protocollo · gare · concessioni · ANAC" },
    { key: "industriale", label: "Industriale",   sub: "Manifatturiero / R&D",     icon: "🏭", desc: "Brevetti · supply chain · ISO 27001 · Industria 5.0" },
    { key: "completo",    label: "Completo",      sub: "Tutti e 4 i settori",      icon: "✨", desc: "Mix di linguaggio business generico" },
  ];

  const seedDemo = async (profile) => {
    setShowSeedPicker(false);
    setSeedBusy(true);
    try {
      // If demo data already on chain, wipe first so we don't accumulate
      // tenants across profile switches.
      if (allTenantsAreDemo) {
        await api.post("/admin/chain/reset", {}, {
          headers: { "X-Lattice-Role": "sovereign", "X-Lattice-Reset-Confirm": "WIPE_CHAIN_YES" }
        });
      }
      const r = await api.post(`/admin/chain/seed-demo?profile=${profile}`, {}, {
        headers: { "X-Lattice-Role": "sovereign", "X-Lattice-Seed-Confirm": "SEED_DEMO_YES" }
      });
      toast.success(r.data.message);
      await loadTenants();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Errore seed");
    } finally { setSeedBusy(false); }
  };

  return (
    <div className="space-y-8">
      {/* "Per chi è Lattice" — 3 role-targeted cards (CEO / CISO / Legal)
          con le frasi-pitch esatte usate nel positioning. */}
      <SectionPanel
        title="Per chi è Lattice"
        eyebrow="LATTICE NETWORK · TARGETING"
        testId="onboarding-for-who"
      >
        <div className="px-5 py-3 border-b hairline">
          <div className="font-mono-data text-[11px] text-[var(--lattice-text-3)] leading-relaxed">
            <strong className="text-white">Lattice è la rete sovrana che usa la tua azienda per comunicare.</strong> Identità verificate (LNS), posta legale (Certify), chat interna (Pulse) e audit immutabile su blockchain QBFT post-quantistica. Tutto firmato ML-DSA-65, on-premise o cloud sovrano UE.
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-0">
          {/* CEO — pitch ChatGPT verbatim */}
          <div
            data-testid="for-who-ceo"
            className="px-5 py-5 border-r-0 md:border-r hairline border-b md:border-b-0 last:border-r-0"
          >
            <div className="flex items-center gap-2">
              <Briefcase size={16} className="text-[var(--lattice-gold)]" />
              <div className="font-display text-xl text-white">CEO / Founder</div>
            </div>
            <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] uppercase tracking-[0.18em] mt-1">
              Sovranità & continuità
            </div>
            <blockquote className="text-[13px] text-white mt-3 leading-relaxed border-l-2 border-[var(--lattice-gold)] pl-3 italic">
              «Riduci il rischio di fuga dati e hai prove verificabili di ogni comunicazione importante.»
            </blockquote>
            <div className="text-[12px] text-[var(--lattice-text-2)] mt-3 leading-relaxed">
              Smetti di dipendere da fornitori extra-UE per le mail e le decisioni più importanti. Se Microsoft o Google sospendono il tuo account, la tua azienda continua a operare. Le chiavi sono tue.
            </div>
          </div>
          {/* CISO — pitch ChatGPT verbatim */}
          <div
            data-testid="for-who-ciso"
            className="px-5 py-5 border-r-0 md:border-r hairline border-b md:border-b-0 last:border-r-0"
          >
            <div className="flex items-center gap-2">
              <ShieldAlert size={16} className="text-[var(--lattice-gold)]" />
              <div className="font-display text-xl text-white">CISO / IT Security</div>
            </div>
            <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] uppercase tracking-[0.18em] mt-1">
              Controllo & isolamento
            </div>
            <blockquote className="text-[13px] text-white mt-3 leading-relaxed border-l-2 border-[var(--lattice-gold)] pl-3 italic">
              «Isoliamo completamente la comunicazione aziendale e la rendiamo verificabile crittograficamente end-to-end, con infrastruttura sotto tuo controllo.»
            </blockquote>
            <div className="text-[12px] text-[var(--lattice-text-2)] mt-3 leading-relaxed">
              Identità aziendali centralizzate, comunicazioni interne isolate da Internet aperta, audit trail crittografico indipendente, revoca immediata. Il perimetro torna definibile.
            </div>
          </div>
          {/* Legal / Compliance — pitch ChatGPT verbatim */}
          <div data-testid="for-who-legal" className="px-5 py-5">
            <div className="flex items-center gap-2">
              <Scale size={16} className="text-[var(--lattice-gold)]" />
              <div className="font-display text-xl text-white">Legal / Compliance</div>
            </div>
            <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] uppercase tracking-[0.18em] mt-1">
              Prova verificabile
            </div>
            <blockquote className="text-[13px] text-white mt-3 leading-relaxed border-l-2 border-[var(--lattice-gold)] pl-3 italic">
              «Ogni comunicazione aziendale può essere verificata nel tempo come prova immutabile, senza dipendere da provider esterni.»
            </blockquote>
            <div className="text-[12px] text-[var(--lattice-text-2)] mt-3 leading-relaxed">
              Prova opponibile in giudizio, verificabile pubblicamente, indipendente dal fornitore. Risolve i limiti della PEC (vale solo in Italia, dipende dal provider). GDPR · NIS2 · eIDAS.
            </div>
          </div>
        </div>
      </SectionPanel>

      <PageHeader
        eyebrow="ONBOARDING · TENANT REGISTRY"
        title="Registra una nuova azienda sulla rete"
        subtitle="Operatore di rete: tu fornisci dominio sovrano + keypair dell'admin. Dopodiché l'admin dell'azienda gestisce in autonomia i propri dipendenti, mail e messaggi. Tu non puoi né vedere né modificare i loro dati interni — è il principio di isolamento di Lattice. Se invece vuoi solo vedere il cruscotto operativo della rete, usa il pulsante qui a destra."
        right={
          <div className="flex items-center gap-2">
            <a
              href="/dashboard"
              data-testid="onboarding-skip-to-dashboard"
              className="btn-ghost inline-flex items-center gap-2 text-[12px]"
              title="Vai al cruscotto della rete senza registrare un'azienda"
            >
              Vai al cruscotto →
            </a>
            {step === 1 && (tenants.length === 0 || allTenantsAreDemo) && (
              <button
                data-testid={tenants.length === 0 ? "onboarding-seed-demo-open" : "onboarding-switch-demo-open"}
                onClick={() => setShowSeedPicker(true)}
                disabled={seedBusy}
                className="btn-ghost inline-flex items-center gap-2 text-[12px]"
                title={tenants.length === 0
                  ? "Popola la rete con un profilo demo settoriale"
                  : "Cancella il profilo demo attuale e carica un nuovo settore"}
              >
                {seedBusy ? "Carico…" : tenants.length === 0 ? "Carica demo settoriale" : "Cambia profilo demo"}
              </button>
            )}
          </div>
        }
      />

      {/* Demo profile picker modal */}
      {showSeedPicker && (
        <div
          data-testid="seed-picker-overlay"
          onClick={() => setShowSeedPicker(false)}
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-6"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="surface-elev border hairline max-w-3xl w-full relative"
            data-testid="seed-picker-modal"
          >
            <div className="absolute top-0 left-0 right-0 h-px gold-line" />
            <div className="px-6 py-5 border-b hairline flex items-center justify-between">
              <div>
                <div className="eyebrow text-[var(--lattice-gold)]">
                  {allTenantsAreDemo ? "CAMBIA PROFILO DEMO · WIPE + RELOAD" : "PROFILO DEMO · SELEZIONA SETTORE"}
                </div>
                <h2 className="font-display text-2xl text-white mt-1">
                  {allTenantsAreDemo ? "Cambia il vocabolario della demo" : "Mostra ciò che fa per il suo settore"}
                </h2>
                <p className="text-[12px] text-[var(--lattice-text-3)] mt-1">
                  {allTenantsAreDemo
                    ? "I dati demo attuali verranno cancellati e sostituiti con il nuovo profilo. ~3 secondi."
                    : "Ogni profilo carica 1 azienda demo + 3 dipendenti + 50 mail Certify + 200 messaggi Pulse con linguaggio specifico del settore. ~2 secondi."}
                </p>
              </div>
              <button
                onClick={() => setShowSeedPicker(false)}
                className="text-[var(--lattice-text-3)] hover:text-white"
                data-testid="seed-picker-close"
                aria-label="Chiudi"
              >✕</button>
            </div>
            <div className="px-6 py-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {DEMO_PROFILES.map((p) => (
                <button
                  key={p.key}
                  data-testid={`seed-profile-${p.key}`}
                  onClick={() => seedDemo(p.key)}
                  disabled={seedBusy}
                  className="border hairline px-4 py-4 text-left hover:border-[var(--lattice-gold)] hover:bg-[rgba(212,175,55,0.04)] transition-all group disabled:opacity-50"
                >
                  <div className="text-2xl mb-2">{p.icon}</div>
                  <div className="font-display text-lg text-white">{p.label}</div>
                  <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] mt-0.5 uppercase tracking-wider">{p.sub}</div>
                  <div className="text-[11px] text-[var(--lattice-text-3)] mt-2 leading-snug">{p.desc}</div>
                </button>
              ))}
            </div>
            <div className="px-6 py-3 border-t hairline font-mono-data text-[10px] text-[var(--lattice-text-3)]">
              {allTenantsAreDemo
                ? <>⚠️ <strong className="text-amber-300">Tutti i dati demo correnti verranno cancellati.</strong> Le aziende non-demo restano intatte (al momento ce ne sono 0).</>
                : <>Suggerimento: per una demo a un cliente Banca scegli <span className="text-[var(--lattice-gold)]">Bancario</span>, per uno studio legale <span className="text-[var(--lattice-gold)]">Legale</span>, ecc. Le mail e i messaggi saranno tutti in linguaggio mirato.</>}
            </div>
          </div>
        </div>
      )}

      {/* Stepper */}
      <div className="flex items-center gap-4 surface px-5 py-3" data-testid="onboarding-stepper">
        <div className="flex items-center gap-2"><StepBadge n={1} active={step === 1} done={step > 1} /><span className="font-mono-data text-[11px] text-white">Crea azienda</span></div>
        <ChevronRight size={14} className="text-[var(--lattice-text-3)]" />
        <div className="flex items-center gap-2"><StepBadge n={2} active={step === 2} done={false} /><span className="font-mono-data text-[11px] text-white">Consegna keypair admin</span></div>
        <span className="ml-auto font-mono-data text-[10px] text-[var(--lattice-text-3)]">{tenants.length} aziende sulla rete</span>
      </div>

      {/* Existing tenants — read-only directory, NO employees, NO drilldown */}
      {step === 1 && tenants.length > 0 && (
        <SectionPanel title="Aziende già registrate sulla rete" eyebrow="ONBOARDED TENANTS · DIRECTORY READ-ONLY" testId="onboarding-tenants-list">
          <div className="px-5 py-3 border-b hairline">
            <div className="font-mono-data text-[11px] text-[var(--lattice-text-3)] leading-relaxed">
              <strong className="text-emerald-300">Isolamento totale.</strong> Dopo la registrazione, ogni azienda è autonoma.
              Tu (operatore di rete) <strong className="text-white">non puoi vedere</strong> i loro dipendenti, mail o messaggi — solo che esistono sulla rete.
            </div>
          </div>
          <div>
            {tenants.map((t) => (
              <div
                key={t.tenant_id}
                data-testid={`tenant-row-${t.tenant_id}`}
                className="w-full text-left px-5 py-3 border-b hairline flex items-center gap-3"
              >
                <Building2 size={14} className="text-[var(--lattice-gold)] shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-[14px] text-white truncate">{t.name}</div>
                  <div className="font-mono-data text-[11px] text-[var(--lattice-text-3)] truncate">{t.domain} · {t.tenant_id}</div>
                </div>
                <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] text-right">
                  registrata<br />{(t.created_at || "").slice(0, 10)}
                </div>
              </div>
            ))}
          </div>
        </SectionPanel>
      )}

      {/* Step 1 — register company */}
      {step === 1 && (
        <SectionPanel title="Nuova azienda" eyebrow="STEP 1 · CREATE TENANT" testId="onboarding-step1">
          <div className="px-5 py-5 space-y-4 max-w-2xl">
            <div>
              <label className="eyebrow block mb-2">Nome azienda</label>
              <input
                data-testid="onboarding-name"
                className="input-sovereign"
                placeholder="es. ACME Industries SpA"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div>
              <label className="eyebrow block mb-2">Slug dominio</label>
              <div className="flex items-center gap-2">
                <input
                  data-testid="onboarding-prefix"
                  className="input-sovereign flex-1"
                  placeholder="acme"
                  value={prefix}
                  onChange={(e) => setPrefix(e.target.value.replace(/[^a-z0-9-]/gi, "").toLowerCase())}
                />
              </div>
              <p className="font-mono-data text-[10px] text-[var(--lattice-text-4)] mt-1">
                Dominio finale: <span className="text-[var(--lattice-gold)]">{(prefix || "acme") + ".lns"}</span>
              </p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="eyebrow block mb-2">LNS prefisso del primo admin</label>
                <input
                  data-testid="onboarding-admin-prefix"
                  className="input-sovereign"
                  placeholder="ceo"
                  value={adminPrefix}
                  onChange={(e) => setAdminPrefix(e.target.value.replace(/[^a-z0-9.-]/gi, "").toLowerCase())}
                />
              </div>
              <div>
                <label className="eyebrow block mb-2">Nome reale dell'admin</label>
                <input
                  data-testid="onboarding-admin-display"
                  className="input-sovereign"
                  placeholder="Mario Bianchi"
                  value={adminDisplay}
                  onChange={(e) => setAdminDisplay(e.target.value)}
                />
              </div>
            </div>
            <button
              data-testid="onboarding-submit-tenant"
              onClick={submitTenant}
              disabled={busy || !name || !prefix || !adminPrefix || !adminDisplay}
              className="btn-gold inline-flex items-center gap-2"
            >
              <Shield size={13} /> {busy ? "Registro…" : "Registra azienda"}
            </button>
            <p className="font-mono-data text-[10px] text-[var(--lattice-text-4)]">
              L'azienda + il primo admin verranno notarizzati on-chain con firma ML-DSA-65. La keypair dell'admin viene consegnata UNA SOLA volta in formato JSON da scaricare.
            </p>
          </div>
        </SectionPanel>
      )}

      {/* Step 2 — keypair delivery */}
      {step === 2 && currentTenant && (
        <>
          <SectionPanel
            title={`${currentTenant.name} · registrata sulla rete`}
            eyebrow="STEP 2 · KEYPAIR ADMIN · UNA SOLA VOLTA"
            testId="onboarding-current-tenant"
          >
            <div className="px-5 py-4 grid grid-cols-1 md:grid-cols-2 gap-3 font-mono-data text-[11px]">
              <div>
                <div className="text-[var(--lattice-text-3)] uppercase tracking-wider text-[10px]">Tenant ID</div>
                <div className="text-white mt-1 break-all">{currentTenant.tenant_id}</div>
              </div>
              <div>
                <div className="text-[var(--lattice-text-3)] uppercase tracking-wider text-[10px]">Primo admin</div>
                <div className="text-[var(--lattice-gold)] mt-1 break-all">{currentTenant.admin_lns}</div>
              </div>
              <div>
                <div className="text-[var(--lattice-text-3)] uppercase tracking-wider text-[10px]">DID</div>
                <div className="text-white mt-1 break-all">{currentTenant.admin_did}</div>
              </div>
              <div>
                <div className="text-[var(--lattice-text-3)] uppercase tracking-wider text-[10px]">Block index</div>
                <div className="text-white mt-1">#{currentTenant.block_index}</div>
              </div>
            </div>
          </SectionPanel>

          <div className="border border-emerald-500/40 bg-emerald-500/5 px-5 py-4 font-mono-data text-[12px] text-emerald-200 leading-relaxed" data-testid="tenant-created-banner">
            <strong className="text-emerald-100">Azienda registrata.</strong> I dipendenti li gestirà l'admin dell'azienda dopo aver fatto login con la sua keypair. Tu non puoi né vedere né registrare i loro dipendenti — è il principio di isolamento di Lattice.
          </div>

          {currentTenant.admin_keypair_json && (
            <div className="surface-elev border hairline p-6 space-y-4" data-testid="admin-keypair-box">
              <div className="eyebrow flex items-center gap-2">
                <KeyRound size={11} className="text-[var(--lattice-gold)]" /> CHIAVE ADMIN · DA CONSEGNARE
              </div>
              <p className="text-[13px] text-[var(--lattice-text-2)] leading-relaxed max-w-3xl">
                Questo file <code className="text-[var(--lattice-gold)]">.keypair.json</code> contiene la chiave segreta ML-DSA-65 dell'admin di <strong className="text-white">{currentTenant.name}</strong>.
                È <strong className="text-rose-300">l'unica copia esistente</strong> — il server non la conserva.
                Consegnalo via canale sicuro (di persona / messaggistica privata) all'admin. Senza questo file, lui non potrà mai più accedere e non è recuperabile.
              </p>
              <button
                data-testid="download-admin-keypair"
                onClick={() => {
                  const blob = new Blob([JSON.stringify(currentTenant.admin_keypair_json, null, 2)], { type: "application/json" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `${currentTenant.admin_lns}.keypair.json`;
                  document.body.appendChild(a);
                  a.click();
                  a.remove();
                  URL.revokeObjectURL(url);
                  toast.success("Keypair scaricata. Consegna SUBITO all'admin via canale sicuro.");
                }}
                className="btn-gold inline-flex items-center gap-2"
              >
                <KeyRound size={13} /> Scarica .keypair.json
              </button>
            </div>
          )}

          <div className="flex items-center justify-between">
            <button
              onClick={() => { setStep(1); setCurrentTenant(null); setName(""); setPrefix(""); setAdminPrefix(""); setAdminDisplay(""); }}
              data-testid="onboarding-back"
              className="btn-ghost"
            >
              ← Registra un'altra azienda
            </button>
          </div>
        </>
      )}
    </div>
  );
}
