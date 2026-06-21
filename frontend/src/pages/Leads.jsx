import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader, SectionPanel } from "@/components/Primitives";
import { Mail, Phone, Building2, RefreshCw, Search, CheckCheck, Hash, Boxes } from "lucide-react";
import { toast } from "sonner";

const STATUSES = [
  { v: "new", label: "Nuovo", color: "pill-gold" },
  { v: "contacted", label: "Contattato", color: "pill-online" },
  { v: "qualified", label: "Qualificato", color: "pill-online" },
  { v: "converted", label: "Convertito", color: "pill-gold" },
  { v: "lost", label: "Perso", color: "pill-offline" },
];

export default function Leads() {
  const [leads, setLeads] = useState([]);
  const [filter, setFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const load = async () => {
    try {
      const r = await api.get("/leads", { params: statusFilter ? { status: statusFilter } : {} });
      setLeads(r.data);
    } catch (e) { toast.error(e?.response?.data?.detail || "Errore caricamento"); }
  };

  useEffect(() => { load(); }, [statusFilter]); // eslint-disable-line

  const changeStatus = async (lead_id, status) => {
    try {
      await api.patch(`/leads/${lead_id}`, { status });
      toast.success(`Status → ${status}`);
      await load();
    } catch (e) { toast.error("Errore aggiornamento"); }
  };

  const markOneRead = async (lead) => {
    if (lead.read_at) return;
    try {
      await api.post(`/leads/${lead.lead_id}/read`);
      setLeads((prev) => prev.map((l) => l.lead_id === lead.lead_id ? { ...l, read_at: new Date().toISOString() } : l));
    } catch (_e) { /* silent */ }
  };

  const markAllRead = async () => {
    try {
      const r = await api.post("/leads/read-all");
      toast.success(`${r.data?.marked || 0} lead marcati come letti`);
      await load();
    } catch (_e) { toast.error("Errore"); }
  };

  const visible = leads.filter((l) =>
    !filter ||
    l.company_name?.toLowerCase().includes(filter.toLowerCase()) ||
    l.contact_name?.toLowerCase().includes(filter.toLowerCase()) ||
    l.email?.toLowerCase().includes(filter.toLowerCase())
  );

  const unreadCount = leads.filter((l) => !l.read_at).length;
  const stats = STATUSES.map((s) => ({ ...s, count: leads.filter((l) => l.status === s.v).length }));

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="SALES PIPELINE · ON-CHAIN"
        title="Lead Aziendali"
        subtitle="Ogni richiesta demo viene tracciata sulla rete Lattice in modo verificabile, indipendente da provider esterni. Niente Mailchimp, niente HubSpot."
        right={
          <div className="flex items-center gap-2">
            {unreadCount > 0 && (
              <button
                onClick={markAllRead}
                data-testid="leads-mark-all-read"
                className="btn-ghost inline-flex items-center gap-2"
                style={{ padding: "6px 12px", fontSize: 11 }}
                title={`Segna tutti i ${unreadCount} lead non letti come letti`}
              >
                <CheckCheck size={12} /> Segna tutti come letti ({unreadCount})
              </button>
            )}
            <button onClick={load} data-testid="leads-refresh" className="btn-ghost inline-flex items-center gap-2" style={{ padding: "6px 12px", fontSize: 11 }}>
              <RefreshCw size={12} /> Ricarica
            </button>
          </div>
        }
      />

      {/* Status summary */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {stats.map((s) => (
          <button
            key={s.v}
            data-testid={`leads-filter-${s.v}`}
            onClick={() => setStatusFilter(statusFilter === s.v ? "" : s.v)}
            className={`surface px-4 py-4 text-left ${statusFilter === s.v ? "border-[var(--lattice-gold)]" : ""}`}
            style={statusFilter === s.v ? { borderColor: "var(--lattice-gold)", borderWidth: 1 } : undefined}
          >
            <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] tracking-wider uppercase">{s.label}</div>
            <div className="font-display text-3xl text-white mt-1">{s.count}</div>
          </button>
        ))}
      </div>

      <SectionPanel
        title={`${visible.length} lead`}
        eyebrow="REGISTRY"
        testId="leads-list-panel"
      >
        <div className="px-5 py-3 border-b hairline flex items-center gap-2">
          <Search size={13} className="text-[var(--lattice-gold)]" />
          <input
            data-testid="leads-search"
            className="bg-transparent border-0 outline-none flex-1 font-mono-data text-[12px] text-white"
            placeholder="Cerca azienda, nome, email…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
        <div className="max-h-[640px] overflow-auto" data-testid="leads-rows">
          {visible.length === 0 && (
            <div className="px-5 py-16 text-center font-mono-data text-[11px] text-[var(--lattice-text-4)] uppercase tracking-wider">
              Nessun lead {statusFilter ? `con stato ${statusFilter}` : ""} ancora
            </div>
          )}
          {visible.map((l) => {
            const isUnread = !l.read_at;
            return (
              <div
                key={l.lead_id}
                data-testid={`lead-row-${l.lead_id}`}
                onClick={() => markOneRead(l)}
                className={`px-5 py-4 border-b hairline grid grid-cols-12 gap-3 items-start cursor-pointer transition-colors ${
                  isUnread ? "bg-[rgba(212,175,55,0.05)] hover:bg-[rgba(212,175,55,0.08)]" : "hover:bg-[rgba(255,255,255,0.02)]"
                }`}
              >
                <div className="col-span-3 min-w-0">
                  <div className="text-[14px] text-white truncate flex items-center gap-2">
                    {isUnread && (
                      <span
                        className="inline-block w-2 h-2 rounded-full bg-[var(--lattice-gold)] shrink-0"
                        data-testid={`lead-unread-dot-${l.lead_id}`}
                        title="Non letto"
                      />
                    )}
                    <Building2 size={12} className="text-[var(--lattice-gold)]" />
                    <span className={isUnread ? "font-bold" : ""}>{l.company_name}</span>
                  </div>
                  <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] mt-1">{l.industry} · {l.employees_range}</div>
                  {l.tx_id && (
                    <div className="font-mono-data text-[9px] text-emerald-400/80 mt-1 flex items-center gap-1" title={`On-chain tx ${l.tx_id} · block #${l.block_index}`}>
                      <Boxes size={9} /> #{l.block_index}
                      <Hash size={9} className="ml-1" /> {l.tx_id.slice(0, 14)}…
                    </div>
                  )}
                </div>
                <div className="col-span-3 min-w-0">
                  <div className="text-[13px] text-white truncate">{l.contact_name}</div>
                  <a onClick={(e) => e.stopPropagation()} href={`mailto:${l.email}`} className="font-mono-data text-[11px] text-[var(--lattice-gold)] hover:underline truncate flex items-center gap-1">
                    <Mail size={10} /> {l.email}
                  </a>
                  {l.phone && (
                    <a onClick={(e) => e.stopPropagation()} href={`tel:${l.phone}`} className="font-mono-data text-[10px] text-[var(--lattice-text-3)] flex items-center gap-1">
                      <Phone size={9} /> {l.phone}
                    </a>
                  )}
                </div>
                <div className="col-span-3 min-w-0 font-mono-data text-[10px] text-[var(--lattice-text-2)] whitespace-pre-wrap">
                  {l.notes || <span className="text-[var(--lattice-text-4)]">— nessuna nota</span>}
                </div>
                <div className="col-span-2" onClick={(e) => e.stopPropagation()}>
                  <select
                    data-testid={`lead-status-${l.lead_id}`}
                    value={l.status}
                    onChange={(e) => changeStatus(l.lead_id, e.target.value)}
                    className="bg-transparent border border-[var(--lattice-border-strong)] px-2 py-1 font-mono-data text-[10px] text-white w-full"
                  >
                    {STATUSES.map((s) => (
                      <option key={s.v} value={s.v} style={{ background: "#0a1020" }}>{s.label}</option>
                    ))}
                  </select>
                </div>
                <div className="col-span-1 font-mono-data text-[10px] text-[var(--lattice-text-3)] text-right">
                  {l.received_at?.slice(0,10)}
                </div>
              </div>
            );
          })}
        </div>
      </SectionPanel>
    </div>
  );
}
