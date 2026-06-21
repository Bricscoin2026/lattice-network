import { useEffect, useState } from "react";
import { useParams, useNavigate, Link, useSearchParams } from "react-router-dom";
import { api, shortHash, fmtNumber, fmtTime, fmtRelative } from "@/lib/api";
import {
  Search, Hash, Box, ShieldCheck, ShieldAlert, ArrowLeft, ArrowRight,
  ExternalLink, AlertTriangle, Loader2, FileSignature, Network, Inbox,
  MessageSquare, CheckCircle2, Copy,
} from "lucide-react";

function ExplorerHeader() {
  return (
    <header className="border-b hairline">
      <div className="max-w-6xl mx-auto px-6 py-5 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-4" data-testid="explorer-home-link">
          <img src="/lattice-logo.jpeg" alt="Lattice Network" style={{ width: 56, height: 56, borderRadius: 8 }} className="border hairline" />
          <div>
            <div className="font-display text-2xl leading-tight">Lattice Explorer</div>
            <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] tracking-[0.18em] uppercase mt-0.5">
              Lattice Network · Verifica pubblica on-chain
            </div>
          </div>
        </Link>
        <Link
          to="/"
          className="font-mono-data text-[11px] uppercase tracking-[0.18em] text-[var(--lattice-text-3)] hover:text-white flex items-center gap-2"
          data-testid="explorer-back-home"
        >
          <ArrowLeft size={12} /> home
        </Link>
      </div>
    </header>
  );
}

function CopyButton({ value, tid }) {
  const [copied, setCopied] = useState(false);
  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (e) { /* ignore */ }
  };
  return (
    <button
      onClick={onCopy}
      data-testid={tid}
      className="inline-flex items-center gap-1 px-1.5 py-0.5 border hairline font-mono-data text-[9px] uppercase tracking-[0.15em] text-[var(--lattice-text-3)] hover:text-[var(--lattice-gold)] hover:border-[var(--lattice-gold)] transition-colors"
    >
      {copied ? <CheckCircle2 size={9} /> : <Copy size={9} />} {copied ? "ok" : "copy"}
    </button>
  );
}

function SearchBar({ initial = "", onSubmit, busy }) {
  const [q, setQ] = useState(initial);
  return (
    <form
      onSubmit={(e) => { e.preventDefault(); if (q.trim()) onSubmit(q.trim()); }}
      className="surface-elev border hairline relative"
      data-testid="explorer-search-form"
    >
      <div className="absolute top-0 left-0 right-0 h-px gold-line opacity-60" />
      <div className="px-4 py-4 flex items-center gap-3">
        <Search size={18} className="text-[var(--lattice-gold)] shrink-0" />
        <input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Cerca tx-… · hash documento · numero blocco · LNS (es. admin.acme.lns) · VAL-01"
          data-testid="explorer-search-input"
          className="flex-1 bg-transparent outline-none font-mono-data text-[13px] text-white placeholder-[var(--lattice-text-3)]"
        />
        <button
          type="submit"
          disabled={busy || !q.trim()}
          data-testid="explorer-search-submit"
          className="px-4 py-2 border border-[var(--lattice-gold)] text-[var(--lattice-gold)] font-mono-data text-[10px] tracking-[0.18em] uppercase hover:bg-[rgba(212,175,55,0.08)] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {busy ? <Loader2 className="animate-spin" size={12} /> : "Cerca →"}
        </button>
      </div>
    </form>
  );
}

function Stat({ label, value, tid, icon: Icon }) {
  return (
    <div data-testid={tid} className="border hairline px-5 py-5 surface-elev relative">
      <div className="absolute top-0 left-0 right-0 h-px gold-line opacity-40" />
      <div className="eyebrow text-[10px] mb-2 flex items-center gap-1.5">
        {Icon && <Icon size={11} />} {label}
      </div>
      <div className="font-display text-3xl text-white leading-none">{value}</div>
    </div>
  );
}

