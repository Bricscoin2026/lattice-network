import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { X, Plus } from "lucide-react";

/**
 * LnsChipInput — chip-style multi-recipient picker for LNS identities.
 * Press Enter or comma to commit a chip. Backspace on empty input removes the last chip.
 *
 * Props:
 *  - value: string[]            (current chips)
 *  - onChange: (string[]) => void
 *  - identities: {lns_name}[]   (active LNS list, for the autocomplete datalist)
 *  - placeholder, testId, listId (one datalist id per instance)
 *  - exclude: string[]          (LNS to hide from suggestions, e.g. sender)
 */
export function LnsChipInput({ value, onChange, identities, placeholder, testId, listId, exclude = [] }) {
  const [draft, setDraft] = useState("");
  const inputRef = useRef(null);

  const commit = (raw) => {
    const v = (raw || "").trim().toLowerCase();
    if (!v) return;
    if (value.includes(v)) return;
    onChange([...value, v]);
    setDraft("");
  };

  const remove = (v) => onChange(value.filter((x) => x !== v));

  const onKeyDown = (e) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      commit(draft);
    } else if (e.key === "Backspace" && !draft && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  };

  const suggestions = (identities || []).filter(
    (i) => !value.includes(i.lns_name) && !exclude.includes(i.lns_name),
  );

  return (
    <div
      className="input-sovereign flex flex-wrap items-center gap-1.5 cursor-text min-h-[42px]"
      onClick={() => inputRef.current?.focus()}
      data-testid={testId}
      style={{ paddingTop: 6, paddingBottom: 6 }}
    >
      {value.map((v) => (
        <span
          key={v}
          className="inline-flex items-center gap-1.5 px-2 py-1 border bg-[rgba(212,175,55,0.08)] text-[var(--lattice-gold)] border-[var(--lattice-gold)]/40"
          style={{ fontSize: 11 }}
          data-testid={`${testId}-chip-${v}`}
        >
          <span>{v}</span>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); remove(v); }}
            className="text-[var(--lattice-gold)] hover:text-white"
            aria-label={`remove ${v}`}
          >
            <X size={11} />
          </button>
        </span>
      ))}
      <input
        ref={inputRef}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={onKeyDown}
        onBlur={() => draft && commit(draft)}
        placeholder={value.length === 0 ? placeholder : ""}
        list={listId}
        className="flex-1 bg-transparent border-0 outline-none font-mono-data text-[12px] text-white min-w-[120px] p-0"
      />
      {listId && (
        <datalist id={listId}>
          {suggestions.map((i) => <option key={i.lns_name} value={i.lns_name} />)}
        </datalist>
      )}
    </div>
  );
}

/**
 * LiveLnsCheck — debounced availability check used by the LNS register dialog.
 * Returns { available, reason, normalized, loading }
 */
export function useLiveLnsCheck(name) {
  const [state, setState] = useState({ available: null, reason: null, normalized: "", loading: false });
  useEffect(() => {
    const n = (name || "").trim().toLowerCase();
    if (!n) {
      setState({ available: null, reason: null, normalized: "", loading: false });
      return;
    }
    setState((s) => ({ ...s, loading: true }));
    const id = setTimeout(async () => {
      try {
        const r = await api.get("/lns/check", { params: { lns_name: n } });
        setState({
          available: !!r.data.available,
          reason: r.data.reason,
          normalized: r.data.normalized,
          loading: false,
        });
      } catch {
        setState({ available: null, reason: "network", normalized: n, loading: false });
      }
    }, 350);
    return () => clearTimeout(id);
  }, [name]);
  return state;
}

/**
 * DataResidencyBanner — shown at the top of Pulse + Certify pages to make
 * the sovereignty guarantee very visible to the customer.
 */
export function DataResidencyBanner({ variant = "pulse", testId = "data-residency-banner" }) {
  const lines = variant === "pulse"
    ? [
        "PQXDH(ML-KEM-768) + Double Ratchet · AES-256-GCM sealed-sender",
        "Routed through the Loopix 3-hop mixnet · ZK-RLN anti-bot gated",
        "Payload mai esce dal cluster on-premise · vendor zero-knowledge",
      ]
    : [
        "SHA3-512 hash of every outbound mail · ML-DSA-65 NotarySeal on-chain",
        "Body + allegati restano nello storage on-premise del tenant",
        "Il vendor (Lattice Sovereign Networks) NON detiene alcun payload",
      ];
  return (
    <div data-testid={testId} className="surface px-5 py-3 flex items-start gap-4 border-l-2" style={{ borderLeftColor: "var(--lattice-gold)" }}>
      <div className="w-1 self-stretch bg-[var(--lattice-gold)]/30" />
      <div className="flex-1">
        <div className="eyebrow text-[var(--lattice-gold)] mb-1.5">DATA RESIDENCY · QUANTUM-SECURE · ZERO-KNOWLEDGE</div>
        <ul className="font-mono-data text-[11px] text-[var(--lattice-text-2)] space-y-0.5 leading-relaxed">
          {lines.map((l, i) => <li key={i}>· {l}</li>)}
        </ul>
      </div>
    </div>
  );
}
