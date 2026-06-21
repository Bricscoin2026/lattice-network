import { useEffect, useState } from "react";
import { useLang } from "@/i18n/LangProvider";
import { api, fmtNumber, fmtRelative } from "@/lib/api";
import { PageHeader, StatPanel, SectionPanel, EmptyRow } from "@/components/Primitives";
import { TID } from "@/constants/lattice-testids";
import { Building2, Server, Users, Coins, Lock, ShieldCheck } from "lucide-react";

const fmtEur = (n) => "€" + (n || 0).toLocaleString("it-IT");

export default function Vendor() {
  const { lang } = useLang();
  const [stats, setStats] = useState(null);
  const [tenants, setTenants] = useState([]);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const [s, t] = await Promise.all([
          api.get("/vendor/stats"),
          api.get("/vendor/tenants"),
        ]);
        if (!alive) return;
        setStats(s.data);
        setTenants(t.data);
      } catch (e) {
        console.error(e);
      }
    };
    load();
    const id = setInterval(load, 8000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  const subtitle = lang === "it"
    ? "Cruscotto operativo del vendor Lattice Sovereign Networks. Tenants attivi, nodi in esercizio, posti licenziati, MRR/ARR. Nessun payload di mail, nessun ciphertext Pulse, nessuna chiave LNS dei clienti: solo metadati operativi."
    : "Lattice Sovereign Networks vendor operations console. Active tenants, live nodes, licensed seats, MRR/ARR. No customer mail bodies, no Pulse ciphertext, no LNS secret keys — only operational metadata.";

  return (
    <div className="space-y-8">
      <PageHeader eyebrow="VENDOR OPERATIONS · ZERO-KNOWLEDGE" title="Vendor Console" subtitle={subtitle} />

      {stats && (
        <div data-testid={TID.vendorResidencyBanner} className="surface px-5 py-4 flex items-start gap-4 border-l-2" style={{ borderLeftColor: "var(--lattice-gold)" }}>
          <Lock size={16} className="text-[var(--lattice-gold)] mt-0.5 shrink-0" />
          <div>
            <div className="eyebrow text-[var(--lattice-gold)] mb-1">DATA RESIDENCY · SOVEREIGN BY DESIGN</div>
            <p className="text-[12px] text-[var(--lattice-text-2)] leading-relaxed max-w-4xl">{stats.data_residency}</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatPanel
          testId={TID.vendorKpiTenants}
          icon={Building2}
          accent
          label="Tenants"
          value={stats ? fmtNumber(stats.tenants_total) : "—"}
          sub={stats ? `${stats.tenants_healthy} healthy · ${stats.tenants_degraded} degraded · ${stats.tenants_offline} offline` : "loading…"}
        />
        <StatPanel
          testId={TID.vendorKpiNodes}
          icon={Server}
          label="Nodi Attivi"
          value={stats ? `${fmtNumber(stats.nodes_active)} / ${fmtNumber(stats.nodes_total)}` : "—"}
          sub="Nodi sovrani · cluster aziendale"
        />
        <StatPanel
          testId={TID.vendorKpiSeats}
          icon={Users}
          label="Posti Licenziati"
          value={stats ? fmtNumber(stats.seats_sold) : "—"}
          sub="seats · enterprise + sovereign"
        />
        <StatPanel
          testId={TID.vendorKpiMrr}
          icon={Coins}
          label="MRR · ARR"
          value={stats ? fmtEur(stats.mrr_eur) : "—"}
          sub={stats ? `ARR: ${fmtEur(stats.arr_eur)}` : "loading…"}
        />
      </div>

      <SectionPanel
        title="Tenants"
        eyebrow="customer instances · operational metadata only"
        testId={TID.vendorTenantsTable}
        right={
          <span className="pill pill-gold inline-flex items-center gap-1.5">
            <ShieldCheck size={11} /> ZERO-KNOWLEDGE OF PAYLOAD
          </span>
        }
      >
        <div className="overflow-x-auto">
          <table className="lattice-table">
            <thead>
              <tr>
                <th>Cliente</th>
                <th>Dominio</th>
                <th>Industry</th>
                <th>Tier</th>
                <th>Seats</th>
                <th>Nodi</th>
                <th>Health</th>
                <th>Block height</th>
                <th>Heartbeat</th>
                <th>MRR</th>
                <th>Scadenza</th>
              </tr>
            </thead>
            <tbody>
              {tenants.length === 0 && <EmptyRow colSpan={11} text="loading…" />}
              {tenants.map((t) => (
                <tr key={t.tenant_id} data-testid={TID.vendorTenantRow(t.tenant_id)}>
                  <td className="font-mono-data text-[13px] text-white">{t.name}</td>
                  <td className="font-mono-data text-[12px] text-[var(--lattice-text-2)]">{t.domain}</td>
                  <td className="font-mono-data text-[11px] text-[var(--lattice-text-3)]">{t.industry}</td>
                  <td>
                    <span className={`pill ${t.license_tier === "SOVEREIGN" ? "pill-gold" : t.license_tier === "ENTERPRISE" ? "pill-online" : t.license_tier === "TRIAL" ? "pill-degraded" : "pill-slate"}`}>
                      {t.license_tier}
                    </span>
                  </td>
                  <td className="font-mono-data text-[var(--lattice-gold)]">{fmtNumber(t.license_seats)}</td>
                  <td className="font-mono-data text-[12px]">{t.nodes_active}/{t.nodes_total}</td>
                  <td>
                    <span className={`pill ${t.health === "HEALTHY" ? "pill-online" : t.health === "DEGRADED" ? "pill-degraded" : "pill-offline"}`}>
                      <span className={`dot ${t.health === "HEALTHY" ? "dot-online" : t.health === "DEGRADED" ? "dot-degraded" : "dot-offline"}`} />
                      {t.health}
                    </span>
                  </td>
                  <td className="font-mono-data text-[11px] text-[var(--lattice-text-3)]">#{fmtNumber(t.block_height_seen)}</td>
                  <td className="font-mono-data text-[10px] text-[var(--lattice-text-4)]">{fmtRelative(t.last_heartbeat_at, lang)}</td>
                  <td className="font-mono-data text-[13px] text-[var(--lattice-gold)]">{fmtEur(t.mrr_eur)}</td>
                  <td className="font-mono-data text-[11px] text-[var(--lattice-text-3)]">{new Date(t.license_expires_at).toLocaleDateString(lang === "it" ? "it-IT" : "en-GB")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionPanel>
    </div>
  );
}
