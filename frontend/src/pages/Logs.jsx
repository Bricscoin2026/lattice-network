import { useEffect, useRef, useState } from "react";
import { useLang } from "@/i18n/LangProvider";
import { API } from "@/lib/api";
import { loadSession } from "@/lib/pqcAuth";
import { Link } from "react-router-dom";
import { PageHeader, SectionPanel } from "@/components/Primitives";
import { TID } from "@/constants/lattice-testids";
import { Pause, Play, Trash2, Radio, Lock, ArrowRight } from "lucide-react";

const LEVELS = ["ALL", "INFO", "WARN", "ERROR", "AUDIT"];
const MAX_LINES = 400;

export default function Logs() {
  const { t } = useLang();
  const session = loadSession();
  const isAuthed = !!(session && session.lns_name);
  const [lines, setLines] = useState([]);
  const [paused, setPaused] = useState(false);
  const [level, setLevel] = useState("ALL");
  const [connected, setConnected] = useState(false);
  const containerRef = useRef(null);
  const esRef = useRef(null);

  useEffect(() => {
    if (!isAuthed) return;
    if (paused) {
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
        setConnected(false);
      }
      return;
    }
    let cancelled = false;
    const es = new EventSource(`${API}/logs/sse?rate=0.6&batch=4`);
    esRef.current = es;
    es.onopen = () => {
      if (!cancelled) setConnected(true);
    };
    es.onerror = () => {
      if (!cancelled) setConnected(false);
    };
    es.addEventListener("backfill", (ev) => {
      try {
        const arr = JSON.parse(ev.data);
        if (!cancelled) setLines(arr.slice(0, MAX_LINES));
      } catch {
        // noop
      }
    });
    es.onmessage = (ev) => {
      try {
        const arr = JSON.parse(ev.data);
        if (!Array.isArray(arr) || arr.length === 0) return;
        if (!cancelled) {
          setLines((prev) => {
            const next = [...arr, ...prev];
            return next.slice(0, MAX_LINES);
          });
        }
      } catch {
        // noop
      }
    };
    return () => {
      cancelled = true;
      es.close();
      esRef.current = null;
      setConnected(false);
    };
  }, [paused, isAuthed]);

  if (!isAuthed) {
    return (
      <div className="space-y-8" data-testid="logs-locked">
        <PageHeader
          eyebrow={t.logs.eyebrow}
          title={t.logs.title}
          subtitle={t.logs.subtitle}
        />
        <div className="surface-elev border hairline relative max-w-2xl">
          <div className="absolute top-0 left-0 right-0 h-px gold-line opacity-60" />
          <div className="px-6 py-6 flex items-start gap-4">
            <div className="border hairline w-11 h-11 flex items-center justify-center shrink-0 bg-[rgba(212,175,55,0.04)]">
              <Lock size={18} className="text-[var(--lattice-gold)]" />
            </div>
            <div className="flex-1">
              <div className="eyebrow text-[var(--lattice-gold)] mb-1">ACCESSO RISERVATO</div>
              <h3 className="font-display text-xl text-white">Log SSE solo per Sovereign Admin</h3>
              <p className="text-[13px] text-[var(--lattice-text-2)] mt-2 leading-relaxed">
                Lo stream live dei log della rete è disponibile esclusivamente al{" "}
                <strong className="text-white">Sovereign Admin autenticato</strong>. Effettua il login
                per visualizzare in tempo reale gli eventi QBFT, mixnet, audit e RLN.
              </p>
              <p className="text-[12px] text-[var(--lattice-text-3)] mt-3">
                Se cerchi di verificare una transazione o un hash <strong className="text-[var(--lattice-gold)]">senza login</strong>,
                usa il Public Block Explorer.
              </p>
              <div className="mt-5 flex flex-wrap gap-3">
                <Link
                  to="/login"
                  data-testid="logs-login-cta"
                  className="px-4 py-2 border border-[var(--lattice-gold)] text-[var(--lattice-gold)] font-mono-data text-[11px] tracking-[0.18em] uppercase hover:bg-[rgba(212,175,55,0.08)] flex items-center gap-2"
                >
                  Login Sovereign Admin <ArrowRight size={12} />
                </Link>
                <Link
                  to="/explorer"
                  data-testid="logs-explorer-cta"
                  className="px-4 py-2 border hairline text-[var(--lattice-text-2)] font-mono-data text-[11px] tracking-[0.18em] uppercase hover:text-white hover:border-[var(--lattice-gold)] flex items-center gap-2"
                >
                  Apri Public Explorer <ArrowRight size={12} />
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const filtered = level === "ALL" ? lines : lines.filter((l) => l.level === level);

  const fmtLine = (l) => {
    const ts = (l.ts || "").slice(11, 23);
    return `[${ts}] ${l.level.padEnd(5)} ${l.component.padEnd(20)} ${(l.node_id || "").slice(0, 12).padEnd(12)} │ ${l.message}`;
  };

  const lvlClass = (lvl) =>
    lvl === "ERROR" ? "log-error" : lvl === "WARN" ? "log-warn" : lvl === "AUDIT" ? "log-audit" : "log-info";

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={t.logs.eyebrow}
        title={t.logs.title}
        subtitle={t.logs.subtitle}
        right={
          <div className="flex items-center gap-2">
            <span
              data-testid={TID.logsSseStatus}
              className={`pill ${connected ? "pill-online" : "pill-offline"} inline-flex items-center`}
            >
              <Radio size={11} strokeWidth={2} />
              {connected ? t.sseConnected : t.sseDisconnected}
            </span>
            {paused ? (
              <button data-testid={TID.logsResumeBtn} onClick={() => setPaused(false)} className="btn-ghost inline-flex items-center gap-2">
                <Play size={12} /> {t.logs.resume}
              </button>
            ) : (
              <button data-testid={TID.logsPauseBtn} onClick={() => setPaused(true)} className="btn-ghost inline-flex items-center gap-2">
                <Pause size={12} /> {t.logs.pause}
              </button>
            )}
            <button onClick={() => setLines([])} className="btn-ghost inline-flex items-center gap-2">
              <Trash2 size={12} /> {t.common.cancel === "Annulla" ? "Pulisci" : "Clear"}
            </button>
          </div>
        }
      />

      <SectionPanel
        title={t.logs.title}
        eyebrow={t.logs.eyebrow}
        testId={TID.logsTerminal}
        right={
          <div className="flex items-center gap-2 flex-wrap" data-testid={TID.logsLevelFilter}>
            <span className="eyebrow mr-2">{t.logs.filter}</span>
            {LEVELS.map((lvl) => (
              <button
                key={lvl}
                onClick={() => setLevel(lvl)}
                className={`font-mono-data text-[10px] uppercase tracking-[0.2em] px-2.5 py-1 border transition-colors ${
                  level === lvl
                    ? "bg-[var(--lattice-gold)] text-[var(--lattice-bg)] border-[var(--lattice-gold)]"
                    : "bg-transparent text-[var(--lattice-text-3)] border-[var(--lattice-border-strong)] hover:text-white hover:border-[var(--lattice-gold)]"
                }`}
              >
                {t.logs.levels[lvl] || lvl}
              </button>
            ))}
          </div>
        }
      >
        <div className="terminal" ref={containerRef} style={{ height: 560, overflow: "auto" }}>
          <div className="px-4 py-3 border-b hairline flex items-center gap-3 bg-[#070b14]">
            <div className="flex gap-1.5">
              <span className="dot" style={{ background: "#7f1d1d", boxShadow: "0 0 8px #7f1d1d" }} />
              <span className="dot" style={{ background: "#854d0e", boxShadow: "0 0 8px #854d0e" }} />
              <span className="dot" style={{ background: "#065f46", boxShadow: "0 0 8px #065f46" }} />
            </div>
            <span className="font-mono-data text-[11px] text-[var(--lattice-text-3)]">
              lattice@sovereign-cluster:~$ sse-tail -F /var/log/lattice/qbft.aggregated
            </span>
            <span className="ml-auto font-mono-data text-[10px] text-[var(--lattice-gold)]">
              {paused ? t.paused : t.live} · {filtered.length}
            </span>
          </div>
          <div className="py-2">
            {filtered.length === 0 && (
              <div className="px-4 py-6 font-mono-data text-[11px] text-[var(--lattice-text-4)]">{t.common.loading}</div>
            )}
            {filtered.map((l, i) => (
              <div key={`${l.ts}-${i}`} className={`terminal-line ${lvlClass(l.level)}`}>
                {fmtLine(l)}
              </div>
            ))}
          </div>
        </div>
      </SectionPanel>
    </div>
  );
}
