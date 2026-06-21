import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader, SectionPanel } from "@/components/Primitives";
import { Shield, Activity, Network, KeyRound, RefreshCw, ShieldCheck, ShieldAlert } from "lucide-react";
import { toast } from "sonner";

function StatusDot({ live }) {
  return <span className={`inline-block w-2.5 h-2.5 rounded-full ${live ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]" : "bg-red-400"}`} />;
}

export default function NetworkStatus() {
  const [qbft, setQbft] = useState(null);
  const [mix, setMix] = useState(null);
  const [pqc, setPqc] = useState(null);
  const [zk, setZk] = useState({ proof: null, verify: null, busy: false });
  const [refreshIdx, setRefreshIdx] = useState(0);

  useEffect(() => {
    const load = async () => {
      try {
        const [q, m, p] = await Promise.all([
          api.get("/qbft/status"),
          api.get("/mixnet/status"),
          api.get("/pqc/info"),
        ]);
        setQbft(q.data);
        setMix(m.data);
        setPqc(p.data);
      } catch (e) { console.warn(e); }
    };
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [refreshIdx]);

  const runZkRoundtrip = async () => {
    setZk({ proof: null, verify: null, busy: true });
    try {
      // 1. pull an LNS we can prove against
      const lns = (await api.get("/lns/active")).data?.[0]?.lns_name;
      if (!lns) throw new Error("no LNS available");
      const proof = await api.get(`/rln/zk/prove/${encodeURIComponent(lns)}`);
      const body = {
        epoch: proof.data.epoch,
        commitment_hex: proof.data.commitment_hex,
        nullifier_hex: proof.data.nullifier_hex,
        A_hex: proof.data.A_hex,
        B_hex: proof.data.B_hex,
        z_hex: proof.data.z_hex,
      };
      const ver = await api.post("/rln/zk/verify", body);
      setZk({ proof: proof.data, verify: ver.data, busy: false });
      toast.success(`ZK proof ${ver.data.ok ? "VALIDA" : "FALLITA"}`);
    } catch (e) {
      setZk({ proof: null, verify: null, busy: false });
      toast.error("Errore prova ZK: " + (e?.response?.data?.detail || e.message));
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="LATTICE NETWORK · LIVE STATUS"
        title="Stato della rete"
        subtitle="Tutti i componenti girano come processi reali in ascolto su porte indipendenti. Niente è simulato."
        right={
          <button
            onClick={() => setRefreshIdx((x) => x + 1)}
            data-testid="network-status-refresh"
            className="btn-ghost inline-flex items-center gap-2"
            style={{ padding: "6px 12px", fontSize: 11 }}
          >
            <RefreshCw size={12} /> Aggiorna
          </button>
        }
      />

      {/* QBFT panel */}
      <SectionPanel
        title={`Consenso QBFT · ${qbft?.live_count ?? 0}/${qbft?.total_count ?? 0} validator live`}
        eyebrow="REAL BYZANTINE FAULT TOLERANCE"
        testId="network-qbft-panel"
      >
        <div className="px-5 py-4">
          <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] mb-3">
            {qbft?.consensus} · {qbft?.implementation}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {(qbft?.validators ?? []).map((v) => (
              <div key={v.validator_id} className="border hairline px-4 py-3 surface" data-testid={`qbft-card-${v.validator_id}`}>
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono-data text-[12px] text-white">{v.validator_id}</span>
                  <StatusDot live={v.live} />
                </div>
                <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">port {v.port}</div>
                <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] break-all">pk {v.pk_fingerprint?.slice(0,16)}…</div>
                <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] mt-2">{v.signed_total ?? 0} blocchi firmati</div>
              </div>
            ))}
          </div>
          <div className="mt-4 flex items-center gap-2 font-mono-data text-[11px]">
            <ShieldCheck size={13} className={qbft?.quorum_reached ? "text-emerald-400" : "text-red-400"} />
            <span className="text-white">Quorum {qbft?.quorum_required}/{qbft?.total_count}</span>
            <span className="text-[var(--lattice-text-3)]">— ogni blocco richiede {qbft?.quorum_required} firme ML-DSA-65 da processi distinti</span>
          </div>
        </div>
      </SectionPanel>

      {/* Mixnet panel */}
      <SectionPanel
        title={`Mixnet Loopix · ${mix?.live_count ?? 0}/${mix?.total_count ?? 0} relay live`}
        eyebrow="REAL ONION ROUTING · 3 HOPS"
        testId="network-mixnet-panel"
      >
        <div className="px-5 py-4">
          <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] mb-3">
            {mix?.topology} · {mix?.implementation}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {(mix?.relays ?? []).map((r) => (
              <div key={r.relay_id} className="border hairline px-4 py-3 surface" data-testid={`mix-card-${r.relay_id}`}>
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono-data text-[12px] text-white">{r.relay_id} · L{r.layer}</span>
                  <StatusDot live={r.live} />
                </div>
                <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">port {r.port}</div>
                <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] break-all">X25519 pk {r.pk_hex?.slice(0,20)}…</div>
                <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] mt-2">{r.relayed_total ?? 0} pacchetti instradati</div>
              </div>
            ))}
          </div>
        </div>
      </SectionPanel>

      {/* PQC panel */}
      <SectionPanel
        title="Post-Quantum Cryptography"
        eyebrow="NIST FIPS 204 · LIVE"
        testId="network-pqc-panel"
      >
        <div className="px-5 py-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 font-mono-data text-[11px]">
            <div className="border hairline px-4 py-3 surface">
              <div className="text-[var(--lattice-text-3)] text-[10px] uppercase tracking-wider">Algoritmo</div>
              <div className="text-[var(--lattice-gold)] mt-1">{pqc?.algorithm}</div>
            </div>
            <div className="border hairline px-4 py-3 surface">
              <div className="text-[var(--lattice-text-3)] text-[10px] uppercase tracking-wider">Standard</div>
              <div className="text-white mt-1 text-[10px]">{pqc?.standard}</div>
            </div>
            <div className="border hairline px-4 py-3 surface">
              <div className="text-[var(--lattice-text-3)] text-[10px] uppercase tracking-wider">Implementazione</div>
              <div className="text-white mt-1 text-[10px]">{pqc?.implementation}</div>
            </div>
            <div className="border hairline px-4 py-3 surface">
              <div className="text-[var(--lattice-text-3)] text-[10px] uppercase tracking-wider">Dimensioni</div>
              <div className="text-white mt-1 text-[10px]">pk {pqc?.public_key_size_bytes}B · sig {pqc?.signature_size_bytes}B</div>
            </div>
          </div>
        </div>
      </SectionPanel>

      {/* ZK proof panel */}
      <SectionPanel
        title="Prova ZK in tempo reale"
        eyebrow="BN254 · CHAUM-PEDERSEN · FIAT-SHAMIR"
        testId="network-zk-panel"
      >
        <div className="px-5 py-4 space-y-3">
          <p className="text-[12px] text-[var(--lattice-text-3)] leading-relaxed">
            Esegui una vera prova zero-knowledge BN254: il backend produce una firma sigma che dimostra di conoscere il secret RLN di un'identità <em>senza mai rivelarlo</em>, poi la verifica con due equazioni di gruppo. Niente Groth16 mock — è il sigma protocol che sta sotto a tutte le ZK-RLN production.
          </p>
          <button
            data-testid="zk-roundtrip-btn"
            onClick={runZkRoundtrip}
            disabled={zk.busy}
            className="btn-gold inline-flex items-center gap-2"
          >
            <KeyRound size={13} /> {zk.busy ? "Calcolo in corso…" : "Esegui prove → verify"}
          </button>
          {zk.proof && (
            <div className="border hairline px-4 py-3 surface-2 space-y-2 font-mono-data text-[10px]" data-testid="zk-roundtrip-output">
              <div className="flex items-center gap-2">
                {zk.verify?.ok ? <ShieldCheck size={14} className="text-emerald-400" /> : <ShieldAlert size={14} className="text-red-400" />}
                <span className={`font-display text-[14px] ${zk.verify?.ok ? "text-emerald-300" : "text-red-300"}`}>
                  {zk.verify?.ok ? "PROVA VALIDA" : "PROVA FALLITA"}
                </span>
              </div>
              <div><span className="text-[var(--lattice-text-3)]">scheme:</span> <span className="text-[var(--lattice-gold)]">{zk.proof.scheme}</span></div>
              <div><span className="text-[var(--lattice-text-3)]">epoch:</span> <span className="text-white">{zk.proof.epoch}</span></div>
              <div><span className="text-[var(--lattice-text-3)]">commitment C:</span> <span className="text-white break-all">{zk.proof.commitment_hex}</span></div>
              <div><span className="text-[var(--lattice-text-3)]">nullifier N:</span> <span className="text-white break-all">{zk.proof.nullifier_hex}</span></div>
              <div><span className="text-[var(--lattice-text-3)]">A:</span> <span className="text-white break-all">{zk.proof.A_hex.slice(0,48)}…</span></div>
              <div><span className="text-[var(--lattice-text-3)]">B:</span> <span className="text-white break-all">{zk.proof.B_hex.slice(0,48)}…</span></div>
              <div><span className="text-[var(--lattice-text-3)]">z:</span> <span className="text-white break-all">{zk.proof.z_hex}</span></div>
              <div className="pt-2 border-t hairline">
                <span className="text-[var(--lattice-text-3)]">detail:</span> <span className="text-white">{zk.verify?.detail}</span>
              </div>
            </div>
          )}
        </div>
      </SectionPanel>
    </div>
  );
}
