import { useEffect, useMemo, useRef, useState } from "react";
import { useLang } from "@/i18n/LangProvider";
import { api, fmtRelative, fmtTime, fmtClock } from "@/lib/api";
import { PageHeader, SectionPanel } from "@/components/Primitives";
import { TID } from "@/constants/lattice-testids";
import { toast } from "sonner";
import { Radio, Send, Shield, Plus, Lock, X, Hash, Route as RouteIcon, GaugeCircle, Fingerprint, Megaphone, Check, CheckCheck, Search, Paperclip, FileText, Image as ImageIcon, Download, FileX } from "lucide-react";
import { useRole } from "@/lib/useRole";
import { loadSession } from "@/lib/pqcAuth";
import { LnsChipInput, DataResidencyBanner } from "@/components/LatticePrimitives";
import VerifySignatureModal, { useVerify } from "@/components/VerifySignatureModal";
import { AttachmentChip } from "@/components/AttachmentChip";

function BroadcastDialog({ open, sender, identities, onClose, onBroadcasted }) {
  const { t } = useLang();
  const [recipients, setRecipients] = useState([]);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) { setRecipients([]); setBody(""); }
  }, [open]);

  if (!open) return null;

  const submit = async () => {
    const list = recipients.filter((r) => r !== sender);
    if (list.length === 0 || !body.trim()) return;
    setBusy(true);
    let ok = 0, fail = 0;
    for (const r of list) {
      try {
        await api.post("/pulse/send", { from_lns: sender, to_lns: r, plaintext: body });
        ok += 1;
      } catch (e) {
        fail += 1;
      }
    }
    if (ok > 0) toast.success(`Broadcast sealed-sender · ${ok} OK${fail ? ` · ${fail} fail` : ""}`);
    if (ok === 0) toast.error(`Broadcast failed · ${fail} errors`);
    setBusy(false);
    onBroadcasted?.();
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-6">
      <div data-testid={TID.pulseBroadcastDialog} className="w-full max-w-2xl surface-elev relative">
        <div className="absolute top-0 left-0 right-0 h-px gold-line" />
        <header className="flex items-start justify-between px-6 py-5 border-b hairline">
          <div>
            <div className="eyebrow">SEALED-SENDER · BROADCAST</div>
            <h3 className="font-display text-2xl text-white mt-1">Pulse Broadcast</h3>
          </div>
          <button onClick={onClose} className="text-[var(--lattice-text-3)] hover:text-white">
            <X size={18} />
          </button>
        </header>
        <div className="px-6 py-5 space-y-4">
          <p className="text-[12px] text-[var(--lattice-text-3)] leading-relaxed">
            Invio fan-out: una conversazione sealed-sender separata verso ogni destinatario. Ogni leg è cifrato col proprio session key PQXDH e instradato indipendentemente attraverso la mixnet Loopix.
          </p>
          <div>
            <label className="eyebrow block mb-2">Destinatari (multi)</label>
            <LnsChipInput
              value={recipients}
              onChange={setRecipients}
              identities={identities}
              exclude={sender ? [sender] : []}
              placeholder="es. legal.acme.lns · invio con Invio/virgola"
              testId={TID.pulseBroadcastInput}
              listId="pulse-broadcast-list"
            />
          </div>
          <div>
            <label className="eyebrow block mb-2">Messaggio</label>
            <textarea
              data-testid={TID.pulseBroadcastBody}
              className="input-sovereign"
              rows={5}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              style={{ fontFamily: "JetBrains Mono, monospace" }}
              placeholder="…"
            />
          </div>
          <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">
            Fan-out: <span className="text-[var(--lattice-gold)]">{recipients.length}</span> sealed-sender leg(s)
          </div>
        </div>
        <footer className="flex items-center justify-end gap-3 px-6 py-4 border-t hairline">
          <button className="btn-ghost" onClick={onClose} disabled={busy}>{t.common.cancel}</button>
          <button
            data-testid={TID.pulseBroadcastSend}
            className="btn-gold inline-flex items-center gap-2"
            onClick={submit}
            disabled={busy || recipients.length === 0 || !body.trim()}
          >
            <Megaphone size={13} /> {busy ? "…" : `Broadcast (${recipients.length})`}
          </button>
        </footer>
      </div>
    </div>
  );
}