function ExplorerHome({ onSearch }) {
  const [stats, setStats] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.get("/explorer/stats")
      .then((r) => setStats(r.data))
      .catch((e) => setErr(e?.message || "errore"));
  }, []);

  return (
    <main className="max-w-6xl mx-auto px-6 py-10 space-y-8" data-testid="explorer-home">
      <section>
        <div className="eyebrow flex items-center gap-2 text-[var(--lattice-gold)]">
          <ShieldCheck size={11} /> EXPLORER PUBBLICO · NO LOGIN
        </div>
        <h1 className="font-display text-4xl sm:text-5xl mt-2">Verifica indipendente on-chain</h1>
        <p className="text-[14px] text-[var(--lattice-text-2)] mt-4 leading-relaxed max-w-3xl">
          Inserisci un <strong className="text-white">tx_id</strong>, un{" "}
          <strong className="text-white">hash di documento</strong>, un{" "}
          <strong className="text-white">numero di blocco</strong> o un{" "}
          <strong className="text-white">nome LNS</strong> per verificare matematicamente la firma
          ML-DSA-65 di una transazione. Nessun contenuto di mail o messaggi viene mai esposto:
          solo hash e firme post-quantistiche.
        </p>
      </section>

      <SearchBar onSubmit={onSearch} />

      {err && (
        <div className="border border-rose-500/40 bg-rose-500/5 px-4 py-3 font-mono-data text-[11px] text-rose-300" data-testid="explorer-stats-error">
          Errore caricamento stats: {err}
        </div>
      )}

      {stats && (
        <>
          <section className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <Stat label="BLOCK HEIGHT"     value={fmtNumber(stats.block_height)}      tid="explorer-stat-blocks"   icon={Box} />
            <Stat label="TRANSAZIONI"      value={fmtNumber(stats.total_transactions)} tid="explorer-stat-tx"      icon={Hash} />
            <Stat label="IDENTITÀ LNS"      value={fmtNumber(stats.total_lns)}          tid="explorer-stat-lns"     icon={Network} />
            <Stat label="MAIL NOTARIZZATE" value={fmtNumber(stats.total_mails)}        tid="explorer-stat-mails"   icon={Inbox} />
            <Stat label="MESSAGGI ANCHOR"   value={fmtNumber(stats.total_pulses)}       tid="explorer-stat-pulses"  icon={MessageSquare} />
          </section>

          <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <RecentBlocks blocks={stats.recent_blocks} />
            <RecentTxs txs={stats.recent_transactions} />
          </section>
        </>
      )}

      {!stats && !err && (
        <div className="font-mono-data text-[12px] text-[var(--lattice-text-3)] flex items-center gap-2">
          <Loader2 className="animate-spin" size={12} /> caricamento stats…
        </div>
      )}
    </main>
  );
}

