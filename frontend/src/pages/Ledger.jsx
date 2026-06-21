import { useEffect, useState } from "react";
import { useLang } from "@/i18n/LangProvider";
import { api, API, fmtNumber, fmtTime } from "@/lib/api";
import { PageHeader, SectionPanel, HashCell, EmptyRow } from "@/components/Primitives";
import { TID } from "@/constants/lattice-testids";
import { Download, FileJson, ShieldCheck, ShieldAlert, Shield, X } from "lucide-react";
import { toast } from "sonner";

function PqcBanner() {
  const [info, setInfo] = useState(null);
  useEffect(() => { api.get("/pqc/info").then((r) => setInfo(r.data)).catch(() => {}); }, []);
  if (!info) return null;
  return (
    <div className="surface px-4 py-3 flex items-center gap-3 flex-wrap" data-testid="pqc-banner">
      <Shield size={14} className="text-[var(--lattice-gold)]" />
      <span className="font-mono-data text-[11px] text-white">{info.algorithm}</span>
      <span className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">· {info.standard}</span>
      <span className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">·</span>
      <span className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">pk {info.public_key_size_bytes}B · sig {info.signature_size_bytes}B</span>
      <span className="ml-auto font-mono-data text-[10px] text-[var(--lattice-gold)]">{info.implementation} · LIVE</span>
    </div>
  );
}

function VerifyDialog({ txId, onClose }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(true);
  useEffect(() => {
    if (!txId) return;
    setBusy(true);
    api.get(`/ledger/verify/${txId}`)
      .then((r) => setData(r.data))
      .catch((e) => setData({ ok: false, detail: e?.response?.data?.detail || "Errore verifica" }))
      .finally(() => setBusy(false));
  }, [txId]);
  if (!txId) return null;
  const ok = data?.ok;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-6" data-testid="verify-dialog">
      <div className="w-full max-w-2xl surface-elev relative">
        <div className="absolute top-0 left-0 right-0 h-px gold-line" />
        <header className="flex items-start justify-between px-6 py-5 border-b hairline">
          <div>
            <div className="eyebrow">PQC · CRYPTOGRAPHIC VERIFICATION</div>
            <h3 className="font-display text-2xl text-white mt-1">Verifica firma on-chain</h3>
          </div>
          <button onClick={onClose} className="text-[var(--lattice-text-3)] hover:text-white"><X size={18} /></button>
        </header>
        <div className="px-6 py-5 space-y-4">
          {busy && <div className="font-mono-data text-[11px] text-[var(--lattice-text-3)] uppercase tracking-wider">Verifica in corso…</div>}
          {data && (
            <>
              <div className="flex items-center gap-3">
                {ok ? <ShieldCheck size={28} className="text-[var(--lattice-gold)]" /> : <ShieldAlert size={28} className="text-red-400" />}
                <div>
                  <div className="font-display text-xl text-white">{ok ? "FIRMA VALIDA" : "VERIFICA FALLITA"}</div>
                  <div className="font-mono-data text-[11px] text-[var(--lattice-text-3)]">{data.algorithm} · {data.signed_with}</div>
                </div>
              </div>
              <div className="border hairline-strong p-4 surface-2 space-y-2 font-mono-data text-[11px]">
                <div><span className="text-[var(--lattice-text-3)]">TX:</span> <span className="text-white break-all">{data.tx_id}</span></div>
                {data.signer_entity && <div><span className="text-[var(--lattice-text-3)]">Firmatario:</span> <span className="text-[var(--lattice-gold)] break-all">{data.signer_entity}</span></div>}
                {data.public_key_fingerprint && <div><span className="text-[var(--lattice-text-3)]">PK fingerprint:</span> <span className="text-white">{data.public_key_fingerprint}</span></div>}
                <div><span className="text-[var(--lattice-text-3)]">Dimensione PK:</span> <span className="text-white">{data.public_key_size_bytes} byte</span></div>
                <div><span className="text-[var(--lattice-text-3)]">Dimensione firma:</span> <span className="text-white">{data.signature_size_bytes} byte</span></div>
              </div>
              <div className="border hairline px-4 py-3 surface">
                <div className="eyebrow mb-1">Messaggio canonico (esadecimale)</div>
                <div className="font-mono-data text-[10px] text-[var(--lattice-text-2)] break-all max-h-32 overflow-auto">{data.message_hex}</div>
              </div>
              <div className={`text-[12px] leading-relaxed ${ok ? "text-[var(--lattice-gold)]" : "text-red-300"}`}>{data.detail}</div>
            </>
          )}
        </div>
        <footer className="flex items-center justify-end gap-3 px-6 py-4 border-t hairline">
          <button className="btn-ghost" onClick={onClose}>Chiudi</button>
        </footer>
      </div>
    </div>
  );
}

