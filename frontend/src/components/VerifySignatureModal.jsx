import { useState } from "react";
import { api } from "@/lib/api";
import { ShieldCheck, X, CheckCircle2, XCircle, Loader2, Copy, ExternalLink, Hash } from "lucide-react";

/**
 * Hook + Modal pattern (React 19 friendly).
 *
 *   const verifier = useVerify();
 *   <button onClick={() => verifier.open(txId, "Mail · ricevuta")}>verifica</button>
 *   <VerifySignatureModal {...verifier.props} />
 */
export function useVerify() {
  const [s, setS] = useState({ open: false, loading: false, data: null, error: null, label: "" });
  const close = () => setS({ open: false, loading: false, data: null, error: null, label: "" });
  const open = (txId, label) => {
    setS({ open: true, loading: true, data: null, error: null, label: label || "Transazione on-chain" });
    api.get(`/ledger/verify/${txId}`)
      .then((r) => setS((p) => p.open ? { ...p, loading: false, data: { ...r.data, _txId: txId } } : p))
      .catch((e) => setS((p) => p.open ? {
        ...p, loading: false, data: { _txId: txId },
        error: e?.response?.data?.detail || e.message || "Errore di verifica",
      } : p));
  };
  return { open, close, props: { ...s, onClose: close } };
}

export default function VerifySignatureModal({ open, loading, data, error, label, onClose }) {
  if (!open) return null;
  const ok = data?.ok === true;
  const txId = data?._txId || "";
  const copy = (txt) => navigator.clipboard?.writeText(txt);

  return (
    <div
      data-testid="verify-signature-modal"
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="surface-elev border hairline w-full max-w-2xl relative"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="absolute top-0 left-0 right-0 h-px gold-line" />
        <header className="px-6 py-4 border-b hairline flex items-center justify-between">
          <div>
            <div className="eyebrow flex items-center gap-2 text-[var(--lattice-gold)]">
              <ShieldCheck size={11} /> VERIFICA FIRMA BFT
            </div>
            <p className="text-[11px] text-[var(--lattice-text-3)] mt-1 font-mono-data">{label || ""}</p>
          </div>
          <button
            data-testid="verify-modal-close"
            onClick={onClose}
            className="text-[var(--lattice-text-3)] hover:text-white"
          ><X size={18} /></button>
        </header>
        <div className="px-6 py-6 space-y-4">
          {loading && (
            <div className="flex items-center gap-3 text-[var(--lattice-text-2)] py-6">
              <Loader2 size={16} className="animate-spin" />
              <span className="font-mono-data text-[12px]">Verificando la firma sui nodi…</span>
            </div>
          )}
          {error && (
            <div className="border border-rose-500/40 bg-rose-500/5 px-4 py-3 flex items-start gap-3">
              <XCircle size={18} className="text-rose-300 mt-0.5 shrink-0" />
              <div>
                <div className="eyebrow text-rose-300">VERIFICA FALLITA</div>
                <div className="font-mono-data text-[12px] text-[var(--lattice-text-2)] mt-1">{error}</div>
              </div>
            </div>
          )}
          {data && !error && (
            <>
              <div className={`border px-4 py-3 flex items-start gap-3 ${
                ok ? "border-emerald-500/40 bg-emerald-500/5" : "border-rose-500/40 bg-rose-500/5"
              }`}>
                {ok
                  ? <CheckCircle2 size={22} className="text-emerald-300 mt-0.5 shrink-0" />
                  : <XCircle size={22} className="text-rose-300 mt-0.5 shrink-0" />}
                <div className="flex-1">
                  <div className={`font-display text-lg ${ok ? "text-emerald-200" : "text-rose-200"}`}>
                    {ok ? "Firma valida · catena integra" : "Firma NON valida"}
                  </div>
                  <div className="text-[12px] text-[var(--lattice-text-2)] mt-1 leading-relaxed">
                    {ok
                      ? "La firma post-quantistica ML-DSA-65 è stata verificata dai validator BFT con la chiave pubblica registrata in keystore. Il messaggio è autentico e non manomesso."
                      : (data.detail || "La firma non corrisponde al contenuto firmato.")}
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px]">
                <Field label="Algoritmo" value={data.signed_with || "—"} ok={data.signed_with === "ML-DSA-65"} />
                <Field label="Standard" value="NIST FIPS 204" />
                <Field label="TX ID" value={txId} copyable copy={copy} />
                <Field label="Firmatario" value={data.signer_entity || data.signer || "—"} />
                {data.block_index !== undefined && <Field label="Blocco" value={`#${data.block_index}`} />}
                {data.timestamp && <Field label="Notarizzato il" value={String(data.timestamp).slice(0, 19).replace("T", " ")} />}
              </div>
              {data.signature_preview && (
                <div className="border hairline px-3 py-2">
                  <div className="eyebrow text-[10px] mb-1 flex items-center gap-1">
                    <Hash size={9} /> FIRMA (preview)
                  </div>
                  <div className="font-mono-data text-[10px] text-[var(--lattice-text-2)] break-all">
                    {data.signature_preview}
                  </div>
                </div>
              )}
              <div className="border-t hairline pt-3 flex items-center justify-between gap-3">
                <a
                  href={`/api/ledger/verify/${txId}`}
                  target="_blank"
                  rel="noreferrer"
                  data-testid="verify-modal-raw-link"
                  className="font-mono-data text-[10px] uppercase tracking-wider text-[var(--lattice-text-3)] hover:text-white flex items-center gap-1"
                >
                  <ExternalLink size={10} /> JSON raw
                </a>
                <span className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">
                  Verificato da {data.qbft_quorum || 3}/{data.qbft_total_validators || 4} validator BFT
                </span>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, value, ok, copyable, copy }) {
  return (
    <div className="border hairline px-3 py-2">
      <div className="eyebrow text-[10px] mb-1">{label}</div>
      <div className="flex items-center justify-between gap-2">
        <div className={`font-mono-data text-[11px] break-all ${
          ok === true ? "text-emerald-300" : ok === false ? "text-rose-300" : "text-white"
        }`}>{value}</div>
        {copyable && copy && (
          <button
            onClick={() => copy(value)}
            className="text-[var(--lattice-text-3)] hover:text-[var(--lattice-gold)] shrink-0"
            title="Copia"
          ><Copy size={11} /></button>
        )}
      </div>
    </div>
  );
}
