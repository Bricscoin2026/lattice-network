import { useEffect, useState } from "react";
import { useLang } from "@/i18n/LangProvider";
import { api, fmtNumber, fmtRelative, fmtTime } from "@/lib/api";
import { PageHeader, StatPanel, SectionPanel, HashCell, EmptyRow } from "@/components/Primitives";
import { TID } from "@/constants/lattice-testids";
import { Boxes, Shield, IdCard, MailCheck, Activity, Hash } from "lucide-react";

export default function Dashboard() {
  const { t, lang } = useLang();
  const [stats, setStats] = useState(null);
  const [nodes, setNodes] = useState([]);
  const [blocks, setBlocks] = useState([]);
  const [txs, setTxs] = useState([]);
  const [lnsCount, setLnsCount] = useState({ active: 0, revoked: 0 });
  const [certify, setCertify] = useState(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const [s, n, b, x, lns, c] = await Promise.all([
          api.get("/ledger/stats"),
          api.get("/qbft/nodes"),
          api.get("/ledger/blocks", { params: { limit: 8 } }),
          api.get("/transactions", { params: { limit: 8 } }),
          api.get("/lns", { params: { limit: 500 } }),
          api.get("/certify/stats"),
        ]);
        if (!mounted) return;
        setStats(s.data);
        setNodes(n.data);
        setBlocks(b.data);
        setTxs(x.data);
        setCertify(c.data);
        const active = lns.data.filter((r) => r.status === "ACTIVE").length;
        const revoked = lns.data.length - active;
        setLnsCount({ active, revoked });
      } catch (e) {
        console.error(e);
      }
    };
    load();
    const id = setInterval(load, 6000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);

  const onlineNodes = nodes.filter((n) => n.status === "ONLINE").length;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={t.home.eyebrow}
        title={t.home.title}
        subtitle={t.home.subtitle}
        right={
          <div className="hidden md:flex items-center gap-4">
            <div className="text-right">
              <div className="eyebrow">{t.home.chainId}</div>
              <div className="font-mono-data text-[12px] text-white mt-1">lattice-sovereign-it-prod</div>
            </div>
          </div>
        }
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatPanel
          testId={TID.kpiBlockHeight}
          label={t.home.blockHeight}
          icon={Boxes}
          accent
          value={stats ? fmtNumber(stats.block_height) : "—"}
          sub={stats ? `${t.home.qbftRound}: ${fmtNumber(stats.qbft_round)}` : t.common.loading}
        />
        <StatPanel
          testId={TID.kpiTransactions}
          label={t.home.totalTx}
          icon={Hash}
          value={stats ? fmtNumber(stats.total_transactions) : "—"}
          sub={stats ? `${t.home.pendingTx}: ${stats.pending_transactions}` : t.common.loading}
        />
        <StatPanel
          testId={TID.kpiNodes}
          label={t.home.activeNodes}
          icon={Shield}
          value={`${onlineNodes}/${nodes.length || "—"}`}
          sub={stats ? `${t.home.finality}: ${stats.finality_ms} ms` : t.common.loading}
        />
        <StatPanel
          testId={TID.kpiCertify}
          label={t.home.certifyTotal}
          icon={MailCheck}
          value={certify ? fmtNumber(certify.total_notarized) : "—"}
          sub={certify ? `24h · ${fmtNumber(certify.last_24h)}  ·  7g · ${fmtNumber(certify.last_7d)}` : t.common.loading}
        />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <SectionPanel
          testId={TID.panelLedger}
          eyebrow={t.home.panels.ledgerSub}
          title={t.home.panels.ledger}
          right={
            <div className="pill pill-slate">
              <span className="dot dot-online" />
              <span>{t.home.lastBlock}</span>
            </div>
          }
        >
          <div className="px-5 py-4 border-b hairline">
            <div className="flex items-baseline gap-3">
              <div className="font-display text-3xl text-white">#{stats ? fmtNumber(stats.block_height) : "—"}</div>
              <div className="font-mono-data text-[11px] text-[var(--lattice-text-3)]">
                {stats ? fmtRelative(stats.last_block_at, lang) : ""}
              </div>
            </div>
            <div className="mt-2">
              <HashCell value={stats?.last_block_hash} color="gold" />
            </div>
          </div>
          <div className="max-h-[260px] overflow-auto">
            <table className="lattice-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>{t.ledger.columns.proposer}</th>
                  <th>{t.ledger.columns.txs}</th>
                  <th>{t.ledger.columns.hash}</th>
                </tr>
              </thead>
              <tbody>
                {blocks.length === 0 && <EmptyRow colSpan={4} text={t.common.loading} />}
                {blocks.map((b) => (
                  <tr key={b.index}>
                    <td className="font-mono-data text-[var(--lattice-gold)]">{b.index}</td>
                    <td className="font-mono-data text-[12px]">{b.proposer}</td>
                    <td className="font-mono-data text-[12px]">{b.transactions_count}</td>
                    <td><HashCell value={b.block_hash} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionPanel>

        <SectionPanel
          testId={TID.panelQbft}
          eyebrow={t.home.panels.qbftSub}
          title={t.home.panels.qbft}
        >
          <div className="divide-y divide-[var(--lattice-border)]">
            {nodes.length === 0 && (
              <div className="px-5 py-6 text-[var(--lattice-text-4)] font-mono-data text-[11px] tracking-wider uppercase">
                {t.common.loading}
              </div>
            )}
            {nodes.slice(0, 8).map((n) => (
              <div key={n.node_id} className="px-5 py-3 flex items-center justify-between hover:bg-[rgba(212,175,55,0.04)]">
                <div className="flex items-center gap-3 min-w-0">
                  <span className={`dot ${n.status === "ONLINE" ? "dot-online" : n.status === "DEGRADED" ? "dot-degraded" : "dot-offline"}`} />
                  <div className="min-w-0">
                    <div className="font-mono-data text-[13px] text-white">{n.label}</div>
                    <div className="font-mono-data text-[11px] text-[var(--lattice-text-3)] truncate">{n.region} · {t.qbft.roles[n.role]}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-mono-data text-[11px] text-[var(--lattice-text-2)]">CPU {n.cpu_pct}%</div>
                  <div className="font-mono-data text-[10px] text-[var(--lattice-text-4)]">MEM {n.mem_pct}%</div>
                </div>
              </div>
            ))}
          </div>
        </SectionPanel>

        <div className="grid grid-cols-1 gap-4">
          <SectionPanel
            testId={TID.panelLns}
            eyebrow={t.home.panels.lnsSub}
            title={t.home.panels.lns}
          >
            <div className="grid grid-cols-2 divide-x divide-[var(--lattice-border)]">
              <div className="px-5 py-5">
                <div className="eyebrow">{t.common.active}</div>
                <div className="mt-2 font-display text-3xl text-white">{fmtNumber(lnsCount.active)}</div>
              </div>
              <div className="px-5 py-5">
                <div className="eyebrow">{t.common.revoked}</div>
                <div className="mt-2 font-display text-3xl text-[var(--lattice-gold)]">{fmtNumber(lnsCount.revoked)}</div>
              </div>
            </div>
          </SectionPanel>

          <SectionPanel
            testId={TID.panelCertify}
            eyebrow={t.home.panels.certifySub}
            title={t.home.panels.certify}
          >
            <div className="px-5 py-5">
              <div className="font-display text-4xl text-white">{certify ? fmtNumber(certify.total_notarized) : "—"}</div>
              <div className="mt-1 eyebrow">{t.home.certifyTotal}</div>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <div>
                  <div className="eyebrow text-[10px]">{t.certify.stats.last24}</div>
                  <div className="font-mono-data text-white mt-1">{certify ? fmtNumber(certify.last_24h) : "—"}</div>
                </div>
                <div>
                  <div className="eyebrow text-[10px]">{t.certify.stats.last7}</div>
                  <div className="font-mono-data text-white mt-1">{certify ? fmtNumber(certify.last_7d) : "—"}</div>
                </div>
              </div>
            </div>
          </SectionPanel>
        </div>
      </div>

      <SectionPanel
        testId={TID.panelLogs}
        eyebrow={t.ledger.subtitle}
        title={t.ledger.transactions}
      >
        <div className="max-h-[360px] overflow-auto">
          <table className="lattice-table">
            <thead>
              <tr>
                <th>{t.ledger.columns.tx}</th>
                <th>{t.ledger.columns.kind}</th>
                <th>{t.ledger.columns.summary}</th>
                <th>{t.ledger.columns.time}</th>
                <th>#</th>
              </tr>
            </thead>
            <tbody>
              {txs.length === 0 && <EmptyRow colSpan={5} text={t.common.loading} />}
              {txs.map((x) => (
                <tr key={x.tx_id}>
                  <td><HashCell value={x.tx_id} color="gold" /></td>
                  <td>
                    <span className="pill pill-slate">{t.ledger.kinds[x.kind]}</span>
                  </td>
                  <td className="font-mono-data text-[12px] text-[var(--lattice-text-2)]">{x.summary}</td>
                  <td className="font-mono-data text-[11px] text-[var(--lattice-text-3)]">{fmtTime(x.timestamp, lang)}</td>
                  <td className="font-mono-data text-[var(--lattice-gold)]">{x.block_index}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionPanel>
    </div>
  );
}
