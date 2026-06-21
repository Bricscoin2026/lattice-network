import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Building2, Users, MailCheck, Radio, ShieldCheck, Activity, ChevronRight, IdCard, KeyRound, Globe2, Lock } from "lucide-react";
import { api, fmtNumber } from "@/lib/api";
import { loadSession } from "@/lib/pqcAuth";

function KpiTile({ label, value, sub, Icon, tone = "gold", tid }) {
  const toneClass = {
    gold: "text-[var(--lattice-gold)]",
    cyan: "text-cyan-300",
    rose: "text-rose-300",
    green: "text-emerald-300",
  }[tone];
  return (
    <div className="surface-elev border hairline p-5 relative overflow-hidden" data-testid={tid}>
      <div className="absolute top-0 left-0 right-0 h-px gold-line opacity-50" />
      <div className="flex items-start justify-between">
        <div>
          <div className="eyebrow mb-2 flex items-center gap-2">
            <Icon size={11} className={toneClass} /> {label}
          </div>
          <div className={`font-display text-4xl ${toneClass} leading-none`}>{value}</div>
          {sub && <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] mt-2">{sub}</div>}
        </div>
      </div>
    </div>
  );
}

function QuickAction({ to, Icon, title, desc, tid }) {
  return (
    <Link
      to={to}
      data-testid={tid}
      className="surface-elev border hairline p-4 flex items-start gap-3 hover:border-[var(--lattice-gold)] hover:bg-[rgba(212,175,55,0.04)] transition-all group"
    >
      <div className="border hairline w-9 h-9 flex items-center justify-center shrink-0">
        <Icon size={16} className="text-[var(--lattice-gold)]" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-sans-ui text-[13px] text-white">{title}</div>
        <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] mt-1 truncate">{desc}</div>
      </div>
      <ChevronRight size={14} className="text-[var(--lattice-text-3)] mt-2 group-hover:text-[var(--lattice-gold)]" />
    </Link>
  );
}

