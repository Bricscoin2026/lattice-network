import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Boxes, ShieldCheck, Cpu, Activity, AlertTriangle, Check, Loader2 } from "lucide-react";

function Row({ k, v, tid }) {
  return (
    <div className="flex justify-between py-1.5 border-b hairline last:border-0" data-testid={tid}>
      <span className="font-mono-data text-[11px] text-[var(--lattice-text-3)] uppercase tracking-[0.1em]">{k}</span>
      <span className="font-mono-data text-[11px] text-white text-right break-all max-w-[60%]">{v}</span>
    </div>
  );
}

export default function RustBridge() {
  const [info, setInfo] = useState(null);
  const [selftest, setSelftest] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.get("/rust/info").then(r => setInfo(r.data)).catch(e => setErr(e?.response?.data?.detail || "Bridge non raggiungibile"));
  }, []);

  const runSelftest = async () => {
    setBusy(true); setErr("");
    try {
      const r = await api.get("/rust/selftest");
      setSelftest(r.data);
    } catch (e) {
      setErr(e?.response?.data?.detail || "Selftest fallito");
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-8" data-testid="rust-bridge-page">
      <div>
        <div className="eyebrow flex items-center gap-2 mb-1">
          <Cpu size={11} className="text-[var(--lattice-gold)]" /> ARCHITETTURA · GATEWAY RUST NATIVO
        </div>
        <h1 className="font-display text-4xl text-white">Rust nativo (Axum)</h1>
        <p className="text-[13px] text-[var(--lattice-text-3)] mt-2 max-w-3xl leading-relaxed">
          L'API gateway è un binario Rust standalone (<code className="text-[var(--lattice-gold)]">lattice-gateway</code>) basato
          su <strong className="text-white">Axum + Tokio</strong> in ascolto su porta 8002. Tutti gli ~89 endpoint
          (Pulse, Certify, Auth, LNS, Attachments, OTS, audit chain) sono compilati in Rust e usano
          <strong className="text-white"> esecuzione Rust nativa</strong> per i primitivi crittografici NIST FIPS 202/203/204
          — nessun PyO3, nessun fallback Python, nessun simulatore.
        </p>
      </div>

      {/* Status */}
      <div className="surface-elev border hairline p-5">
        <div className="flex items-center gap-2 mb-3">
          {info?.available ? (
            <><Check size={14} className="text-emerald-400" /><span className="font-mono-data text-[11px] uppercase tracking-[0.15em] text-emerald-300">BRIDGE ATTIVO</span></>
          ) : (
            <><AlertTriangle size={14} className="text-amber-300" /><span className="font-mono-data text-[11px] uppercase tracking-[0.15em] text-amber-300">BRIDGE NON DISPONIBILE</span></>
          )}
        </div>
        {info && (
          <div className="grid md:grid-cols-2 gap-x-8">
            <div>
              <Row k="versione" v={info.version || "—"} tid="rust-version" />
              <Row k="binding" v={info.binding || "—"} />
              <Row k="crate" v={info.crate || "—"} />
            </div>
            <div>
              <Row k="SHA3-512 proof input" v={info.proof?.input_utf8 || "—"} />
              <Row k="SHA3-512 output (Rust)" v={info.proof?.sha3_512_rust_hex?.slice(0, 32) + "…" || "—"} tid="rust-proof-hash" />
              <Row k="exec by" v={info.proof?.computed_by || "—"} />
            </div>
          </div>
        )}
        {info?.exposes && (
          <div className="mt-4">
            <div className="eyebrow mb-2">FUNZIONI ESPOSTE</div>
            <ul className="space-y-1">
              {info.exposes.map((fn) => (
                <li key={fn} className="font-mono-data text-[11px] text-[var(--lattice-gold)]">→ {fn}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Live ML-DSA-65 selftest */}
      <div className="surface-elev border hairline p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="eyebrow flex items-center gap-2"><ShieldCheck size={11} className="text-[var(--lattice-gold)]" /> SELFTEST ML-DSA-65</div>
            <p className="text-[12px] text-[var(--lattice-text-3)] mt-1">
              Genera una keypair → firma un nonce casuale → verifica. <strong className="text-white">Tutto in Rust nativo.</strong>
            </p>
          </div>
          <button
            data-testid="run-rust-selftest"
            onClick={runSelftest}
            disabled={busy || !info?.available}
            className="btn-gold inline-flex items-center gap-2"
          >
            {busy ? <Loader2 size={13} className="animate-spin" /> : <Activity size={13} />}
            {busy ? "esecuzione…" : "esegui ora"}
          </button>
        </div>
        {selftest && (
          <div className="surface-2 border hairline p-4 space-y-1">
            <Row k="algoritmo" v={selftest.algorithm} />
            <Row k="eseguito da" v={selftest.computed_in} tid="selftest-runtime" />
            <Row k="public key" v={`${selftest.public_key_bytes} bytes`} />
            <Row k="secret key" v={`${selftest.secret_key_bytes} bytes`} />
            <Row k="signature" v={`${selftest.signature_bytes} bytes`} />
            <Row k="fingerprint" v={selftest.fingerprint} tid="selftest-fp" />
            <Row k="nonce firmato" v={selftest.nonce_hex.slice(0, 24) + "…"} />
            <Row k="signature head" v={selftest.signature_first_32_hex + "…"} />
            <div className="pt-2 mt-2 border-t hairline">
              <span className={`font-mono-data text-[11px] ${selftest.verify_ok ? "text-emerald-300" : "text-rose-300"}`} data-testid="selftest-verify-ok">
                {selftest.verify_ok ? "✓ VERIFICA OK · firma valida" : "✗ VERIFICA FALLITA"}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Architecture note */}
      <div className="surface-elev border hairline p-5">
        <div className="eyebrow mb-2 flex items-center gap-2"><Boxes size={11} className="text-[var(--lattice-gold)]" /> ARCHITETTURA</div>
        <pre className="font-mono-data text-[10px] text-[var(--lattice-text-2)] leading-relaxed whitespace-pre-wrap">
{`/app/lattice/                                  ← Workspace Cargo (Rust)
├── core/lattice-crypto/   (BSL 1.1)            ← ML-DSA-65 · ML-KEM-768 · SHA3
├── core/lattice-node/     (BSL 1.1)            ← QBFT chain
├── core/pulse-protocol/   (BSL 1.1)            ← AES-256-GCM + sealed sender
├── core/pulse-ratchet/    (BSL 1.1)            ← PQXDH + Double Ratchet
├── core/lattice-zk-rln/   (BSL 1.1)            ← rate-limit ZK
├── core/lattice-mixnet/   (BSL 1.1)            ← Loopix relay
├── prod/qbft-validator    (Commercial)         ← binario standalone
├── prod/mixnet-relay      (Commercial)         ← binario standalone
└── prod/lattice-gateway/  (Commercial)         ← ◀ Axum API gateway
                            cargo build --release
                            ↓
                            lattice-gateway (port 8002)
                            ↓
                            ~89 endpoint /api/* nativi
                            ↓
                            /api/rust/info
                            /api/rust/selftest`}
        </pre>
        <p className="text-[12px] text-[var(--lattice-text-3)] mt-3 leading-relaxed">
          <strong className="text-white">Architettura attuale (M8 finale):</strong> il gateway Rust nativo
          è il front-end primario per ~89 endpoint, mentre il backend Python residuo agisce come thin
          reverse-proxy verso <code className="text-[var(--lattice-gold)]">127.0.0.1:8002</code> per il
          preview Kubernetes. In produzione (Hetzner) nginx fa lo split-routing direttamente. Ogni firma
          ML-DSA-65 e ogni hash SHA3 è calcolata dai crate Rust sopra elencati — il binario è 100%
          self-contained, niente PyO3, niente runtime Python nel percorso di firma.
        </p>
      </div>

      {err && (
        <div className="border border-red-500/40 bg-red-500/5 px-4 py-3 text-[12px] text-red-300">{err}</div>
      )}
    </div>
  );
}
