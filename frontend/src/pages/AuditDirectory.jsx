import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Building2, ShieldCheck, ArrowLeft, ArrowRight, Search, Sparkles } from "lucide-react";

/**
 * /audit — directory pubblica delle aziende presenti sulla rete Lattice.
 * Da qui si naviga ai singoli /audit/:slug senza dover indovinare nessuno slug.
 */
export default function AuditDirectory() {
  const [tenants, setTenants] = useState(null);
  const [err, setErr] = useState("");
  const [query, setQuery] = useState("");

  useEffect(() => {
    api.get("/tenants/public")
      .then((r) => setTenants(Array.isArray(r.data) ? r.data : []))
      .catch((e) => setErr(e?.response?.data?.detail || "Impossibile caricare la directory"));
  }, []);

  const filtered = (tenants || []).filter((t) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return (t.name || "").toLowerCase().includes(q) || (t.domain || "").toLowerCase().includes(q);
  });

  return (
    <div className="min-h-screen bg-[var(--lattice-bg)] text-white" data-testid="audit-directory-page">
      <header className="border-b hairline">
        <div className="max-w-5xl mx-auto px-6 py-5 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-4" data-testid="audit-dir-home-link">
            <img src="/lattice-logo.jpeg" alt="Lattice Network" style={{ width: 56, height: 56, borderRadius: 8 }} className="border hairline" />
            <div>
              <div className="font-display text-2xl leading-tight">Lattice Network</div>
              <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] tracking-[0.18em] uppercase mt-0.5">
                Sovereign B2B Infrastructure · Made in EU
              </div>
            </div>
          </Link>
          <Link
            to="/"
            className="font-mono-data text-[11px] uppercase tracking-[0.18em] text-[var(--lattice-text-3)] hover:text-white flex items-center gap-2"
          >
            <ArrowLeft size={12} /> indietro
          </Link>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10 space-y-8">
        <div>
          <div className="eyebrow flex items-center gap-2 text-[var(--lattice-gold)]">
            <ShieldCheck size={11} /> AUDIT PUBBLICO · DIRECTORY
          </div>
          <h1 className="font-display text-4xl sm:text-5xl mt-2">Aziende sulla rete</h1>
          <p className="text-[13px] text-[var(--lattice-text-3)] mt-4 leading-relaxed max-w-3xl">
            Ogni azienda che usa Lattice ha una pagina di audit pubblica con i suoi dati on-chain:
            numero di transazioni firmate, ultime notarizzazioni, algoritmi crittografici.
            <strong className="text-white"> Nessun contenuto di mail o messaggi è visibile.</strong>
          </p>
        </div>

        {/* CTA conversione: trasforma il visitatore due-diligence in lead */}
        <section
          data-testid="audit-join-cta"
          className="surface-elev border hairline relative overflow-hidden"
        >
          <div className="absolute top-0 left-0 right-0 h-px gold-line" />
          <div
            className="absolute -right-20 -top-20 w-80 h-80 rounded-full opacity-[0.06] pointer-events-none"
            style={{ background: "radial-gradient(circle, var(--lattice-gold) 0%, transparent 70%)" }}
          />
          <div className="px-6 py-7 sm:px-8 sm:py-8 flex flex-col md:flex-row md:items-center gap-6 relative">
            <div className="flex-1 min-w-0">
              <div className="eyebrow flex items-center gap-2 text-[var(--lattice-gold)] mb-2">
                <Sparkles size={11} /> ENTRA NELLA RETE
              </div>
              <h2 className="font-display text-2xl sm:text-3xl text-white leading-tight">
                Vuoi vedere il <span className="text-[var(--lattice-gold)]">tuo nome</span> qui sopra?
              </h2>
              <p className="text-[13px] text-[var(--lattice-text-2)] mt-3 max-w-xl leading-relaxed">
                Aggiungi la tua azienda alla rete sovrana Lattice. Le tue mail e i tuoi messaggi
                saranno cifrati post-quantum, notarizzati on-chain e validi in tribunale.
                Setup in <strong className="text-white">5 giorni lavorativi</strong>.
              </p>
            </div>
            <div className="flex flex-col sm:flex-row gap-2 shrink-0">
              <a
                href="/#demo"
                data-testid="audit-cta-demo"
                className="btn-gold inline-flex items-center justify-center gap-2 whitespace-nowrap"
                style={{ padding: "12px 22px", fontSize: 12 }}
              >
                Richiedi una demo <ArrowRight size={13} />
              </a>
              <Link
                to="/security"
                data-testid="audit-cta-howitworks"
                className="btn-ghost inline-flex items-center justify-center gap-2 whitespace-nowrap"
                style={{ padding: "12px 22px", fontSize: 12 }}
              >
                Come funziona
              </Link>
            </div>
          </div>
        </section>

        <div className="relative max-w-md">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--lattice-text-3)]" />
          <input
            data-testid="audit-dir-search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Cerca azienda o dominio…"
            className="input-sovereign pl-10"
          />
        </div>

        {err && (
          <div className="surface-elev border border-rose-500/40 bg-rose-500/5 px-5 py-4" data-testid="audit-dir-error">
            <div className="eyebrow text-rose-300 mb-1">ERRORE</div>
            <p className="text-[13px] text-[var(--lattice-text-2)]">{err}</p>
          </div>
        )}

        {tenants === null && !err && (
          <div className="font-mono-data text-[12px] text-[var(--lattice-text-3)]">Caricamento directory…</div>
        )}

        {tenants !== null && filtered.length === 0 && (
          <div className="surface-elev border hairline px-6 py-8 text-center" data-testid="audit-dir-empty">
            <Building2 size={28} className="mx-auto text-[var(--lattice-text-3)] opacity-50" />
            <p className="font-mono-data text-[12px] text-[var(--lattice-text-3)] mt-3">
              {query ? "Nessuna azienda corrisponde alla ricerca." : "Nessuna azienda registrata sulla rete."}
            </p>
          </div>
        )}

        {filtered.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3" data-testid="audit-dir-list">
            {filtered.map((t) => {
              const slug = (t.domain || "").split(".")[0] || t.tenant_id;
              return (
                <Link
                  key={t.tenant_id}
                  to={`/audit/${encodeURIComponent(slug)}`}
                  data-testid={`audit-dir-item-${t.tenant_id}`}
                  className="surface-elev border hairline px-5 py-4 flex items-start gap-3 hover:border-[var(--lattice-gold)] hover:bg-[rgba(212,175,55,0.04)] transition-all group"
                >
                  <div className="border hairline w-10 h-10 flex items-center justify-center shrink-0">
                    <Building2 size={16} className="text-[var(--lattice-gold)]" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-display text-lg text-white truncate">{t.name}</div>
                    <div className="font-mono-data text-[11px] text-[var(--lattice-gold)] truncate">{t.domain}</div>
                    <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] mt-1">
                      registrata {t.created_at?.slice(0, 10) || "—"}
                    </div>
                  </div>
                  <ArrowRight size={14} className="text-[var(--lattice-text-3)] mt-3 group-hover:text-[var(--lattice-gold)]" />
                </Link>
              );
            })}
          </div>
        )}
      </main>

      <footer className="border-t hairline mt-16">
        <div className="max-w-5xl mx-auto px-6 py-6 font-mono-data text-[11px] text-[var(--lattice-text-3)] flex flex-wrap items-center justify-between gap-3">
          <span>Lattice Network · Directory pubblica · No login</span>
          <Link to="/whitepaper" className="hover:text-[var(--lattice-gold)]" data-testid="audit-dir-whitepaper">
            Whitepaper tecnico →
          </Link>
        </div>
      </footer>
    </div>
  );
}