export default function TenantDashboard() {
  const session = loadSession();
  const tenantId = session?.tenant_id;
  const [stats, setStats] = useState(null);
  const [employees, setEmployees] = useState([]);
  const [network, setNetwork] = useState([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!tenantId) return;
    let alive = true;
    (async () => {
      try {
        const [s, e, n] = await Promise.all([
          api.get(`/tenants/${tenantId}/stats`),
          api.get(`/tenants/${tenantId}/employees`).catch(() => ({ data: [] })),
          api.get(`/tenants/public`).catch(() => ({ data: [] })),
        ]);
        if (!alive) return;
        setStats(s.data);
        setEmployees(e.data || []);
        setNetwork(n.data || []);
      } catch (er) {
        if (alive) setErr(er?.response?.data?.detail || "Impossibile caricare i KPI azienda");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [tenantId]);

  if (!tenantId) {
    return (
      <div className="surface-elev border hairline p-8 max-w-xl">
        <h2 className="font-display text-2xl text-white">Nessuna azienda associata</h2>
        <p className="text-[13px] text-[var(--lattice-text-3)] mt-2">
          Il tuo account non è collegato a un tenant. Effettua il login con la chiave .keypair.json fornita dalla tua azienda.
        </p>
        <Link to="/login" data-testid="tenant-dash-login" className="btn-gold inline-flex items-center gap-2 mt-4">
          <KeyRound size={13} /> Vai al login
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-8" data-testid="tenant-dashboard">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <div className="eyebrow flex items-center gap-2 mb-1">
            <Building2 size={11} className="text-[var(--lattice-gold)]" /> WORKSPACE AZIENDALE
          </div>
          <h1 className="font-display text-4xl text-white">
            {stats?.tenant_name || (loading ? "…" : "Azienda")}
          </h1>
          <div className="font-mono-data text-[11px] text-[var(--lattice-text-3)] mt-1">
            dominio: <span className="text-[var(--lattice-gold)]">{stats?.domain || "—"}</span>
            <span className="mx-2 opacity-50">·</span>
            tenant: <span>{tenantId}</span>
            <span className="mx-2 opacity-50">·</span>
            ruolo: <span className="text-white uppercase">{session?.role || "—"}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="pill pill-gold flex items-center gap-2">
            <ShieldCheck size={11} /> ML-DSA-65 · ZK-RLN · MIXNET
          </div>
        </div>
      </div>

      {err && (
        <div className="border border-red-500/40 bg-red-500/5 px-4 py-3 text-[12px] text-red-300" data-testid="tenant-dash-error">
          {err}
        </div>
      )}

      {/* KPI grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiTile
          label="Dipendenti attivi"
          value={loading ? "…" : fmtNumber(stats?.employees_active || 0)}
          sub={`${stats?.employees_total || 0} totali · ${stats?.employees_revoked || 0} revocati`}
          Icon={Users}
          tone="gold"
          tid="kpi-employees"
        />
        <KpiTile
          label="Mail Certify"
          value={loading ? "…" : fmtNumber(stats?.certify_mails_total || 0)}
          sub="notarizzate on-chain"
          Icon={MailCheck}
          tone="cyan"
          tid="kpi-certify"
        />
        <KpiTile
          label="Messaggi Pulse"
          value={loading ? "…" : fmtNumber(stats?.pulse_messages_total || 0)}
          sub="cifrati end-to-end"
          Icon={Radio}
          tone="green"
          tid="kpi-pulse"
        />
        <KpiTile
          label="Tx on-chain"
          value={loading ? "…" : fmtNumber(stats?.on_chain_tx_total || 0)}
          sub="firmate ML-DSA-65"
          Icon={Activity}
          tone="rose"
          tid="kpi-onchain"
        />
      </div>

      {/* Quick actions */}
      <div>
        <div className="eyebrow mb-3">SCORCIATOIE</div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <QuickAction
            to="/lns"
            Icon={IdCard}
            title="Gestisci dipendenti"
            desc="Aggiungi · revoca · cambia ruolo"
            tid="qa-lns"
          />
          <QuickAction
            to="/certify"
            Icon={MailCheck}
            title="Mail certificate"
            desc="Componi · notarizza · ricevi"
            tid="qa-certify"
          />
          <QuickAction
            to="/pulse"
            Icon={Radio}
            title="Pulse messaging"
            desc="Conversazioni cifrate"
            tid="qa-pulse"
          />
        </div>
      </div>

      {/* Ripartizione ruoli + ultimi dipendenti */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="surface-elev border hairline p-5 lg:col-span-1">
          <div className="eyebrow mb-3">RIPARTIZIONE RUOLI</div>
          <div className="space-y-2">
            {stats?.roles_breakdown && Object.keys(stats.roles_breakdown).length > 0 ? (
              Object.entries(stats.roles_breakdown).map(([role, n]) => {
                const total = stats.employees_total || 1;
                const pct = Math.round((n / total) * 100);
                return (
                  <div key={role} data-testid={`role-${role}`}>
                    <div className="flex justify-between font-mono-data text-[11px]">
                      <span className="uppercase tracking-[0.15em] text-[var(--lattice-text-2)]">{role}</span>
                      <span className="text-[var(--lattice-gold)]">{n} · {pct}%</span>
                    </div>
                    <div className="h-1 bg-[rgba(255,255,255,0.05)] mt-1">
                      <div className="h-full bg-[var(--lattice-gold)]" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="font-mono-data text-[11px] text-[var(--lattice-text-3)]">
                Nessun dipendente registrato. <Link to="/lns" className="text-[var(--lattice-gold)]">Aggiungi il primo →</Link>
              </div>
            )}
          </div>
        </div>

        <div className="surface-elev border hairline p-5 lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <div className="eyebrow">DIPENDENTI RECENTI</div>
            <Link to="/lns" className="font-mono-data text-[10px] text-[var(--lattice-gold)] hover:underline" data-testid="see-all-lns">
              vedi tutti →
            </Link>
          </div>
          {employees.length === 0 ? (
            <div className="font-mono-data text-[11px] text-[var(--lattice-text-3)]">
              Nessun dipendente. <Link to="/lns" className="text-[var(--lattice-gold)]">Registrane uno →</Link>
            </div>
          ) : (
            <table className="w-full text-[12px]" data-testid="employees-recent-table">
              <thead>
                <tr className="text-[var(--lattice-text-3)] font-mono-data text-[10px] uppercase tracking-[0.1em]">
                  <th className="text-left py-2 border-b hairline">LNS</th>
                  <th className="text-left py-2 border-b hairline">Ruolo</th>
                  <th className="text-left py-2 border-b hairline">Stato</th>
                </tr>
              </thead>
              <tbody>
                {employees.slice(0, 6).map((emp) => (
                  <tr key={emp.lns_name} className="border-b hairline last:border-0">
                    <td className="py-2 font-mono-data text-[var(--lattice-gold)]">{emp.lns_name}</td>
                    <td className="py-2 font-mono-data text-[var(--lattice-text-2)] uppercase text-[10px]">{emp.role || "—"}</td>
                    <td className="py-2 font-mono-data text-[10px]">
                      <span className={emp.status === "REVOKED" ? "text-rose-300" : "text-emerald-300"}>
                        {emp.status || "ATTIVO"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Aziende sulla rete Lattice — solo nomi, ZERO dati */}
      <div className="surface-elev border hairline p-5" data-testid="network-companies">
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="eyebrow flex items-center gap-2"><Globe2 size={11} className="text-[var(--lattice-gold)]" /> AZIENDE SULLA RETE LATTICE</div>
            <p className="text-[11px] text-[var(--lattice-text-3)] mt-1 leading-relaxed">
              <Lock size={9} className="inline mr-1 text-emerald-400" />
              <strong className="text-white">{network.length}</strong> aziende usano Lattice. Vedi solo il nome — <strong className="text-white">nessun dato</strong> delle altre aziende è accessibile.
              Ogni isola è completamente isolata: nessuno può scriverti se non fa parte di <span className="text-[var(--lattice-gold)]">{stats?.domain || "—"}</span>.
            </p>
          </div>
          <div className="pill pill-gold flex items-center gap-2">
            <ShieldCheck size={11} /> ISOLAMENTO TOTALE
          </div>
        </div>
        {network.length === 0 ? (
          <div className="font-mono-data text-[11px] text-[var(--lattice-text-3)]">Caricamento…</div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2 mt-2">
            {network.map((c) => {
              const isMe = c.tenant_id === tenantId;
              return (
                <div
                  key={c.tenant_id}
                  data-testid={`net-company-${c.tenant_id}`}
                  className={`border hairline px-3 py-2 ${isMe ? "bg-[rgba(212,175,55,0.08)] border-[var(--lattice-gold)]" : "surface-2"}`}
                >
                  <div className="flex items-center gap-2">
                    <Building2 size={12} className={isMe ? "text-[var(--lattice-gold)]" : "text-[var(--lattice-text-3)]"} />
                    <div className="min-w-0 flex-1">
                      <div className={`text-[12px] truncate ${isMe ? "text-white font-bold" : "text-white"}`}>{c.name}</div>
                      <div className="font-mono-data text-[9px] text-[var(--lattice-gold)] truncate">{c.domain}</div>
                    </div>
                    {isMe && <span className="font-mono-data text-[9px] text-emerald-300">TU</span>}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