function RecentBlocks({ blocks }) {
  return (
    <div className="surface-elev border hairline relative" data-testid="explorer-recent-blocks">
      <div className="absolute top-0 left-0 right-0 h-px gold-line" />
      <header className="px-5 py-4 border-b hairline flex items-center justify-between">
        <div className="eyebrow flex items-center gap-2 text-[var(--lattice-gold)]"><Box size={11} /> ULTIMI BLOCCHI</div>
        <span className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">{blocks?.length || 0}</span>
      </header>
      <div className="overflow-x-auto">
        <table className="lattice-table">
          <thead>
            <tr><th>#</th><th>HASH</th><th>TX</th><th>QUANDO</th></tr>
          </thead>
          <tbody>
            {(blocks || []).map((b) => (
              <tr key={b.index} data-testid={`explorer-block-row-${b.index}`}>
                <td className="font-mono-data text-[var(--lattice-gold)]">
                  <Link to={`/explorer/block/${b.index}`} className="hover:underline">{b.index}</Link>
                </td>
                <td className="font-mono-data text-[10px] text-[var(--lattice-text-2)]">{shortHash(b.block_hash, 10, 6)}</td>
                <td className="font-mono-data text-[11px]">{b.transactions_count}</td>
                <td className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">{fmtRelative(b.timestamp)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RecentTxs({ txs }) {
  return (
    <div className="surface-elev border hairline relative" data-testid="explorer-recent-txs">
      <div className="absolute top-0 left-0 right-0 h-px gold-line" />
      <header className="px-5 py-4 border-b hairline flex items-center justify-between">
        <div className="eyebrow flex items-center gap-2 text-[var(--lattice-gold)]"><Hash size={11} /> ULTIME TRANSAZIONI</div>
        <span className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">{txs?.length || 0}</span>
      </header>
      <div className="overflow-x-auto">
        <table className="lattice-table">
          <thead>
            <tr><th>#BLK</th><th>TX</th><th>KIND</th><th>FIRMATARIO</th></tr>
          </thead>
          <tbody>
            {(txs || []).map((t) => (
              <tr key={t.tx_id} data-testid={`explorer-tx-row-${t.tx_id}`}>
                <td className="font-mono-data text-[var(--lattice-gold)]">
                  <Link to={`/explorer/block/${t.block_index}`} className="hover:underline">{t.block_index}</Link>
                </td>
                <td className="font-mono-data text-[10px] text-[var(--lattice-text-2)]">
                  <Link to={`/explorer/tx/${t.tx_id}`} className="hover:underline">{shortHash(t.tx_id, 10, 6)}</Link>
                </td>
                <td><span className="pill pill-slate">{t.kind}</span></td>
                <td className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">{t.signer_entity || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SearchResults() {
  const [params] = useSearchParams();
  const q = params.get("q") || "";
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!q) return;
    setLoading(true);
    setErr("");
    setData(null);
    api.get("/explorer/search", { params: { q } })
      .then((r) => {
        setData(r.data);
        // Auto-redirect to dedicated page
        const t = r.data.type;
        if (t === "transaction") navigate(`/explorer/tx/${r.data.result.tx_id}`, { replace: true });
        else if (t === "block") navigate(`/explorer/block/${r.data.result.index}`, { replace: true });
        else if (t === "lns") navigate(`/explorer/lns/${r.data.result.lns_name}`, { replace: true });
        else if (t === "mail" && r.data.result.tx_id) navigate(`/explorer/tx/${r.data.result.tx_id}`, { replace: true });
      })
      .catch((e) => setErr(e?.response?.data?.detail || "errore"))
      .finally(() => setLoading(false));
  }, [q, navigate]);

  return (
    <main className="max-w-6xl mx-auto px-6 py-10 space-y-6" data-testid="explorer-search-results">
      <SearchBar initial={q} onSubmit={(nq) => navigate(`/explorer/search?q=${encodeURIComponent(nq)}`)} busy={loading} />
      {loading && (
        <div className="font-mono-data text-[12px] text-[var(--lattice-text-3)] flex items-center gap-2">
          <Loader2 className="animate-spin" size={12} /> ricerca di &quot;{q}&quot;…
        </div>
      )}
      {err && (
        <div className="surface-elev border border-rose-500/40 bg-rose-500/5 px-5 py-4" data-testid="explorer-no-match">
          <div className="eyebrow text-rose-300 mb-1 flex items-center gap-2"><AlertTriangle size={12} /> NESSUNA CORRISPONDENZA</div>
          <p className="text-[13px] text-[var(--lattice-text-2)]">
            La query <code className="font-mono-data text-[var(--lattice-gold)]">{q}</code> non corrisponde
            a nessuna transazione, blocco, hash o identità LNS sulla rete.
          </p>
          <ul className="mt-3 text-[12px] text-[var(--lattice-text-3)] list-disc pl-5 space-y-1">
            <li>Per transazioni usa il prefisso <code className="text-[var(--lattice-gold)]">tx-…</code></li>
            <li>Per blocchi inserisci solo il numero (es. <code className="text-[var(--lattice-gold)]">42</code>)</li>
            <li>Per hash documento incolla l&apos;esadecimale completo (SHA-3 / SHA-256)</li>
            <li>Per identità LNS usa il nome completo (es. <code className="text-[var(--lattice-gold)]">admin.acme.lns</code>)</li>
          </ul>
        </div>
      )}
      {data && data.type && (
        <div className="font-mono-data text-[12px] text-[var(--lattice-gold)]">Reindirizzo a /{data.type}/…</div>
      )}
    </main>
  );
}

function TxDetail() {
  const { tx_id } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    setData(null); setErr("");
    api.get(`/explorer/tx/${encodeURIComponent(tx_id)}`)
      .then((r) => setData(r.data))
      .catch((e) => setErr(e?.response?.data?.detail || "errore"));
  }, [tx_id]);

  return (
    <main className="max-w-5xl mx-auto px-6 py-10 space-y-6" data-testid="explorer-tx-detail">
      <SearchBar onSubmit={(nq) => window.location.assign(`/explorer/search?q=${encodeURIComponent(nq)}`)} />
      <Link to="/explorer" className="font-mono-data text-[11px] text-[var(--lattice-text-3)] hover:text-white flex items-center gap-2" data-testid="explorer-tx-back">
        <ArrowLeft size={12} /> torna all&apos;explorer
      </Link>

      {err && (
        <div className="surface-elev border border-rose-500/40 bg-rose-500/5 px-5 py-4">
          <div className="eyebrow text-rose-300 mb-1">TRANSAZIONE NON TROVATA</div>
          <p className="text-[13px] text-[var(--lattice-text-2)]">
            Nessuna tx con id <code className="font-mono-data text-[var(--lattice-gold)]">{tx_id}</code>.
          </p>
        </div>
      )}

      {data && (
        <>
          <section>
            <div className="eyebrow flex items-center gap-2 text-[var(--lattice-gold)]"><Hash size={11} /> TRANSAZIONE</div>
            <h1 className="font-display text-3xl mt-2 break-all" data-testid="explorer-tx-id">{data.transaction.tx_id}</h1>
            <div className="flex items-center gap-3 mt-3 flex-wrap">
              <VerifyBadge verified={data.verified} algorithm={data.algorithm} />
              <span className="pill pill-slate">{data.transaction.kind}</span>
              {data.transaction.signed_with && (
                <span className="font-mono-data text-[10px] text-emerald-300 border border-emerald-500/30 px-2 py-0.5">
                  {data.transaction.signed_with}
                </span>
              )}
            </div>
            <p className="text-[12px] text-[var(--lattice-text-2)] mt-3 max-w-3xl leading-relaxed">{data.verify_detail}</p>
          </section>

          <section className="surface-elev border hairline relative" data-testid="explorer-tx-fields">
            <div className="absolute top-0 left-0 right-0 h-px gold-line opacity-60" />
            <div className="px-6 py-5 grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4 font-mono-data text-[12px]">
              <Field label="BLOCK" value={data.transaction.block_index} link={`/explorer/block/${data.transaction.block_index}`} tid="explorer-tx-block" />
              <Field label="TIMESTAMP" value={fmtTime(data.transaction.timestamp)} tid="explorer-tx-timestamp" />
              <Field label="KIND" value={data.transaction.kind} tid="explorer-tx-kind" />
              <Field label="SUMMARY" value={data.transaction.summary} tid="explorer-tx-summary" />
              <Field label="SIGNER ENTITY" value={data.transaction.signer_entity} link={data.transaction.signer_entity ? `/explorer/lns/${data.transaction.signer_entity}` : null} tid="explorer-tx-signer" />
              {data.transaction.delegated_for && (
                <Field label="DELEGATED FOR (mittente reale)" value={data.transaction.delegated_for} link={`/explorer/lns/${data.transaction.delegated_for}`} tid="explorer-tx-delegated-for" />
              )}
              <Field label="PUBLIC KEY FINGERPRINT" value={data.transaction.sender_public_key} copy tid="explorer-tx-pkfp" />
              {data.transaction.doc_hash && (
                <Field label="DOC HASH" value={data.transaction.doc_hash} copy tid="explorer-tx-dochash" wide />
              )}
              <Field label="SIGNATURE (firma ML-DSA-65)" value={data.transaction.signature} copy tid="explorer-tx-signature" wide truncate />
            </div>
          </section>

          {data.block && (
            <section className="surface-elev border hairline" data-testid="explorer-tx-block-card">
              <header className="px-6 py-4 border-b hairline flex items-center justify-between">
                <div className="eyebrow flex items-center gap-2 text-[var(--lattice-gold)]"><Box size={11} /> ANCORATA NEL BLOCCO #{data.block.index}</div>
                <Link to={`/explorer/block/${data.block.index}`} className="font-mono-data text-[10px] text-[var(--lattice-gold)] hover:underline">apri blocco →</Link>
              </header>
              <div className="px-6 py-5 grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-3 font-mono-data text-[12px]">
                <Field label="BLOCK HASH" value={data.block.block_hash} copy />
                <Field label="MERKLE ROOT" value={data.block.merkle_root} copy />
                <Field label="PROPOSER" value={data.block.proposer} />
                <Field label="VOTI QBFT" value={(data.block.qbft_votes || []).length} />
              </div>
            </section>
          )}
        </>
      )}
    </main>
  );
}

function VerifyBadge({ verified, algorithm }) {
  if (verified === true) {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 border border-emerald-500/50 bg-emerald-500/10 text-emerald-300 font-mono-data text-[11px] tracking-[0.15em] uppercase" data-testid="explorer-verify-ok">
        <ShieldCheck size={12} /> firma valida · {algorithm}
      </span>
    );
  }
  if (verified === false) {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 border border-rose-500/50 bg-rose-500/10 text-rose-300 font-mono-data text-[11px] tracking-[0.15em] uppercase" data-testid="explorer-verify-fail">
        <ShieldAlert size={12} /> firma NON valida
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-3 py-1 border hairline text-[var(--lattice-text-3)] font-mono-data text-[11px] tracking-[0.15em] uppercase" data-testid="explorer-verify-legacy">
      seed legacy
    </span>
  );
}

function Field({ label, value, link, copy, tid, wide, truncate }) {
  const v = value === undefined || value === null || value === "" ? "—" : String(value);
  const display = truncate && v.length > 80 ? `${v.slice(0, 80)}…` : v;
  return (
    <div className={wide ? "md:col-span-2" : ""} data-testid={tid}>
      <div className="eyebrow text-[10px] flex items-center gap-1.5">
        {label}
        {copy && v !== "—" && <CopyButton value={v} tid={tid ? `${tid}-copy` : undefined} />}
      </div>
      <div className="text-white mt-1 break-all">
        {link ? <Link to={link} className="text-[var(--lattice-gold)] hover:underline">{display}</Link> : display}
      </div>
    </div>
  );
}

function BlockDetail() {
  const { block_index } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    setData(null); setErr("");
    api.get(`/explorer/block/${block_index}`)
      .then((r) => setData(r.data))
      .catch((e) => setErr(e?.response?.data?.detail || "errore"));
  }, [block_index]);

  return (
    <main className="max-w-6xl mx-auto px-6 py-10 space-y-6" data-testid="explorer-block-detail">
      <SearchBar onSubmit={(nq) => window.location.assign(`/explorer/search?q=${encodeURIComponent(nq)}`)} />
      <Link to="/explorer" className="font-mono-data text-[11px] text-[var(--lattice-text-3)] hover:text-white flex items-center gap-2" data-testid="explorer-block-back">
        <ArrowLeft size={12} /> torna all&apos;explorer
      </Link>

      {err && (
        <div className="surface-elev border border-rose-500/40 bg-rose-500/5 px-5 py-4">
          <div className="eyebrow text-rose-300 mb-1">BLOCCO NON TROVATO</div>
          <p className="text-[13px] text-[var(--lattice-text-2)]">
            Nessun blocco con indice <code className="font-mono-data text-[var(--lattice-gold)]">{block_index}</code>.
          </p>
        </div>
      )}

      {data && (
        <>
          <section className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <div className="eyebrow flex items-center gap-2 text-[var(--lattice-gold)]"><Box size={11} /> BLOCCO</div>
              <h1 className="font-display text-4xl mt-2" data-testid="explorer-block-index">#{data.block.index}</h1>
              <div className="font-mono-data text-[11px] text-[var(--lattice-text-3)] mt-1">{fmtTime(data.block.timestamp)}</div>
            </div>
            <div className="flex items-center gap-2">
              {data.prev && (
                <Link to={`/explorer/block/${data.prev.index}`} data-testid="explorer-block-prev" className="px-3 py-2 border hairline font-mono-data text-[10px] uppercase tracking-[0.18em] text-[var(--lattice-text-2)] hover:text-white hover:border-[var(--lattice-gold)] flex items-center gap-2">
                  <ArrowLeft size={10} /> #{data.prev.index}
                </Link>
              )}
              {data.next && (
                <Link to={`/explorer/block/${data.next.index}`} data-testid="explorer-block-next" className="px-3 py-2 border hairline font-mono-data text-[10px] uppercase tracking-[0.18em] text-[var(--lattice-text-2)] hover:text-white hover:border-[var(--lattice-gold)] flex items-center gap-2">
                  #{data.next.index} <ArrowRight size={10} />
                </Link>
              )}
            </div>
          </section>

          <section className="surface-elev border hairline relative">
            <div className="absolute top-0 left-0 right-0 h-px gold-line opacity-60" />
            <div className="px-6 py-5 grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4 font-mono-data text-[12px]">
              <Field label="BLOCK HASH" value={data.block.block_hash} copy wide tid="explorer-block-hash" />
              <Field label="PREVIOUS HASH" value={data.block.previous_hash} copy wide />
              <Field label="MERKLE ROOT" value={data.block.merkle_root} copy />
              <Field label="PROPOSER" value={data.block.proposer} />
              <Field label="ALGORITMO" value={data.block.signed_with} />
              <Field label="VOTI QBFT" value={(data.block.qbft_votes || []).length} />
              <Field label="TX COUNT" value={data.block.transactions_count} />
              <Field label="TX IDs" value={(data.block.tx_ids || []).join(", ") || "—"} wide truncate />
            </div>
          </section>

          {data.transactions?.length > 0 && (
            <section className="surface-elev border hairline" data-testid="explorer-block-txs">
              <header className="px-6 py-4 border-b hairline">
                <div className="eyebrow flex items-center gap-2 text-[var(--lattice-gold)]"><FileSignature size={11} /> TRANSAZIONI NEL BLOCCO</div>
              </header>
              <div className="overflow-x-auto">
                <table className="lattice-table">
                  <thead><tr><th>TX</th><th>KIND</th><th>FIRMATARIO</th><th>ALG</th></tr></thead>
                  <tbody>
                    {data.transactions.map((t) => (
                      <tr key={t.tx_id} data-testid={`explorer-block-tx-${t.tx_id}`}>
                        <td className="font-mono-data text-[11px]">
                          <Link to={`/explorer/tx/${t.tx_id}`} className="text-[var(--lattice-gold)] hover:underline">{shortHash(t.tx_id, 12, 6)}</Link>
                        </td>
                        <td><span className="pill pill-slate">{t.kind}</span></td>
                        <td className="font-mono-data text-[11px] text-[var(--lattice-text-2)]">{t.signer_entity || "—"}</td>
                        <td className="font-mono-data text-[10px] text-emerald-300">{t.signed_with || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}
    </main>
  );
}

function LnsDetail() {
  const { lns_name } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    setData(null); setErr("");
    api.get(`/explorer/lns/${encodeURIComponent(lns_name)}`)
      .then((r) => setData(r.data))
      .catch((e) => setErr(e?.response?.data?.detail || "errore"));
  }, [lns_name]);

  return (
    <main className="max-w-5xl mx-auto px-6 py-10 space-y-6" data-testid="explorer-lns-detail">
      <SearchBar onSubmit={(nq) => window.location.assign(`/explorer/search?q=${encodeURIComponent(nq)}`)} />
      <Link to="/explorer" className="font-mono-data text-[11px] text-[var(--lattice-text-3)] hover:text-white flex items-center gap-2">
        <ArrowLeft size={12} /> torna all&apos;explorer
      </Link>

      {err && (
        <div className="surface-elev border border-rose-500/40 bg-rose-500/5 px-5 py-4">
          <div className="eyebrow text-rose-300 mb-1">IDENTITÀ NON TROVATA</div>
          <p className="text-[13px] text-[var(--lattice-text-2)]">
            Nessuna identità LNS con nome <code className="font-mono-data text-[var(--lattice-gold)]">{lns_name}</code>.
          </p>
        </div>
      )}

      {data && (
        <>
          <section>
            <div className="eyebrow flex items-center gap-2 text-[var(--lattice-gold)]"><Network size={11} /> IDENTITÀ LNS</div>
            <h1 className="font-display text-3xl mt-2 break-all" data-testid="explorer-lns-name">{data.lns.lns_name}</h1>
            <div className="flex items-center gap-3 mt-3 flex-wrap">
              {data.keystore?.algorithm && (
                <span className="font-mono-data text-[10px] text-emerald-300 border border-emerald-500/30 px-2 py-0.5">{data.keystore.algorithm}</span>
              )}
              {data.lns.role && <span className="pill pill-slate">{data.lns.role}</span>}
            </div>
          </section>

          <section className="surface-elev border hairline relative">
            <div className="absolute top-0 left-0 right-0 h-px gold-line opacity-60" />
            <div className="px-6 py-5 grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4 font-mono-data text-[12px]">
              <Field label="OWNER" value={data.lns.owner_id} />
              <Field label="REGISTRATA IL" value={fmtTime(data.lns.registered_at)} />
              <Field label="FINGERPRINT CHIAVE" value={data.keystore?.fingerprint || data.lns.public_key_fingerprint} copy />
              <Field label="ALGORITMO" value={data.keystore?.algorithm || "ML-DSA-65"} />
              <Field label="PUBLIC KEY (hex, ML-DSA-65)" value={data.keystore?.pk_hex} copy wide truncate />
            </div>
          </section>

          <section className="surface-elev border hairline" data-testid="explorer-lns-txs">
            <header className="px-6 py-4 border-b hairline">
              <div className="eyebrow flex items-center gap-2 text-[var(--lattice-gold)]"><FileSignature size={11} /> ULTIME 20 TRANSAZIONI FIRMATE</div>
              <p className="text-[11px] text-[var(--lattice-text-3)] mt-1">Ogni firma è verificabile matematicamente contro la chiave pubblica qui sopra.</p>
            </header>
            <div className="overflow-x-auto">
              <table className="lattice-table">
                <thead><tr><th>#BLK</th><th>TX</th><th>KIND</th><th>SUMMARY</th><th>QUANDO</th></tr></thead>
                <tbody>
                  {(data.recent_transactions || []).length === 0 && (
                    <tr><td colSpan={5} className="text-center py-6 font-mono-data text-[12px] text-[var(--lattice-text-3)]">Nessuna transazione.</td></tr>
                  )}
                  {(data.recent_transactions || []).map((t) => (
                    <tr key={t.tx_id}>
                      <td className="font-mono-data text-[var(--lattice-gold)]">{t.block_index}</td>
                      <td className="font-mono-data text-[10px]"><Link to={`/explorer/tx/${t.tx_id}`} className="hover:underline">{shortHash(t.tx_id, 10, 6)}</Link></td>
                      <td><span className="pill pill-slate">{t.kind}</span></td>
                      <td className="font-mono-data text-[10px] text-[var(--lattice-text-2)] max-w-md truncate">{t.summary}</td>
                      <td className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">{fmtRelative(t.timestamp)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </main>
  );
}

export default function Explorer({ view = "home" }) {
  const navigate = useNavigate();
  const onSearch = (q) => navigate(`/explorer/search?q=${encodeURIComponent(q)}`);
  return (
    <div className="min-h-screen bg-[var(--lattice-bg)] text-white">
      <ExplorerHeader />
      {view === "home" && <ExplorerHome onSearch={onSearch} />}
      {view === "search" && <SearchResults />}
      {view === "tx" && <TxDetail />}
      {view === "block" && <BlockDetail />}
      {view === "lns" && <LnsDetail />}
      <footer className="border-t hairline mt-16">
        <div className="max-w-6xl mx-auto px-6 py-6 font-mono-data text-[11px] text-[var(--lattice-text-3)] flex flex-wrap items-center justify-between gap-3">
          <span>Lattice Network Explorer · No login · Verifica matematica ML-DSA-65</span>
          <Link to="/whitepaper" className="hover:text-white flex items-center gap-1">whitepaper <ExternalLink size={10} /></Link>
        </div>
      </footer>
    </div>
  );
}
