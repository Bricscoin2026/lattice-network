import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "@/lib/api";
import { ShieldCheck, Building2, Calendar, Users, Boxes, Hash, ArrowLeft, ExternalLink, ArrowRight, Server, CheckCircle2 } from "lucide-react";

function Stat({ label, value, tid }) {
  return (
    <div data-testid={tid} className="border hairline px-5 py-5 surface-elev relative">
      <div className="absolute top-0 left-0 right-0 h-px gold-line opacity-40" />
      <div className="eyebrow text-[10px] mb-2">{label}</div>
      <div className="font-display text-4xl text-white leading-none">{value}</div>
    </div>
  );
}

export default function AuditPublic() {
  const { slug } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [suggestions, setSuggestions] = useState([]);

  useEffect(() => {
    api.get(`/audit/public/${encodeURIComponent(slug)}`)
      .then((r) => setData(r.data))
      .catch((e) => {
        setErr(e?.response?.data?.detail || "Azienda non trovata sulla rete");
        api.get("/tenants/public")
          .then((r) => setSuggestions(Array.isArray(r.data) ? r.data.slice(0, 6) : []))
          .catch(() => setSuggestions([]));
      });
  }, [slug]);

  return (
    <div className="min-h-screen bg-[var(--lattice-bg)] text-white">
      {/* top bar — logo grande + brand */}
      <header className="border-b hairline">
        <div className="max-w-5xl mx-auto px-6 py-5 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-4" data-testid="audit-home-link">
            <img src="/lattice-logo.jpeg" alt="Lattice Network" style={{ width: 56, height: 56, borderRadius: 8 }} className="border hairline" />
            <div>
              <div className="font-display text-2xl leading-tight">Lattice Network</div>
              <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] tracking-[0.18em] uppercase mt-0.5">
                Sovereign B2B Infrastructure · Made in EU
              </div>
            </div>
          </Link>
          <Link
            to="/audit"
            className="font-mono-data text-[11px] uppercase tracking-[0.18em] text-[var(--lattice-text-3)] hover:text-white flex items-center gap-2"
          >
            <ArrowLeft size={12} /> directory
          </Link>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10 space-y-10" data-testid="audit-page">
        <div>
          <div className="eyebrow flex items-center gap-2 text-[var(--lattice-gold)]">
            <ShieldCheck size={11} /> AUDIT PUBBLICO · DUE DILIGENCE
          </div>
          <h1 className="font-display text-4xl sm:text-5xl mt-2">
            {data?.tenant?.name || (err ? "Azienda non trovata" : "Caricamento…")}
          </h1>
          {data?.tenant?.domain && (
            <div className="flex items-center gap-3 mt-3">
              <span className="font-mono-data text-[13px] text-[var(--lattice-gold)]">
                {data.tenant.domain}
              </span>
              <span className="inline-flex items-center gap-1.5 px-2 py-1 border border-emerald-500/40 bg-emerald-500/5 text-emerald-300 font-mono-data text-[10px] tracking-[0.15em] uppercase" data-testid="audit-verified-badge">
                <CheckCircle2 size={11} /> Verificato on-chain
              </span>
            </div>
          )}
          <p className="text-[14px] text-[var(--lattice-text-2)] mt-5 leading-relaxed max-w-3xl">
            Questa pagina espone esclusivamente dati pubblici notarizzati sulla blockchain Lattice:
            numero di transazioni firmate dai dipendenti, altezza del blocco corrente, firme
            post-quantistiche ML-DSA-65 verificabili. <strong className="text-white">Nessun contenuto di
            mail, messaggi o documenti viene mai esposto.</strong>
          </p>
        </div>

        {err && (
          <div className="surface-elev border border-rose-500/40 bg-rose-500/5 px-5 py-4" data-testid="audit-error">
            <div className="eyebrow text-rose-300 mb-1">AZIENDA NON TROVATA</div>
            <p className="text-[13px] text-[var(--lattice-text-2)]">
              Lo slug <code className="font-mono-data text-[var(--lattice-gold)]">{slug}</code> non corrisponde
              a nessuna azienda registrata su Lattice. {suggestions.length > 0 && "Prova una di queste:"}
            </p>
            {suggestions.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-4" data-testid="audit-suggestions">
                {suggestions.map((t) => {
                  const sslug = (t.domain || "").split(".")[0] || t.tenant_id;
                  return (
                    <Link
                      key={t.tenant_id}
                      to={`/audit/${encodeURIComponent(sslug)}`}
                      data-testid={`audit-suggest-${t.tenant_id}`}
                      className="border hairline px-3 py-2 flex items-center gap-2 hover:border-[var(--lattice-gold)] hover:bg-[rgba(212,175,55,0.04)] transition-all group"
                    >
                      <Building2 size={13} className="text-[var(--lattice-gold)] shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="text-[13px] text-white truncate">{t.name}</div>
                        <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] truncate">{t.domain}</div>
                      </div>
                      <ArrowRight size={12} className="text-[var(--lattice-text-3)] group-hover:text-[var(--lattice-gold)]" />
                    </Link>
                  );
                })}
              </div>
            )}
            <div className="mt-4 flex flex-wrap gap-2">
              <Link
                to="/audit"
                data-testid="audit-back-to-dir"
                className="px-3 py-2 border border-[var(--lattice-gold)] text-[var(--lattice-gold)] font-mono-data text-[10px] tracking-[0.18em] uppercase hover:bg-[rgba(212,175,55,0.08)]"
              >
                Vedi tutte le aziende →
              </Link>
            </div>
          </div>
        )}

        {data && (
          <>
            <section className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <Stat label="DIPENDENTI" value={data.footprint.employees} tid="audit-employees" />
              <Stat label="TX ON-CHAIN" value={data.footprint.transactions_total} tid="audit-tx-total" />
              <Stat label="BLOCK HEIGHT" value={data.network.block_height} tid="audit-block-height" />
            </section>

            <section className="surface-elev border hairline relative">
              <div className="absolute top-0 left-0 right-0 h-px gold-line" />
              <header className="px-6 py-5 border-b hairline">
                <div className="eyebrow flex items-center gap-2 text-[var(--lattice-gold)]">
                  <Building2 size={11} /> METADATA AZIENDA
                </div>
              </header>
              <div className="px-6 py-5 grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-3 font-mono-data text-[12px]">
                <div>
                  <div className="eyebrow text-[10px]">RAGIONE SOCIALE</div>
                  <div className="text-white mt-1">{data.tenant.name}</div>
                </div>
                <div>
                  <div className="eyebrow text-[10px]">DOMINIO LNS</div>
                  <div className="text-white mt-1 break-all">{data.tenant.domain}</div>
                </div>
                <div>
                  <div className="eyebrow text-[10px] flex items-center gap-1"><Calendar size={9} /> REGISTRATA IL</div>
                  <div className="text-white mt-1">{data.tenant.registered_at?.slice(0, 19).replace("T", " ") || "—"}</div>
                </div>
                <div>
                  <div className="eyebrow text-[10px]">TENANT-ID PARZIALE</div>
                  <div className="text-[var(--lattice-text-2)] mt-1">{data.tenant.tenant_id_short}</div>
                </div>
              </div>
            </section>

            <section className="surface-elev border hairline relative" data-testid="audit-recent-tx">
              <div className="absolute top-0 left-0 right-0 h-px gold-line" />
              <header className="px-6 py-5 border-b hairline">
                <div className="eyebrow flex items-center gap-2 text-[var(--lattice-gold)]">
                  <Hash size={11} /> ULTIME 10 TRANSAZIONI ON-CHAIN
                </div>
                <p className="text-[12px] text-[var(--lattice-text-3)] mt-2">
                  Hash crittografici già pubblicati sulla catena. Nessun contenuto in chiaro.
                </p>
              </header>
              <div className="overflow-x-auto">
                <table className="lattice-table">
                  <thead>
                    <tr>
                      <th>#BLOCK</th>
                      <th>TX</th>
                      <th>KIND</th>
                      <th>FIRMATARIO</th>
                      <th>HASH DOC</th>
                      <th>ALG</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.footprint.recent_transactions.length === 0 && (
                      <tr><td colSpan={6} className="text-center py-6 font-mono-data text-[12px] text-[var(--lattice-text-3)]">
                        Nessuna TX da questo dominio.
                      </td></tr>
                    )}
                    {data.footprint.recent_transactions.map((tx) => (
                      <tr key={tx.tx_id} data-testid={`audit-tx-${tx.tx_id}`}>
                        <td className="font-mono-data text-[var(--lattice-gold)]">{tx.block_index}</td>
                        <td className="font-mono-data text-[11px] text-[var(--lattice-text-2)]">{tx.tx_id?.slice(0, 18)}…</td>
                        <td><span className="pill pill-slate">{tx.kind}</span></td>
                        <td className="font-mono-data text-[11px]">{tx.signer_short}</td>
                        <td className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">{tx.doc_hash_short}…</td>
                        <td className="font-mono-data text-[10px] text-emerald-300">{tx.signed_with}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="surface-elev border hairline">
              <div className="px-6 py-5">
                <div className="eyebrow text-[var(--lattice-gold)] mb-3">PROPRIETÀ DELLA RETE</div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono-data text-[12px]">
                  <div>
                    <div className="eyebrow text-[10px]">CHAIN ID</div>
                    <div className="text-white mt-1">{data.network.chain_id}</div>
                  </div>
                  <div>
                    <div className="eyebrow text-[10px]">CONSENSO</div>
                    <div className="text-white mt-1">{data.network.consensus}</div>
                  </div>
                  <div>
                    <div className="eyebrow text-[10px]">ALGORITMO FIRMA</div>
                    <div className="text-white mt-1">{data.network.pqc_algorithm} · NIST FIPS 204</div>
                  </div>
                </div>
                <div className="mt-4 pt-4 border-t hairline">
                  <p className="text-[12px] text-[var(--lattice-text-3)] leading-relaxed">
                    Verificato il <strong className="text-white">{data.checked_at?.slice(0, 19).replace("T", " ")}</strong> ·
                    Per un audit crittografico completo è disponibile il whitepaper tecnico in PDF.
                  </p>
                </div>
              </div>
            </section>

            <div className="flex flex-wrap items-center gap-3">
              <Link
                to="/whitepaper"
                data-testid="audit-whitepaper-link"
                className="px-4 py-2 border border-[var(--lattice-gold)] text-[var(--lattice-gold)] font-mono-data text-[11px] tracking-[0.18em] uppercase hover:bg-[rgba(212,175,55,0.08)] flex items-center gap-2"
              >
                Leggi il whitepaper <ExternalLink size={12} />
              </Link>
              <Link
                to="/audit"
                data-testid="audit-dir-link"
                className="px-4 py-2 border hairline text-[var(--lattice-text-2)] font-mono-data text-[11px] tracking-[0.18em] uppercase hover:text-white"
              >
                Altre aziende sulla rete
              </Link>
            </div>
          </>
        )}

        {/* On-premise reassurance — visible on every audit page */}
        <section className="surface-elev border hairline relative overflow-hidden" data-testid="audit-onpremise">
          <div className="absolute top-0 left-0 right-0 h-px gold-line opacity-60" />
          <div className="px-6 py-5 flex items-start gap-4">
            <div className="border hairline w-11 h-11 flex items-center justify-center shrink-0 bg-[rgba(212,175,55,0.04)]">
              <Server size={18} className="text-[var(--lattice-gold)]" />
            </div>
            <div>
              <div className="eyebrow text-[var(--lattice-gold)] mb-1">INFRASTRUTTURA SOVRANA</div>
              <h3 className="font-display text-xl text-white">Installato dentro l&apos;azienda</h3>
              <p className="text-[13px] text-[var(--lattice-text-2)] mt-2 leading-relaxed">
                L&apos;intero stack Lattice — applicazione, blockchain, validatori e mixnet — gira
                dentro il data center dell&apos;azienda iscritta. <strong className="text-white">Nessun dato
                aziendale resta su server di terze parti</strong>: i blocchi qui referenziati sono
                replicati esclusivamente sui nodi controllati dall&apos;organizzazione e dai suoi peer
                consorziati.
              </p>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t hairline mt-16">
        <div className="max-w-5xl mx-auto px-6 py-6 font-mono-data text-[11px] text-[var(--lattice-text-3)] flex flex-wrap items-center justify-between gap-3">
          <span>Lattice Network · Sovereign B2B PQC infrastructure · Made in EU</span>
          <span>Audit pubblico · No login · Solo dati on-chain</span>
        </div>
      </footer>
    </div>
  );
}