function NewChatDialog({ open, identities, sender, onClose, onConfirm }) {
  const { t } = useLang();
  const [recipient, setRecipient] = useState("");
  const [q, setQ] = useState("");

  useEffect(() => {
    if (open) { setRecipient(""); setQ(""); }
  }, [open]);

  if (!open) return null;

  // Company directory = all active LNS in the same tenant, minus myself.
  // The backend already scopes /lns to the caller's tenant_id, so the
  // identities list here IS the company directory.
  const contacts = identities
    .filter((i) => i.lns_name !== sender)
    .filter((i) => !q || i.lns_name.toLowerCase().includes(q.toLowerCase()) || (i.department || "").toLowerCase().includes(q.toLowerCase()))
    .sort((a, b) => a.lns_name.localeCompare(b.lns_name));

  const submit = (lns) => {
    const r = (lns || recipient).trim().toLowerCase();
    if (!r) return;
    if (r === sender) {
      toast.error("Mittente e destinatario devono essere diversi");
      return;
    }
    onConfirm(r);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-6">
      <div data-testid={TID.pulseNewChatDialog} className="w-full max-w-xl surface-elev relative">
        <div className="absolute top-0 left-0 right-0 h-px gold-line" />
        <header className="flex items-start justify-between px-6 py-5 border-b hairline">
          <div>
            <div className="eyebrow">RUBRICA AZIENDALE · SEALED-SENDER</div>
            <h3 className="font-display text-2xl text-white mt-1">Nuova conversazione</h3>
            <p className="text-[12px] text-[var(--lattice-text-3)] mt-1">
              Puoi scrivere SOLO ai colleghi della tua azienda. La rubrica è generata dalla blockchain (LNS attivi del tuo tenant).
            </p>
          </div>
          <button onClick={onClose} className="text-[var(--lattice-text-3)] hover:text-white">
            <X size={18} />
          </button>
        </header>
        <div className="px-6 py-4 border-b hairline">
          <div className="flex items-center gap-2 border hairline-strong px-3 py-2 surface-2">
            <Search size={14} className="text-[var(--lattice-gold)]" />
            <input
              data-testid={TID.pulseNewChatRecipient}
              className="flex-1 bg-transparent border-0 outline-none font-mono-data text-[13px] text-white"
              placeholder="Cerca per nome o reparto…"
              value={q}
              onChange={(e) => { setQ(e.target.value); setRecipient(e.target.value); }}
              onKeyDown={(e) => e.key === "Enter" && contacts.length === 1 && submit(contacts[0].lns_name)}
              autoFocus
            />
          </div>
        </div>
        <div className="max-h-[420px] overflow-auto">
          {contacts.length === 0 && (
            <div className="px-6 py-12 text-center font-mono-data text-[11px] text-[var(--lattice-text-4)] uppercase tracking-wider">
              {identities.length === 0
                ? "Rubrica vuota — chiedi all'admin di registrare i tuoi colleghi"
                : "Nessun collega corrisponde alla ricerca"}
            </div>
          )}
          {contacts.map((c) => {
            const initials = c.lns_name.split(".").slice(0, 2).map((s) => s[0]?.toUpperCase()).join("");
            const isRevoked = c.status === "REVOKED";
            return (
              <button
                key={c.lns_name}
                type="button"
                data-testid={`pulse-contact-${c.lns_name}`}
                disabled={isRevoked}
                onClick={() => submit(c.lns_name)}
                className={`w-full text-left px-6 py-3 border-b hairline flex items-center gap-3 transition-colors ${
                  isRevoked
                    ? "opacity-40 cursor-not-allowed"
                    : "hover:bg-[rgba(212,175,55,0.06)] hover:border-l-2 hover:border-l-[var(--lattice-gold)]"
                }`}
              >
                <div className="w-10 h-10 border hairline bg-[rgba(212,175,55,0.08)] flex items-center justify-center font-display text-[13px] text-[var(--lattice-gold)] shrink-0">
                  {initials || "?"}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-mono-data text-[13px] text-white truncate">{c.lns_name}</div>
                  <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] uppercase tracking-wider">
                    {c.department || c.role || "membro"}
                    {isRevoked && <span className="text-rose-400 ml-2">· REVOCATO</span>}
                  </div>
                </div>
                {!isRevoked && (
                  <Send size={13} className="text-[var(--lattice-gold)] opacity-60 group-hover:opacity-100" />
                )}
              </button>
            );
          })}
        </div>
        <footer className="px-6 py-3 border-t hairline font-mono-data text-[10px] text-[var(--lattice-text-4)] uppercase tracking-wider">
          {contacts.length} contatti aziendali · click per avviare chat
        </footer>
      </div>
    </div>
  );
}