export default function Ledger() {
  const { t, lang } = useLang();
  const [blocks, setBlocks] = useState([]);
  const [txs, setTxs] = useState([]);
  const [filter, setFilter] = useState("ALL");
  const [verifyTx, setVerifyTx] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const params = filter === "ALL" ? { limit: 60 } : { limit: 60, kind: filter };
        const [b, x] = await Promise.all([
          api.get("/ledger/blocks", { params: { limit: 30 } }),
          api.get("/transactions", { params }),
        ]);
        if (!alive) return;
        setBlocks(b.data);
        setTxs(x.data);
      } catch (e) {
        console.error(e);
      }
    };
    load();
    const id = setInterval(load, 7000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [filter]);

  const filterBtn = (key, tid, label) => (
    <button
      data-testid={tid}
      onClick={() => setFilter(key)}
      className={`font-mono-data text-[10px] uppercase tracking-[0.2em] px-3 py-1.5 border transition-colors ${
        filter === key
          ? "bg-[var(--lattice-gold)] text-[var(--lattice-bg)] border-[var(--lattice-gold)]"
          : "bg-transparent text-[var(--lattice-text-3)] border-[var(--lattice-border-strong)] hover:text-white hover:border-[var(--lattice-gold)]"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="space-y-8">
      <PageHeader eyebrow={t.ledger.eyebrow} title={t.ledger.title} subtitle={t.ledger.subtitle} />
      <PqcBanner />

      <SectionPanel title={t.ledger.blocks} eyebrow={t.home.panels.ledgerSub} testId={TID.ledgerBlocksTable}>
        <div className="overflow-x-auto">
          <table className="lattice-table">
            <thead>
              <tr>
                <th>{t.ledger.columns.index}</th>
                <th>{t.ledger.columns.time}</th>
                <th>{t.ledger.columns.txs}</th>
                <th>Weight</th>
                <th>Events</th>
                <th>{t.ledger.columns.proposer}</th>
                <th>{t.ledger.columns.hash}</th>
                <th>Extrinsics Root</th>
                <th>State Root</th>
                <th>{t.ledger.columns.prev}</th>
              </tr>
            </thead>
            <tbody>
              {blocks.length === 0 && <EmptyRow colSpan={10} text={t.common.loading} />}
              {blocks.map((b) => (
                <tr key={b.index}>
                  <td className="font-mono-data text-[var(--lattice-gold)]">{fmtNumber(b.index)}</td>
                  <td className="font-mono-data text-[11px] text-[var(--lattice-text-3)]">{fmtTime(b.timestamp, lang)}</td>
                  <td className="font-mono-data">{b.transactions_count}</td>
                  <td className="font-mono-data text-[11px] text-[var(--lattice-text-2)]">{fmtNumber(b.weight_used || 0)}</td>
                  <td className="font-mono-data text-[11px] text-[var(--lattice-text-2)]">{b.events_count || 0}</td>
                  <td className="font-mono-data text-[12px]">{b.proposer}</td>
                  <td><HashCell value={b.block_hash} color="gold" /></td>
                  <td><HashCell value={b.extrinsics_root} /></td>
                  <td><HashCell value={b.state_root} /></td>
                  <td><HashCell value={b.previous_hash} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionPanel>

      <SectionPanel
        title={t.ledger.transactions}
        eyebrow={t.ledger.subtitle}
        testId={TID.txTable}
        right={
          <div className="flex items-center gap-2 flex-wrap">
            {filterBtn("ALL", TID.txFilterAll, t.common.all)}
            {filterBtn("NotarySeal", TID.txFilterNotary, t.ledger.kinds.NotarySeal)}
            {filterBtn("IdentityRegister", TID.txFilterRegister, t.ledger.kinds.IdentityRegister)}
            {filterBtn("IdentityRevoke", TID.txFilterRevoke, t.ledger.kinds.IdentityRevoke)}
            <span className="w-px h-5 bg-[var(--lattice-border-strong)] mx-1" />
            <a
              data-testid={TID.txExportCsv}
              href={`${API}/transactions/export?fmt=csv${filter !== "ALL" ? `&kind=${filter}` : ""}&limit=2000`}
              className="font-mono-data text-[10px] uppercase tracking-[0.2em] px-3 py-1.5 border bg-transparent text-[var(--lattice-gold)] border-[var(--lattice-gold)]/50 hover:bg-[var(--lattice-gold)]/10 transition-colors inline-flex items-center gap-1.5"
            >
              <Download size={11} /> CSV
            </a>
            <a
              data-testid={TID.txExportJson}
              href={`${API}/transactions/export?fmt=json${filter !== "ALL" ? `&kind=${filter}` : ""}&limit=2000`}
              className="font-mono-data text-[10px] uppercase tracking-[0.2em] px-3 py-1.5 border bg-transparent text-[var(--lattice-gold)] border-[var(--lattice-gold)]/50 hover:bg-[var(--lattice-gold)]/10 transition-colors inline-flex items-center gap-1.5"
            >
              <FileJson size={11} /> JSON
            </a>
          </div>
        }
      >
        <div className="overflow-x-auto">
          <table className="lattice-table">
            <thead>
              <tr>
                <th>{t.ledger.columns.tx}</th>
                <th>{t.ledger.columns.kind}</th>
                <th>{t.ledger.columns.summary}</th>
                <th>{t.ledger.columns.signature}</th>
                <th>{t.ledger.columns.time}</th>
                <th>{t.ledger.columns.index}</th>
                <th>Verifica</th>
              </tr>
            </thead>
            <tbody>
              {txs.length === 0 && <EmptyRow colSpan={7} text={t.common.empty} />}
              {txs.map((x) => (
                <tr key={x.tx_id}>
                  <td><HashCell value={x.tx_id} color="gold" /></td>
                  <td>
                    <span
                      className={`pill ${
                        x.kind === "IdentityRevoke"
                          ? "pill-offline"
                          : x.kind === "IdentityRegister"
                          ? "pill-online"
                          : "pill-gold"
                      }`}
                    >
                      {t.ledger.kinds[x.kind]}
                    </span>
                  </td>
                  <td className="font-mono-data text-[12px] text-[var(--lattice-text-2)]">{x.summary}</td>
                  <td><HashCell value={x.signature} /></td>
                  <td className="font-mono-data text-[11px] text-[var(--lattice-text-3)]">{fmtTime(x.timestamp, lang)}</td>
                  <td className="font-mono-data text-[var(--lattice-gold)]">{x.block_index}</td>
                  <td>
                    <button
                      data-testid={`tx-verify-${x.tx_id}`}
                      onClick={() => setVerifyTx(x.tx_id)}
                      className="font-mono-data text-[10px] uppercase tracking-[0.15em] px-2 py-1 border border-[var(--lattice-gold)]/40 text-[var(--lattice-gold)] hover:bg-[var(--lattice-gold)]/10 inline-flex items-center gap-1"
                    >
                      <ShieldCheck size={11} /> verify
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionPanel>
      <VerifyDialog txId={verifyTx} onClose={() => setVerifyTx(null)} />
    </div>
  );
}
