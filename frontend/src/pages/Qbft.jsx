import { useEffect, useState } from "react";
import { useLang } from "@/i18n/LangProvider";
import { api, fmtRelative } from "@/lib/api";
import { PageHeader, SectionPanel, EmptyRow } from "@/components/Primitives";
import { TID } from "@/constants/lattice-testids";

function Bar({ pct, gold = false }) {
  const v = Math.max(0, Math.min(100, pct || 0));
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 bg-[#0a1020] border border-[var(--lattice-border)] relative overflow-hidden">
        <div
          style={{
            width: `${v}%`,
            background: gold ? "var(--lattice-gold)" : v > 80 ? "#f59e0b" : "#34d399",
            transition: "width 0.4s ease",
            height: "100%",
          }}
        />
      </div>
      <span className="font-mono-data text-[11px] text-[var(--lattice-text-2)]">{v.toFixed(1)}%</span>
    </div>
  );
}

export default function Qbft() {
  const { t, lang } = useLang();
  const [nodes, setNodes] = useState([]);
  const [alerts, setAlerts] = useState({ alerts: [], quorum_ok: true, validators_online: 0, validators_total: 0, required_quorum: 0 });

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const [n, a] = await Promise.all([
          api.get("/qbft/nodes"),
          api.get("/qbft/alerts"),
        ]);
        if (alive) {
          setNodes(n.data);
          setAlerts(a.data);
        }
      } catch (e) {
        console.error(e);
      }
    };
    load();
    const id = setInterval(load, 5000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="space-y-8">
      <PageHeader eyebrow={t.qbft.eyebrow} title={t.qbft.title} subtitle={t.qbft.subtitle} />

      {(alerts.alerts || []).length > 0 && (
        <div
          data-testid="qbft-alerts-panel"
          className={`surface-elev border ${
            alerts.quorum_ok ? "border-amber-500/40 bg-amber-500/5" : "border-rose-500/40 bg-rose-500/5"
          } relative`}
        >
          <div className="absolute top-0 left-0 right-0 h-px bg-rose-400" />
          <div className="px-5 py-4">
            <div className={`eyebrow flex items-center gap-2 ${alerts.quorum_ok ? "text-amber-300" : "text-rose-300"}`}>
              {alerts.quorum_ok ? "AVVISI · QUORUM OK" : "QUORUM PERSO · BFT NON DISPONIBILE"}
            </div>
            <div className="font-mono-data text-[11px] text-[var(--lattice-text-2)] mt-1">
              {alerts.validators_online}/{alerts.validators_total} validator ONLINE · soglia richiesta {alerts.required_quorum}
            </div>
            <ul className="mt-3 space-y-1">
              {(alerts.alerts || []).map((a, i) => (
                <li
                  key={i}
                  data-testid={`qbft-alert-${a.kind}`}
                  className={`text-[12px] leading-relaxed ${a.severity === "critical" ? "text-rose-300" : "text-amber-300"}`}
                >
                  <span className="font-mono-data text-[10px] uppercase tracking-wider mr-2">{a.severity}</span>
                  {a.detail}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      <SectionPanel
        title={t.qbft.title}
        eyebrow={t.home.panels.qbftSub}
        testId={TID.qbftTable}
        right={
          <div className="flex items-center gap-3">
            <span className="pill pill-online"><span className="dot dot-online" /> {nodes.filter((n) => n.status === "ONLINE").length} {t.common.online}</span>
            <span className="pill pill-degraded"><span className="dot dot-degraded" /> {nodes.filter((n) => n.status === "DEGRADED").length} {t.common.degraded}</span>
          </div>
        }
      >
        <div className="overflow-x-auto">
          <table className="lattice-table">
            <thead>
              <tr>
                <th>{t.qbft.columns.label}</th>
                <th>{t.qbft.columns.node}</th>
                <th>{t.qbft.columns.region}</th>
                <th>{t.qbft.columns.role}</th>
                <th>{t.qbft.columns.status}</th>
                <th>{t.qbft.columns.vp}</th>
                <th>{t.qbft.columns.proposed}</th>
                <th>{t.qbft.columns.cpu}</th>
                <th>{t.qbft.columns.mem}</th>
                <th>{t.qbft.columns.last}</th>
                <th>{t.qbft.columns.version}</th>
              </tr>
            </thead>
            <tbody>
              {nodes.length === 0 && <EmptyRow colSpan={11} text={t.common.loading} />}
              {nodes.map((n) => (
                <tr key={n.node_id}>
                  <td className="font-mono-data text-white">{n.label}</td>
                  <td className="font-mono-data text-[11px] text-[var(--lattice-text-3)]">{n.node_id}</td>
                  <td className="font-mono-data text-[12px]">{n.region}</td>
                  <td>
                    <span className="pill pill-slate">{t.qbft.roles[n.role]}</span>
                  </td>
                  <td>
                    <span className={`pill ${n.status === "ONLINE" ? "pill-online" : n.status === "DEGRADED" ? "pill-degraded" : "pill-offline"}`}>
                      <span className={`dot ${n.status === "ONLINE" ? "dot-online" : n.status === "DEGRADED" ? "dot-degraded" : "dot-offline"}`} />
                      {n.status}
                    </span>
                  </td>
                  <td className="font-mono-data text-[var(--lattice-gold)]">{n.voting_power}</td>
                  <td className="font-mono-data">{n.blocks_proposed}</td>
                  <td><Bar pct={n.cpu_pct} /></td>
                  <td><Bar pct={n.mem_pct} gold /></td>
                  <td className="font-mono-data text-[11px] text-[var(--lattice-text-3)]">{fmtRelative(n.last_seen, lang)}</td>
                  <td className="font-mono-data text-[11px] text-[var(--lattice-text-4)]">{n.version}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionPanel>

      <AlertWebhooksPanel />
    </div>
  );
}

function AlertWebhooksPanel() {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ url: "", label: "", kind: "generic", extra: "", severity_filter: "all" });

  const load = () => {
    api.get("/alerts/webhooks")
      .then((r) => setItems(r.data?.items || []))
      .catch(() => { /* non-platform users get 403 */ });
  };
  useEffect(() => { load(); }, []);

  const add = () => {
    if (!form.url || !form.label) return;
    const payload = { ...form };
    if (form.kind === "telegram" && form.extra) {
      try { payload.extra = JSON.parse(form.extra); } catch {
        payload.extra = { chat_id: form.extra };
      }
    } else {
      delete payload.extra;
    }
    api.post("/alerts/webhooks", payload)
      .then(() => {
        setForm({ url: "", label: "", kind: "generic", extra: "", severity_filter: "all" });
        load();
      })
      .catch(() => { /* surfaced via toast at api layer */ });
  };

  const remove = (url) => {
    if (!window.confirm(`Rimuovere il webhook ${url}?`)) return;
    api.delete("/alerts/webhooks", { params: { url } }).then(load);
  };

  const testFire = (url) => {
    api.post("/alerts/test-fire", { url, message: "Test alert dalla console" })
      .then((r) => window.alert(r.data.ok ? "Webhook OK · 2xx" : "Webhook ha risposto con errore"));
  };

  if (!items) return null;
  return (
    <div data-testid="alert-webhooks-panel" className="surface-elev border hairline relative">
      <div className="absolute top-0 left-0 right-0 h-px gold-line" />
      <header className="px-6 py-5 border-b hairline">
        <div className="eyebrow text-[var(--lattice-gold)]">ALERT WEBHOOKS</div>
        <p className="text-[12px] text-[var(--lattice-text-3)] mt-2 leading-relaxed">
          Quando un validator passa a DEGRADED/OFFLINE per &gt;30s, il backend
          notifica i canali registrati. Supporta Slack incoming-webhook,
          Telegram Bot API, e qualsiasi endpoint che accetta POST JSON.
        </p>
      </header>
      <div className="px-6 py-5 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-6 gap-2">
          <input
            data-testid="webhook-url-input"
            value={form.url}
            onChange={(e) => setForm({ ...form, url: e.target.value })}
            placeholder="https://hooks.slack.com/services/…"
            className="md:col-span-2 bg-transparent border hairline px-2 py-2 font-mono-data text-[12px] text-white"
          />
          <input
            data-testid="webhook-label-input"
            value={form.label}
            onChange={(e) => setForm({ ...form, label: e.target.value })}
            placeholder="label"
            className="bg-transparent border hairline px-2 py-2 font-mono-data text-[12px] text-white"
          />
          <select
            data-testid="webhook-kind-select"
            value={form.kind}
            onChange={(e) => setForm({ ...form, kind: e.target.value })}
            className="bg-transparent border hairline px-2 py-2 font-mono-data text-[12px] text-white"
          >
            <option value="generic">generic</option>
            <option value="slack">slack</option>
            <option value="telegram">telegram</option>
          </select>
          <input
            data-testid="webhook-extra-input"
            value={form.extra}
            onChange={(e) => setForm({ ...form, extra: e.target.value })}
            placeholder={form.kind === "telegram" ? "chat_id" : "(opz.)"}
            className="bg-transparent border hairline px-2 py-2 font-mono-data text-[12px] text-white"
          />
          <button
            data-testid="webhook-add-btn"
            onClick={add}
            className="px-3 py-2 border border-[var(--lattice-gold)] text-[var(--lattice-gold)] font-mono-data text-[11px] tracking-wider uppercase hover:bg-[rgba(212,175,55,0.08)]"
          >
            Aggiungi
          </button>
        </div>
        {items.length === 0 ? (
          <div className="text-[12px] text-[var(--lattice-text-3)]">Nessun webhook configurato.</div>
        ) : (
          <table className="lattice-table">
            <thead>
              <tr>
                <th>Label</th><th>Kind</th><th>URL</th><th>Severity</th><th>Fired</th><th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((w) => (
                <tr key={w.url} data-testid={`webhook-row-${w.label}`}>
                  <td className="font-mono-data">{w.label}</td>
                  <td><span className="pill pill-slate">{w.kind}</span></td>
                  <td className="font-mono-data text-[11px] break-all">{w.url}</td>
                  <td className="font-mono-data text-[11px]">{w.severity_filter}</td>
                  <td className="font-mono-data text-[11px]">{w.fire_count || 0}</td>
                  <td className="flex gap-2">
                    <button
                      data-testid={`webhook-test-${w.label}`}
                      onClick={() => testFire(w.url)}
                      className="font-mono-data text-[10px] uppercase tracking-wider text-sky-300 hover:underline"
                    >test</button>
                    <button
                      data-testid={`webhook-delete-${w.label}`}
                      onClick={() => remove(w.url)}
                      className="font-mono-data text-[10px] uppercase tracking-wider text-rose-300 hover:underline"
                    >elimina</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