function CipherPreview({ hex }) {
  if (!hex) return null;
  return (
    <span title={hex} className="font-mono-data text-[10px] text-[var(--lattice-text-4)] tracking-wide">
      {hex.slice(0, 32)}…{hex.slice(-12)}
    </span>
  );
}

function MixnetRouteBar({ route, t }) {
  if (!route || !route.hops || route.hops.length === 0) return null;
  return (
    <div data-testid="pulse-mixnet-route" className="surface-2 px-4 py-3 border-b hairline">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
        <span className="eyebrow flex items-center gap-2">
          <RouteIcon size={11} /> {t.pulse.mixnetRoute}
        </span>
        <div className="flex items-center gap-3">
          <span className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">
            {t.pulse.mixnetTotalDelay}: <span className="text-[var(--lattice-gold)]">{route.total_delay_ms}ms</span>
          </span>
          <span className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">
            {t.pulse.mixnetCover}: {route.cover_traffic_rate_hz}Hz
          </span>
        </div>
      </div>
      <div className="flex items-center gap-2 overflow-x-auto">
        {route.hops.map((h, idx) => (
          <div key={h.relay_node_id} className="flex items-center gap-2 shrink-0">
            <div className="border hairline-strong px-3 py-1.5 surface flex items-center gap-2">
              <span className="font-mono-data text-[9px] text-[var(--lattice-gold)]">L{h.layer}</span>
              <div className="leading-tight">
                <div className="font-mono-data text-[11px] text-white">{h.relay_label}</div>
                <div className="font-mono-data text-[9px] text-[var(--lattice-text-4)]">{h.relay_region} · {h.delay_ms}ms</div>
              </div>
            </div>
            {idx < route.hops.length - 1 && (
              <span className="font-mono-data text-[var(--lattice-gold)] text-[10px]">▶</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Pulse() {
  const { t, lang } = useLang();
  const me = useRole();
  const authSession = loadSession();  // PQC login session (localStorage)
  const myLns = authSession?.lns || me.lns || null;
  const canSendPulse = me.permissions?.can_send_pulse ?? true;
  const canSeePlaintext = me.permissions?.can_read_plaintext ?? true;
  const [identities, setIdentities] = useState([]);
  const [sender, setSender] = useState("");
  const [conversations, setConversations] = useState([]);
  const [selectedConv, setSelectedConv] = useState(null);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [newChatOpen, setNewChatOpen] = useState(false);
  const [broadcastOpen, setBroadcastOpen] = useState(false);
  // iteration_5 additions
  const [session, setSession] = useState(null);
  const [route, setRoute] = useState(null);
  const [rlnQuota, setRlnQuota] = useState(null);
  const [showTech, setShowTech] = useState(false);
  const verifier = useVerify();
  const msgEndRef = useRef(null);
  const msgsContainerRef = useRef(null);
  const prevMsgLenRef = useRef(0);

  useEffect(() => {
    // Always load the LNS directory (so the "Nuova chat" dialog can suggest
    // recipients within the tenant).
    api.get("/lns/active").then((r) => {
      setIdentities(r.data);
      if (!myLns && r.data.length && !sender) setSender(r.data[0].lns_name);
    }).catch(console.error);
    // If we have a real authenticated session, lock the sender to the
    // logged-in user — never let an employee impersonate someone else.
    if (myLns) setSender(myLns);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [myLns]);

  const loadConversations = async () => {
    if (!sender) return;
    try {
      const r = await api.get("/pulse/conversations", { params: { lns: sender, limit: 100 } });
      setConversations(r.data);
      if (!selectedConv && r.data.length) setSelectedConv(r.data[0]);
    } catch (e) {
      console.error(e);
    }
  };

  const loadRlnQuota = async () => {
    if (!sender) return;
    try {
      const r = await api.get("/rln/quota", { params: { lns: sender } });
      setRlnQuota(r.data);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    if (!sender) return;
    setSelectedConv(null);
    setMessages([]);
    setSession(null);
    setRoute(null);
    loadConversations();
    loadRlnQuota();
    const id = setInterval(() => { loadConversations(); loadRlnQuota(); }, 4000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sender]);

  useEffect(() => {
    if (!selectedConv) {
      setSession(null);
      return;
    }
    let cancel = false;
    const load = async () => {
      try {
        const [m, s] = await Promise.all([
          api.get("/pulse/messages", { params: { conv_id: selectedConv.conv_id, limit: 400 } }),
          api.get(`/pulse/session/${selectedConv.conv_id}`).catch(() => ({ data: null })),
        ]);
        if (!cancel) {
          setMessages(m.data);
          setSession(s.data);
        }
      } catch (e) {
        console.error(e);
      }
    };
    load();
    const id = setInterval(load, 3000);
    return () => {
      cancel = true;
      clearInterval(id);
    };
  }, [selectedConv]);

  useEffect(() => {
    // Scroll only the inner messages container, NEVER the page.
    // Only auto-scroll when the message count actually grew (avoids
    // jumping on every 3s poll re-render).
    if (messages.length > prevMsgLenRef.current && msgsContainerRef.current) {
      msgsContainerRef.current.scrollTop = msgsContainerRef.current.scrollHeight;
    }
    prevMsgLenRef.current = messages.length;
  }, [messages.length]);

  const startConversation = async (recipient) => {
    try {
      const r = await api.post("/pulse/send", {
        from_lns: sender,
        to_lns: recipient,
        plaintext: "[SESSION_OPENED]",
      });
      toast.success("Conversazione avviata · PQXDH OK");
      setRoute({
        route_id: r.data.route_id,
        hops: r.data.route_hops,
        total_delay_ms: r.data.route_hops.reduce((a, h) => a + h.delay_ms, 0),
        cover_traffic_rate_hz: 1.5,
      });
      setRlnQuota((q) => q ? { ...q, used: r.data.rln_slot_used } : q);
      await loadConversations();
      setSelectedConv({
        conv_id: r.data.conv_id,
        participants: [sender, recipient].sort(),
        message_count: 1,
        last_message_at: r.data.sealed_at,
        last_anchor_tx: r.data.anchor_tx_id,
        last_anchor_block: r.data.anchor_block_index,
      });
    } catch (e) {
      if (e?.response?.status === 429) toast.error(t.pulse.rlnLimit);
      else toast.error(e?.response?.data?.detail || "Avvio conversazione fallito");
    }
  };

  const [pendingFiles, setPendingFiles] = useState([]);  // attachments queued for next message
  const fileInputRef = useRef(null);

  const handleFilePick = async (files) => {
    if (!files || files.length === 0) return;
    setBusy(true);
    try {
      for (const f of files) {
        const fd = new FormData();
        fd.append("file", f);
        const r = await api.post("/attachments/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
        setPendingFiles((prev) => [...prev, r.data]);
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Upload fallito");
    } finally {
      setBusy(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const sendMessage = async () => {
    if ((!draft.trim() && pendingFiles.length === 0) || !selectedConv || !sender) return;
    const other = selectedConv.participants.find((p) => p !== sender) || selectedConv.participants[0];
    // Compute a simulated RLN proof on the client (the real one would
    // come from the Groth16 prover in `lattice-zk-rln`).
    let rlnProof = null;
    if (rlnQuota && rlnQuota.nullifier_seed) {
      rlnProof = {
        nullifier: rlnQuota.nullifier_seed.toLowerCase(),
        epoch: rlnQuota.epoch,
        signal_hash: "client-computed",
        proof_bytes: "0x" + "0".repeat(192),
      };
    }
    setBusy(true);
    try {
      const r = await api.post("/pulse/send", {
        from_lns: sender,
        to_lns: other,
        plaintext: draft,
        rln_proof: rlnProof,
        attachment_ids: pendingFiles.map((f) => f.attachment_id),
      });
      setDraft("");
      setPendingFiles([]);
      setRoute({
        route_id: r.data.route_id,
        hops: r.data.route_hops,
        total_delay_ms: r.data.route_hops.reduce((a, h) => a + h.delay_ms, 0),
        cover_traffic_rate_hz: 1.5,
      });
      setRlnQuota((q) => q ? { ...q, used: r.data.rln_slot_used } : q);
      if (r.data.anchor_tx_id) {
        toast.success(`Ancoraggio on-chain · TX ${r.data.anchor_tx_id.slice(0, 16)}…`);
      }
      const m = await api.get("/pulse/messages", { params: { conv_id: selectedConv.conv_id, limit: 400 } });
      setMessages(m.data);
      await loadConversations();
      // Update session right away from the send response
      setSession({
        conv_id: r.data.conv_id,
        participants: selectedConv.participants,
        fingerprint: r.data.session_fingerprint,
        epoch: r.data.epoch,
        message_number: r.data.message_number,
        root_key_fingerprint: "",
        started_at: r.data.sealed_at,
        cipher_suite: "PQXDH(ML-KEM-768) + Double-Ratchet · AEAD: AES-256-GCM",
      });
    } catch (e) {
      if (e?.response?.status === 429) toast.error(t.pulse.rlnLimit);
      else toast.error(e?.response?.data?.detail || "Invio non riuscito");
    } finally {
      setBusy(false);
    }
  };

  const counterpart = (conv) =>
    sender ? conv.participants.find((p) => p !== sender) || conv.participants[0] : conv.participants[0];

  const selectedCounterpart = useMemo(
    () => (selectedConv ? counterpart(selectedConv) : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [selectedConv, sender]
  );

  const rlnPct = rlnQuota ? Math.min(100, Math.round((rlnQuota.used / rlnQuota.max_per_epoch) * 100)) : 0;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={t.pulse.eyebrow}
        title={t.pulse.title}
        subtitle={t.pulse.subtitle}
        right={
          <div className="flex items-center gap-3 flex-wrap">
            {!myLns ? (
              <div>
                <div className="eyebrow mb-1">{t.pulse.pickSender}</div>
                <select
                  data-testid={TID.pulseSenderSelect}
                  className="input-sovereign"
                  value={sender}
                  onChange={(e) => setSender(e.target.value)}
                  style={{ minWidth: 280 }}
                >
                  {identities.length === 0 && <option>{t.pulse.pickSenderPlaceholder}</option>}
                  {identities.map((i) => (
                    <option key={i.lns_name} value={i.lns_name} style={{ background: "#0a1020" }}>
                      {i.lns_name}
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              <div className="surface-2 border hairline px-3 py-2" data-testid="pulse-my-identity">
                <div className="eyebrow text-[9px] mb-0.5">Stai usando</div>
                <div className="font-mono-data text-[12px] text-[var(--lattice-gold)]">{myLns}</div>
              </div>
            )}
            {canSendPulse && (
              <button
                data-testid={TID.pulseNewChatBtn}
                className="btn-gold inline-flex items-center gap-2 self-end"
                disabled={!sender}
                onClick={() => setNewChatOpen(true)}
              >
                <Plus size={13} /> {t.pulse.newChat}
              </button>
            )}
            {canSendPulse && (
              <button
                data-testid={TID.pulseBroadcastBtn}
                className="btn-ghost inline-flex items-center gap-2 self-end"
                disabled={!sender}
                onClick={() => setBroadcastOpen(true)}
              >
                <Megaphone size={13} /> Broadcast
              </button>
            )}
          </div>
        }
      />

      {showTech && <DataResidencyBanner variant="pulse" testId="pulse-residency-banner" />}

      {/* RLN quota strip — only when admin opens technical details */}
      {showTech && rlnQuota && (
        <div data-testid="pulse-rln-strip" className="surface px-5 py-3 flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <GaugeCircle size={14} className="text-[var(--lattice-gold)]" />
            <span className="eyebrow">{t.pulse.rlnSlot}</span>
          </div>
          <div className="flex items-center gap-2 min-w-[280px] flex-1">
            <div className="h-1.5 flex-1 bg-[#0a1020] border border-[var(--lattice-border)] relative overflow-hidden">
              <div
                style={{
                  width: `${rlnPct}%`,
                  background: rlnPct > 80 ? "#ef4444" : rlnPct > 50 ? "#f59e0b" : "var(--lattice-gold)",
                  height: "100%",
                  transition: "width .3s ease",
                }}
              />
            </div>
            <span className="font-mono-data text-[11px] text-white">
              {rlnQuota.used}/{rlnQuota.max_per_epoch}
            </span>
          </div>
          <span className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">
            epoch <span className="text-[var(--lattice-gold)]">{rlnQuota.epoch}</span> · {rlnQuota.epoch_seconds}s
          </span>
          <span className="font-mono-data text-[10px] text-[var(--lattice-text-4)]">
            {t.pulse.rlnNullifier}: {rlnQuota.nullifier_seed.slice(0, 16)}…
          </span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4" style={{ minHeight: 600 }}>
        <div className="lg:col-span-4 xl:col-span-3 surface flex flex-col" data-testid={TID.pulseConvList}>
          <header className="px-4 py-3 border-b hairline flex items-center justify-between">
            <span className="eyebrow">CONVERSAZIONI · {conversations.length}</span>
            <Radio size={12} className="text-[var(--lattice-gold)]" />
          </header>
          <div className="flex-1 overflow-auto">
            {conversations.length === 0 && (
              <div className="px-4 py-10 text-center">
                <Lock className="mx-auto text-[var(--lattice-text-4)]" size={20} strokeWidth={1.2} />
                <div className="mt-3 font-mono-data text-[11px] text-[var(--lattice-text-4)] tracking-wider uppercase">{t.pulse.noConv}</div>
              </div>
            )}
            {conversations.map((c) => {
              const isSel = selectedConv?.conv_id === c.conv_id;
              const other = counterpart(c);
              return (
                <button
                  key={c.conv_id}
                  data-testid={TID.pulseConvItem(c.conv_id)}
                  onClick={() => setSelectedConv(c)}
                  className={`w-full text-left px-4 py-3 border-l-2 border-b hairline transition-colors ${
                    isSel
                      ? "border-l-[var(--lattice-gold)] bg-[rgba(212,175,55,0.06)]"
                      : "border-l-transparent hover:bg-[rgba(255,255,255,0.02)]"
                  }`}
                >
                  <div className="font-mono-data text-[12px] text-white truncate">{other}</div>
                  <div className="flex items-center justify-between mt-1">
                    <span className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">
                      {c.message_count} {t.pulse.msgCount}
                    </span>
                    {c.last_message_at && (
                      <span className="font-mono-data text-[10px] text-[var(--lattice-text-4)]">
                        {fmtRelative(c.last_message_at, lang)}
                      </span>
                    )}
                  </div>
                  {c.last_anchor_tx && (
                    <div className="mt-1 inline-flex items-center gap-1.5">
                      <span className="pill pill-gold" style={{ padding: "1px 6px", fontSize: 9 }}>
                        <Hash size={9} /> #{c.last_anchor_block}
                      </span>
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        <div className="lg:col-span-8 xl:col-span-9 surface flex flex-col" style={{ minHeight: 600 }}>
          {!selectedConv ? (
            <div className="flex-1 flex items-center justify-center px-6 py-16 text-center">
              <div>
                <Shield className="mx-auto text-[var(--lattice-text-4)]" size={32} strokeWidth={1.2} />
                <div className="mt-4 font-display text-2xl text-white">{t.pulse.pickConv}</div>
                <div className="mt-1 text-[12px] text-[var(--lattice-text-3)]">{t.pulse.pickConvSub}</div>
              </div>
            </div>
          ) : (
            <>
              <header className="px-5 py-3 border-b hairline">
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <div className="min-w-0">
                    <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] tracking-wider uppercase">Chat con</div>
                    <div className="font-display text-xl text-white mt-0.5 truncate">{selectedCounterpart}</div>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono-data text-[10px] text-[var(--lattice-text-3)]" data-testid="pulse-admin-view-badge" title="L'admin del tenant vede il testo dei messaggi">
                      <Shield size={10} className="inline -mt-0.5 mr-1 text-[var(--lattice-gold)]" />
                      vista admin
                    </span>
                    <span className="font-mono-data text-[10px] text-[var(--lattice-text-4)]">·</span>
                    <span className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">
                      {selectedConv.message_count} msg
                    </span>
                    <button
                      onClick={() => setShowTech((v) => !v)}
                      className="font-mono-data text-[10px] text-[var(--lattice-text-3)] hover:text-[var(--lattice-gold)] underline-offset-2 hover:underline"
                      data-testid="pulse-toggle-tech"
                    >
                      {showTech ? "nascondi dettagli tecnici" : "ℹ︎ dettagli tecnici"}
                    </button>
                  </div>
                </div>
                {showTech && session && (
                  <div data-testid="pulse-session-strip" className="mt-3 flex items-center gap-4 flex-wrap font-mono-data text-[10px]">
                    <span className="flex items-center gap-1.5">
                      <Fingerprint size={11} className="text-[var(--lattice-gold)]" />
                      <span className="text-[var(--lattice-text-3)]">{t.pulse.fingerprint}:</span>
                      <span className="text-[var(--lattice-gold)]">{session.fingerprint}</span>
                    </span>
                    <span className="text-[var(--lattice-text-3)]">
                      {t.pulse.epoch} <span className="text-white">{session.epoch}</span> · msg# <span className="text-white">{session.message_number}</span>
                    </span>
                    {selectedConv.last_anchor_tx && (
                      <span className="pill pill-gold inline-flex items-center gap-1.5">
                        <Hash size={11} /> #{selectedConv.last_anchor_block}
                      </span>
                    )}
                  </div>
                )}
              </header>

              {showTech && <MixnetRouteBar route={route} t={t} />}

              <div data-testid={TID.pulseMessages} ref={msgsContainerRef} className="flex-1 overflow-auto px-5 py-5 space-y-3 bg-[#080d18]">
                {messages.length === 0 && (
                  <div className="text-center font-mono-data text-[11px] text-[var(--lattice-text-4)] tracking-wider uppercase py-10">
                    {t.common.loading}
                  </div>
                )}
                {messages.map((m) => {
                  const mine = m.from_lns === sender;
                  const text = m.plaintext
                    ? m.plaintext
                    : (canSeePlaintext
                        ? "(messaggio sigillato — solo cifrato disponibile)"
                        : "[testo nascosto dal ruolo attivo]");
                  return (
                    <div key={m.msg_id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
                      <div
                        className={`max-w-[78%] px-4 py-2.5 rounded-2xl ${
                          mine
                            ? "bg-[var(--lattice-gold)] text-[#0a1020] rounded-br-sm"
                            : "bg-[#1a2540] text-white rounded-bl-sm"
                        }`}
                      >
                        <div className="text-[14px] leading-snug whitespace-pre-wrap break-words">{text}</div>
                        {m.attachments && m.attachments.length > 0 && (
                          <div className="mt-2 space-y-1" data-testid={`msg-attachments-${m.msg_id}`}>
                            {m.attachments.map((att) => (
                              <AttachmentChip key={att.attachment_id} att={att} mine={mine} />
                            ))}
                          </div>
                        )}
                        <div className={`flex items-center justify-end gap-1.5 mt-1 font-mono-data text-[10px] ${
                          mine ? "text-[#0a1020]/70" : "text-[var(--lattice-text-4)]"
                        }`}>
                          {m.anchor_tx_id && <Hash size={9} className="opacity-80" />}
                          <span className="whitespace-nowrap">{fmtClock(m.sealed_at, lang)}</span>
                          {mine && (
                            m.read_at ? (
                              <CheckCheck size={14} strokeWidth={2.5} className="text-[#1e88e5]" data-testid="msg-status-read" title={`letto · ${fmtClock(m.read_at, lang)}`} />
                            ) : m.delivered_at ? (
                              <CheckCheck size={14} strokeWidth={2.5} className="text-[#0a1020]/50" data-testid="msg-status-delivered" title={`consegnato · ${fmtClock(m.delivered_at, lang)}`} />
                            ) : (
                              <Check size={14} strokeWidth={2.5} className="text-[#0a1020]/50" data-testid="msg-status-sent" title="inviato" />
                            )
                          )}
                        </div>
                        {/* iter_27: always-visible on-chain hash chip with verify link */}
                        <div className={`mt-1.5 flex items-center gap-1.5 text-[9px] font-mono-data ${mine ? "text-[#0a1020]/70" : "text-[var(--lattice-text-4)]"}`}>
                          <Hash size={9} className="opacity-60" />
                          <span data-testid={`msg-hash-${m.message_id || m.ciphertext_hex.slice(0,8)}`}>{m.ciphertext_hex.slice(0, 14)}…</span>
                          {m.anchor_tx_id && (
                            <>
                              <button
                                type="button"
                                onClick={() => verifier.open(m.anchor_tx_id, `Pulse · messaggio in ${selectedConv?.conv_id?.slice(0, 12) || "?"}`)}
                                data-testid={`msg-verify-${m.anchor_tx_id.slice(0,10)}`}
                                className={`underline-offset-2 hover:underline ${mine ? "text-[#0a1020]" : "text-[var(--lattice-gold)]"}`}
                                title="Verifica firma BFT on-chain"
                              >verifica TX {m.anchor_tx_id.slice(0, 10)}…</button>
                              <a
                                href={`/explorer/tx/${m.anchor_tx_id}`}
                                target="_blank"
                                rel="noreferrer"
                                data-testid={`msg-explorer-${m.anchor_tx_id.slice(0,10)}`}
                                className={`underline-offset-2 hover:underline ${mine ? "text-[#0a1020]" : "text-[var(--lattice-gold)]"}`}
                                title="Apri nel Public Explorer"
                              >↗</a>
                            </>
                          )}
                        </div>
                        {showTech && (
                          <div className={`mt-2 pt-2 border-t font-mono-data text-[9px] ${
                            mine ? "border-[#0a1020]/30 text-[#0a1020]/70" : "border-[var(--lattice-border-strong)] text-[var(--lattice-text-4)]"
                          }`}>
                            <div>nonce {m.nonce_hex.slice(0, 12)}…</div>
                            <div>ct {m.ciphertext_hex.slice(0, 24)}…</div>
                            {m.anchor_tx_id && <div>anchor {m.anchor_tx_id.slice(0, 20)}…</div>}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
                <div ref={msgEndRef} />
              </div>

              {canSendPulse ? (
                <footer className="border-t hairline">
                  {pendingFiles.length > 0 && (
                    <div className="px-5 pt-3 flex flex-wrap gap-2" data-testid="pulse-pending-attachments">
                      {pendingFiles.map((f, idx) => (
                        <div key={f.attachment_id} className="surface-2 border hairline px-2 py-1 flex items-center gap-2 max-w-[240px]">
                          {f.mime?.startsWith("image/") ? <ImageIcon size={12} className="text-[var(--lattice-gold)] shrink-0" /> : <FileText size={12} className="text-[var(--lattice-gold)] shrink-0" />}
                          <span className="font-mono-data text-[10px] text-white truncate flex-1">{f.filename}</span>
                          <span className="font-mono-data text-[9px] text-[var(--lattice-text-3)] shrink-0">{(f.size / 1024).toFixed(1)}kB</span>
                          <button onClick={() => setPendingFiles((p) => p.filter((_, i) => i !== idx))} className="text-rose-400 hover:text-rose-300 shrink-0" data-testid={`pulse-remove-att-${idx}`}>
                            <X size={11} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="px-5 py-3 flex items-center gap-2">
                    <input
                      ref={fileInputRef}
                      type="file"
                      multiple
                      className="hidden"
                      onChange={(e) => handleFilePick(Array.from(e.target.files || []))}
                      data-testid="pulse-file-input"
                    />
                    <button
                      type="button"
                      data-testid="pulse-attach-btn"
                      onClick={() => fileInputRef.current?.click()}
                      title="Allega file (PDF, Word, immagini…)"
                      className="border hairline-strong px-3 py-2 hover:border-[var(--lattice-gold)] hover:text-[var(--lattice-gold)] text-[var(--lattice-text-2)] transition-colors"
                      disabled={busy}
                    >
                      <Paperclip size={14} />
                    </button>
                    <input
                      data-testid={TID.pulseInput}
                      className="input-sovereign flex-1"
                      placeholder={t.pulse.placeholder}
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), sendMessage())}
                    />
                    <button
                      data-testid={TID.pulseSendBtn}
                      className="btn-gold inline-flex items-center gap-2"
                      onClick={sendMessage}
                      disabled={busy || (!draft.trim() && pendingFiles.length === 0)}
                    >
                      <Send size={13} /> {t.pulse.sendCta}
                    </button>
                  </div>
                </footer>
              ) : (
                <footer className="px-5 py-3 border-t hairline flex items-center gap-2" data-testid="pulse-rbac-footer">
                  <Shield size={13} className="text-sky-300" />
                  <span className="font-mono-data text-[11px] text-white">Modalità {me.label}</span>
                  <span className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">— invio disattivato · solo lettura</span>
                </footer>
              )}
            </>
          )}
        </div>
      </div>

      <NewChatDialog
        open={newChatOpen}
        identities={identities}
        sender={sender}
        onClose={() => setNewChatOpen(false)}
        onConfirm={startConversation}
      />

      <BroadcastDialog
        open={broadcastOpen}
        sender={sender}
        identities={identities}
        onClose={() => setBroadcastOpen(false)}
        onBroadcasted={() => loadConversations()}
      />
      <VerifySignatureModal {...verifier.props} />
    </div>
  );
}
