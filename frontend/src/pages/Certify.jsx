import { useEffect, useMemo, useRef, useState } from "react";
import { useLang } from "@/i18n/LangProvider";
import { api, fmtBytes, fmtNumber, fmtTime, fmtClock } from "@/lib/api";
import { PageHeader, SectionPanel, HashCell, EmptyRow, StatPanel } from "@/components/Primitives";
import { LnsChipInput, DataResidencyBanner } from "@/components/LatticePrimitives";
import { TID } from "@/constants/lattice-testids";
import { toast } from "sonner";
import { MailCheck, Hash, Clock, Database, Send, Inbox, FileText, Shield, X, Users, Search, Check, Lock, Mail, MailOpen, CheckCheck, ArrowRight, ArrowLeft, Trash2, Paperclip, Image as ImageIcon, BadgeCheck, ScrollText, Download } from "lucide-react";
import { AttachmentChip } from "@/components/AttachmentChip";
import { pqcSignMessage } from "@/lib/pqcAuth";
import VerifySignatureModal, { useVerify } from "@/components/VerifySignatureModal";
import { useRole } from "@/lib/useRole";
import { loadSession } from "@/lib/pqcAuth";

const CLASSES = ["INTERNAL", "CONFIDENTIAL", "RESTRICTED", "LEGAL-HOLD"];

/**
 * ContactBook — full address-book style picker.
 * Click any contact to toggle it in/out of the selection (single, multi or all).
 * Filter by name or department, group "Tutti / Inverti / Svuota" actions.
 */
function ContactBook({ open, identities, selected, exclude = [], onClose, onConfirm, title, testIdPrefix = "certify-book" }) {
  const [filter, setFilter] = useState("");
  const [tempSel, setTempSel] = useState(selected);

  useEffect(() => { if (open) setTempSel(selected); }, [open, selected]);

  if (!open) return null;

  const available = identities.filter((i) => !exclude.includes(i.lns_name));
  const visible = available.filter((i) =>
    !filter ||
    i.lns_name.toLowerCase().includes(filter.toLowerCase()) ||
    (i.department || "").toLowerCase().includes(filter.toLowerCase())
  );
  const toggle = (lns) =>
    setTempSel((prev) => prev.includes(lns) ? prev.filter((x) => x !== lns) : [...prev, lns]);

  const selectAll = () => setTempSel(available.map((i) => i.lns_name));
  const selectNone = () => setTempSel([]);
  const invert = () => {
    const visibleNames = visible.map((i) => i.lns_name);
    setTempSel((prev) => {
      const next = prev.filter((x) => !visibleNames.includes(x));
      visibleNames.forEach((n) => { if (!prev.includes(n)) next.push(n); });
      return next;
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-6" data-testid={`${testIdPrefix}-overlay`}>
      <div className="w-full max-w-2xl surface-elev relative max-h-[88vh] flex flex-col">
        <div className="absolute top-0 left-0 right-0 h-px gold-line" />
        <header className="flex items-start justify-between px-6 py-4 border-b hairline">
          <div>
            <div className="eyebrow">RUBRICA · LNS REGISTRY</div>
            <h3 className="font-display text-xl text-white mt-1">{title}</h3>
            <p className="text-[11px] text-[var(--lattice-text-3)] mt-1">
              Clicca per selezionare uno, alcuni o tutti i contatti.
            </p>
          </div>
          <button onClick={onClose} className="text-[var(--lattice-text-3)] hover:text-white" data-testid={`${testIdPrefix}-close`}><X size={18} /></button>
        </header>

        <div className="px-6 py-3 border-b hairline space-y-3">
          <div className="flex items-center gap-2 border hairline-strong px-3 py-2 surface">
            <Search size={13} className="text-[var(--lattice-gold)]" />
            <input
              autoFocus
              data-testid={`${testIdPrefix}-search`}
              className="flex-1 bg-transparent border-0 outline-none font-mono-data text-[12px] text-white"
              placeholder="Cerca per nome o dipartimento…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <button type="button" onClick={selectAll} data-testid={`${testIdPrefix}-all`}
              className="font-mono-data text-[10px] uppercase tracking-[0.2em] px-3 py-1 border border-[var(--lattice-gold)]/40 text-[var(--lattice-gold)] hover:bg-[var(--lattice-gold)]/10">
              Tutti ({available.length})
            </button>
            <button type="button" onClick={invert} data-testid={`${testIdPrefix}-invert`}
              className="font-mono-data text-[10px] uppercase tracking-[0.2em] px-3 py-1 border border-[var(--lattice-border-strong)] text-[var(--lattice-text-2)] hover:text-white hover:border-[var(--lattice-gold)]">
              Inverti vista
            </button>
            <button type="button" onClick={selectNone} data-testid={`${testIdPrefix}-none`}
              className="font-mono-data text-[10px] uppercase tracking-[0.2em] px-3 py-1 border border-[var(--lattice-border-strong)] text-[var(--lattice-text-3)] hover:text-red-300 hover:border-red-400">
              Svuota
            </button>
            <span className="ml-auto font-mono-data text-[10px] text-[var(--lattice-gold)]">
              {tempSel.length} selezionato{tempSel.length === 1 ? "" : "i"}
            </span>
          </div>
        </div>

        <div className="flex-1 overflow-auto" data-testid={`${testIdPrefix}-list`}>
          {visible.length === 0 && (
            <div className="px-6 py-10 text-center font-mono-data text-[11px] text-[var(--lattice-text-4)] uppercase tracking-wider">
              Nessun contatto corrisponde al filtro
            </div>
          )}
          {visible.map((i) => {
            const isSel = tempSel.includes(i.lns_name);
            return (
              <button
                key={i.lns_name}
                type="button"
                onClick={() => toggle(i.lns_name)}
                data-testid={`${testIdPrefix}-item-${i.lns_name}`}
                className={`w-full text-left px-5 py-3 border-b hairline flex items-center gap-3 transition-colors ${
                  isSel ? "bg-[rgba(212,175,55,0.08)]" : "hover:bg-[rgba(255,255,255,0.02)]"
                }`}
              >
                <span className={`w-4 h-4 border flex items-center justify-center shrink-0 ${
                  isSel ? "border-[var(--lattice-gold)] bg-[var(--lattice-gold)]" : "border-[var(--lattice-border-strong)]"
                }`}>
                  {isSel && <Check size={11} className="text-[var(--lattice-bg)]" strokeWidth={3} />}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="font-mono-data text-[12px] text-white truncate">{i.lns_name}</div>
                  <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] mt-0.5">
                    {i.department || "Operations"} · {(i.public_key_fingerprint || "").slice(0, 12)}…
                  </div>
                </div>
                {isSel && <span className="pill pill-gold" style={{ padding: "1px 6px", fontSize: 9 }}>SELECTED</span>}
              </button>
            );
          })}
        </div>

        <footer className="flex items-center justify-between gap-3 px-6 py-4 border-t hairline">
          <span className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">
            {available.length} contatti disponibili
          </span>
          <div className="flex items-center gap-2">
            <button className="btn-ghost" onClick={onClose} data-testid={`${testIdPrefix}-cancel`}>Annulla</button>
            <button
              className="btn-gold inline-flex items-center gap-2"
              onClick={() => { onConfirm(tempSel); onClose(); }}
              data-testid={`${testIdPrefix}-confirm`}
            >
              <Check size={13} /> Conferma ({tempSel.length})
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}

function Mailbox({ stats, mails, lang, t, onReply, currentLns, onOpenedMail, onDeleteMail, onRestoreMail, box, onChangeBox }) {
  const [open, setOpen] = useState(null);
  const [query, setQuery] = useState("");
  const filtered = mails.filter((m) => {
    if (!query) return true;
    return (
      (m.subject || m.subject_redacted || "").toLowerCase().includes(query.toLowerCase()) ||
      m.sender_lns.toLowerCase().includes(query.toLowerCase()) ||
      m.recipient_lns.toLowerCase().includes(query.toLowerCase())
    );
  });
  const inboxUnread = box === "inbox" && currentLns ? mails.filter((m) => m.recipient_lns === currentLns && !m.read_at).length : 0;

  const tabBtn = (key, label, Icon, count = 0) => (
    <button
      key={key}
      data-testid={`mailbox-tab-${key}`}
      onClick={() => onChangeBox?.(key)}
      className={`font-mono-data text-[11px] uppercase tracking-[0.15em] px-3 py-1.5 border transition-colors inline-flex items-center gap-1.5 ${
        box === key
          ? "bg-[var(--lattice-gold)] text-[var(--lattice-bg)] border-[var(--lattice-gold)]"
          : "bg-transparent text-[var(--lattice-text-3)] border-[var(--lattice-border-strong)] hover:text-white hover:border-[var(--lattice-gold)]"
      }`}
    >
      <Icon size={11} /> {label}{count > 0 && <span className="ml-1 px-1.5 bg-rose-500/30 text-rose-200 rounded-sm">{count}</span>}
    </button>
  );

  const openMail = (m) => {
    setOpen(m);
    // If I'm the recipient and not yet read → mark read & notify parent.
    if (currentLns && m.recipient_lns === currentLns && !m.read_at && box !== "trash") {
      onOpenedMail?.(m.mail_id, m);
    }
  };

  return (
    <>
      <div className="surface">
        <div className="px-5 py-3 border-b hairline flex items-center gap-3 flex-wrap">
          {currentLns && (
            <div className="flex items-center gap-2 flex-wrap">
              {tabBtn("inbox", "In arrivo", Inbox, inboxUnread)}
              {tabBtn("sent", "Inviate", Send)}
              {tabBtn("all", "Tutte", Mail)}
              {tabBtn("trash", "Eliminate", Trash2)}
            </div>
          )}
          <div className="flex items-center gap-2 flex-1 min-w-[280px] border hairline-strong px-3 py-1.5 surface-2">
            <Search size={13} className="text-[var(--lattice-gold)]" />
            <input
              data-testid="certify-mailbox-search"
              className="flex-1 bg-transparent border-0 outline-none font-mono-data text-[12px] text-white"
              placeholder="Cerca mittente, destinatario o oggetto…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-3 font-mono-data text-[10px] text-[var(--lattice-text-3)]">
            <span>{filtered.length} mail</span>
          </div>
        </div>
        <div className="max-h-[640px] overflow-auto" data-testid={TID.certifyMailsTable}>
          {filtered.length === 0 && (
            <div className="px-6 py-16 text-center font-mono-data text-[11px] text-[var(--lattice-text-4)] uppercase tracking-wider">
              {mails.length === 0 ? t.common.loading : "Nessuna mail in questa cartella"}
            </div>
          )}
          {filtered.map((m) => {
            const isMine = currentLns && m.sender_lns === currentLns;  // I am the sender
            const isReceived = currentLns && m.recipient_lns === currentLns;
            const isUnread = isReceived && !m.read_at;
            const EnvIcon = isUnread ? Mail : MailOpen;
            const rowClass = isUnread ? "bg-[rgba(212,175,55,0.04)]" : "";
            return (
              <div
                key={m.mail_id}
                data-testid={`certify-mail-row-${m.mail_id}`}
                className={`w-full px-5 py-3 border-b hairline flex items-center gap-4 hover:bg-[rgba(255,255,255,0.025)] transition-colors group ${rowClass}`}
              >
                <button
                  type="button"
                  onClick={() => openMail(m)}
                  className="flex-1 min-w-0 text-left flex items-center gap-4"
                >
                  <EnvIcon
                    size={16}
                    className={isUnread ? "text-[var(--lattice-gold)] shrink-0" : "text-[var(--lattice-text-3)] shrink-0"}
                    data-testid={isUnread ? "mail-icon-closed" : "mail-icon-open"}
                  />
                  <div className="min-w-0 flex-1 grid grid-cols-12 gap-3 items-center">
                    <div className="col-span-1 font-mono-data text-[9px] text-[var(--lattice-text-3)] uppercase tracking-wider">
                      {isMine ? <span className="text-[var(--lattice-gold)]">→ TO</span> : "← FROM"}
                    </div>
                    <div className={`col-span-3 font-mono-data text-[12px] truncate ${isUnread ? "text-white font-bold" : "text-[var(--lattice-text-2)]"}`}>
                      {isMine ? m.recipient_lns : m.sender_lns}
                    </div>
                    <div className="col-span-6 truncate">
                      <span className={`text-[13px] ${isUnread ? "text-white font-semibold" : "text-[var(--lattice-text-2)]"}`}>
                        {m.subject || "(senza oggetto)"}
                      </span>
                      {m.attachments && m.attachments.length > 0 && (
                        <span className="inline-flex items-center gap-1 ml-2 font-mono-data text-[10px] text-[var(--lattice-gold)]" title={`${m.attachments.length} allegati`}>
                          <Paperclip size={10} /> {m.attachments.length}
                        </span>
                      )}
                      {m.body && <span className="text-[12px] text-[var(--lattice-text-3)] ml-2">— {m.body.slice(0, 60)}{m.body.length > 60 ? "…" : ""}</span>}
                    </div>
                    <div className="col-span-2 flex items-center justify-end gap-2">
                      {isMine && m.delivery_receipt && (
                        <span className="inline-flex items-center gap-1 font-mono-data text-[9px] text-emerald-400" data-testid="mail-pec-receipt" title={`Ricevuta PEC firmata · block #${m.delivery_receipt.block_index}`}>
                          <BadgeCheck size={11} /> PEC
                        </span>
                      )}
                      {isMine && m.read_at && !m.delivery_receipt && (
                        <span className="inline-flex items-center gap-1 font-mono-data text-[9px] text-sky-400" data-testid="mail-read-receipt" title={`Letta · ${fmtClock(m.read_at, lang)}`}>
                          <CheckCheck size={11} /> letta
                        </span>
                      )}
                      {isMine && !m.read_at && (
                        <span className="inline-flex items-center gap-1 font-mono-data text-[9px] text-[var(--lattice-text-3)]" title="Consegnata, non ancora letta">
                          <Check size={11} /> consegn.
                        </span>
                      )}
                      <span className="font-mono-data text-[10px] text-[var(--lattice-text-3)] whitespace-nowrap">
                        {fmtClock(m.sealed_at, lang)}
                      </span>
                    </div>
                  </div>
                </button>
                {currentLns && (
                  box === "trash" ? (
                    <button
                      type="button"
                      data-testid={`mail-restore-${m.mail_id}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        onRestoreMail?.(m.mail_id);
                      }}
                      title="Ripristina nella casella"
                      className="text-[var(--lattice-gold)] hover:text-emerald-400 shrink-0 p-1 font-mono-data text-[10px] uppercase tracking-wider"
                    >
                      ↺ ripristina
                    </button>
                  ) : (
                    <button
                      type="button"
                      data-testid={`mail-delete-${m.mail_id}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        if (window.confirm("Eliminare questa mail dalla tua casella? La firma on-chain resta immutabile.")) {
                          onDeleteMail?.(m.mail_id);
                        }
                      }}
                      title="Elimina dalla mia casella"
                      className="opacity-0 group-hover:opacity-100 transition-opacity text-[var(--lattice-text-3)] hover:text-rose-400 shrink-0 p-1"
                    >
                      <Trash2 size={14} />
                    </button>
                  )
                )}
              </div>
            );
          })}
        </div>
      </div>
      {open && <MailViewer mail={open} lang={lang} currentLns={currentLns} onClose={() => setOpen(null)} onReply={(m) => { setOpen(null); onReply?.(m); }} />}
    </>
  );
}

// (removed ShieldCheck alias — using Shield directly)

function DeliveryTimeline({ mail, lang }) {
  const steps = [
    {
      key: "sent",
      label: "Inviata",
      sub: "Firmata e notarizzata",
      ts: mail.sealed_at,
      done: true,
      Icon: Send,
      tone: "gold",
    },
    {
      key: "delivered",
      label: "Consegnata",
      sub: "Sigillata nel mailbox del destinatario",
      ts: mail.sealed_at,
      done: true,
      Icon: Inbox,
      tone: "gold",
    },
    {
      key: "read",
      label: "Letta",
      sub: mail.read_at ? "Aperta dal destinatario" : "In attesa di apertura",
      ts: mail.read_at,
      done: !!mail.read_at,
      Icon: MailOpen,
      tone: mail.read_at ? "sky" : "muted",
    },
    {
      key: "pec",
      label: "PEC firmata",
      sub: mail.delivery_receipt ? `Block #${mail.delivery_receipt.block_index}` : "Ricevuta legale verificabile",
      ts: mail.delivery_receipt?.signed_at,
      done: !!mail.delivery_receipt,
      Icon: BadgeCheck,
      tone: mail.delivery_receipt ? "emerald" : "muted",
    },
  ];
  const toneColor = {
    gold: "text-[var(--lattice-gold)] border-[var(--lattice-gold)] bg-[rgba(212,175,55,0.08)]",
    sky: "text-sky-400 border-sky-400/60 bg-sky-400/8",
    emerald: "text-emerald-400 border-emerald-400/60 bg-emerald-400/8",
    muted: "text-[var(--lattice-text-4)] border-[var(--lattice-border-strong)] bg-transparent",
  };

  return (
    <div className="flex items-stretch gap-0">
      {steps.map((s, i) => {
        const cls = toneColor[s.tone];
        return (
          <div key={s.key} className="flex-1 relative flex flex-col items-center" data-testid={`timeline-step-${s.key}`}>
            {/* Connector line to next step */}
            {i < steps.length - 1 && (
              <div
                className={`absolute top-5 left-1/2 right-0 w-full h-px ${steps[i + 1].done ? "bg-[var(--lattice-gold)]" : "bg-[var(--lattice-border-strong)]"}`}
                style={{ transform: "translateX(0)" }}
              />
            )}
            <div className={`relative z-10 w-10 h-10 border-2 rounded-full flex items-center justify-center ${cls}`}>
              <s.Icon size={16} strokeWidth={2.5} />
            </div>
            <div className="text-center mt-2 px-1">
              <div className={`font-mono-data text-[10px] uppercase tracking-wider ${s.done ? "text-white" : "text-[var(--lattice-text-4)]"}`}>
                {s.label}
              </div>
              <div className="font-mono-data text-[9px] text-[var(--lattice-text-3)] mt-0.5 leading-tight">
                {s.sub}
              </div>
              {s.ts && (
                <div className="font-mono-data text-[9px] text-[var(--lattice-gold)] mt-0.5">
                  {fmtClock(s.ts, lang)}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}


function DownloadReceiptPdfButton({ mailId, blockIndex }) {
  const [busy, setBusy] = useState(false);
  const download = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const r = await api.get(`/certify/${mailId}/receipt.pdf`, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([r.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `lattice-pec-receipt-block-${blockIndex || mailId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success("PDF della ricevuta PEC scaricato");
    } catch (e) {
      toast.error("Download PDF fallito: " + (e?.response?.data?.detail || e.message));
    } finally {
      setBusy(false);
    }
  };
  return (
    <button
      type="button"
      onClick={download}
      disabled={busy}
      data-testid="download-pec-receipt-pdf"
      title="Scarica la ricevuta PEC come PDF (court-grade)"
      className="inline-flex items-center gap-1.5 px-2.5 py-1 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 hover:text-emerald-200 font-mono-data text-[10px] tracking-wider uppercase transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
    >
      <Download size={11} strokeWidth={2.4} />
      {busy ? "..." : "PDF"}
    </button>
  );
}


function MailViewer({ mail, lang, onClose, onReply, currentLns }) {
  const verifier = useVerify();
  const isSender = currentLns && mail.sender_lns === currentLns;
  const [decryptedBody, setDecryptedBody] = useState(null);
  const [decryptError, setDecryptError] = useState(null);

  useEffect(() => {
    if (!mail.is_e2e_encrypted) return;
    if (isSender) return; // sender stores its outbox in clear if it wants — server has only ciphertext
    const session = loadSession?.() || JSON.parse(sessionStorage.getItem("lattice.session") || "null");
    const sk = session?.enc_secret_key_hex;
    if (!sk) {
      setDecryptError("La tua keypair non contiene la chiave di cifratura X25519 — questa mail è E2E e non puoi leggerla.");
      return;
    }
    (async () => {
      try {
        const { decryptMailBody } = await import("@/lib/certifyE2E");
        const pt = await decryptMailBody(sk, mail.body, mail.body_e2e_envelope);
        setDecryptedBody(pt);
      } catch (e) {
        setDecryptError("Decifratura fallita: " + e.message);
      }
    })();
  }, [mail, isSender]);

  const renderedBody = mail.is_e2e_encrypted
    ? (decryptedBody ?? (decryptError || "[🔒 Mail end-to-end encrypted · decrypting…]"))
    : (mail.body || "[Body non disponibile per mail seedate — solo i nuovi invii Componi & Notarizza memorizzano il body]");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-6">
      <div data-testid="certify-mail-viewer" className="w-full max-w-3xl surface-elev relative max-h-[90vh] overflow-auto">
        <div className="absolute top-0 left-0 right-0 h-px gold-line" />
        <header className="flex items-start justify-between px-6 py-5 border-b hairline sticky top-0 surface-elev">
          <div className="min-w-0">
            <div className="eyebrow">CERTIFY · NOTARIZED MAIL</div>
            <h3 className="font-display text-2xl text-white mt-1 truncate">{mail.subject || mail.subject_redacted}</h3>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {onReply && (
              <button
                data-testid="certify-mail-reply-btn"
                onClick={() => onReply?.(mail)}
                className="btn-gold inline-flex items-center gap-2"
                style={{ padding: "6px 12px", fontSize: 11 }}
              >
                <Send size={12} /> Rispondi
              </button>
            )}
            <button onClick={onClose} className="text-[var(--lattice-text-3)] hover:text-white"><X size={18} /></button>
          </div>
        </header>
        <div className="px-6 py-5 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-[12px]">
            <div><div className="eyebrow mb-1">DA</div><div className="font-mono-data text-white">{mail.sender_lns}</div></div>
            <div><div className="eyebrow mb-1">A</div><div className="font-mono-data text-[var(--lattice-gold)]">{mail.recipient_lns}</div></div>
            <div><div className="eyebrow mb-1">DATA</div><div className="font-mono-data text-[var(--lattice-text-2)]">{fmtTime(mail.sealed_at, lang)}</div></div>
            <div><div className="eyebrow mb-1">CLASSIFICAZIONE</div><span className="pill pill-gold">{mail.classification || "INTERNAL"}</span></div>
          </div>
          {/* Sender-only timeline: inviata → consegnata → letta → PEC firmata */}
          {isSender && (
            <div className="border-t hairline pt-4" data-testid="mail-viewer-timeline">
              <div className="eyebrow mb-3 flex items-center gap-2">
                <CheckCheck size={11} className="text-[var(--lattice-gold)]" /> STATO CONSEGNA
              </div>
              <DeliveryTimeline mail={mail} lang={lang} />
            </div>
          )}
          <div className="border-t hairline pt-4">
            <div className="eyebrow mb-2 flex items-center gap-2">
              CORPO MESSAGGIO
              {mail.is_e2e_encrypted && (
                <span className="pill pill-online flex items-center gap-1" data-testid="mail-viewer-e2e-badge">
                  <Lock size={9} /> E2E
                </span>
              )}
            </div>
            <pre className="font-mono-data text-[12px] text-white whitespace-pre-wrap leading-relaxed bg-[#070d18] p-4 border hairline">{renderedBody}</pre>
          </div>
          {mail.attachments && mail.attachments.length > 0 && (
            <div className="border-t hairline pt-4" data-testid="mail-viewer-attachments">
              <div className="eyebrow mb-2">ALLEGATI · {mail.attachments.length}</div>
              <div className="space-y-2">
                {mail.attachments.map((att) => (
                  <AttachmentChip key={att.attachment_id} att={att} dark />
                ))}
              </div>
            </div>
          )}
          {mail.delivery_receipt && (
            <div className="border-t hairline pt-4" data-testid="mail-viewer-pec-receipt">
              <div className="eyebrow mb-2 flex items-center justify-between gap-2">
                <span className="flex items-center gap-2">
                  <ScrollText size={11} className="text-emerald-400" /> RICEVUTA DI CONSEGNA PEC · ON-CHAIN
                </span>
                <DownloadReceiptPdfButton mailId={mail.mail_id} blockIndex={mail.delivery_receipt.block_index} />
              </div>
              <div className="border border-emerald-500/30 bg-emerald-500/5 px-4 py-3 space-y-2">
                <div className="flex items-center gap-2 text-emerald-200">
                  <BadgeCheck size={14} />
                  <span className="text-[13px] font-bold">Mail letta e firmata dal destinatario</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 font-mono-data text-[10px]">
                  <div>
                    <div className="text-[var(--lattice-text-3)] uppercase">Firmata da</div>
                    <div className="text-[var(--lattice-gold)] mt-0.5">{mail.delivery_receipt.signed_by}</div>
                  </div>
                  <div>
                    <div className="text-[var(--lattice-text-3)] uppercase">Data firma</div>
                    <div className="text-white mt-0.5">{fmtTime(mail.delivery_receipt.signed_at, lang)}</div>
                  </div>
                  <div>
                    <div className="text-[var(--lattice-text-3)] uppercase">TX on-chain</div>
                    <div className="text-white mt-0.5 break-all">{mail.delivery_receipt.tx_id}</div>
                  </div>
                  <div>
                    <div className="text-[var(--lattice-text-3)] uppercase">Block</div>
                    <div className="text-white mt-0.5">#{mail.delivery_receipt.block_index}</div>
                  </div>
                  <div className="md:col-span-2">
                    <div className="text-[var(--lattice-text-3)] uppercase">SHA3-512 del payload firmato</div>
                    <div className="text-[var(--lattice-text-2)] mt-0.5 break-all">{(mail.delivery_receipt.canonical_preimage_sha3_512 || "").slice(0, 96)}…</div>
                  </div>
                  <div className="md:col-span-2">
                    <div className="text-[var(--lattice-text-3)] uppercase">Firma ML-DSA-65 (3309 byte)</div>
                    <div className="text-[var(--lattice-text-2)] mt-0.5 break-all">{(mail.delivery_receipt.signature_hex || "").slice(0, 96)}…</div>
                  </div>
                </div>
                <p className="font-mono-data text-[10px] text-emerald-200/80 mt-2 leading-relaxed">
                  Questa ricevuta è una garanzia crittografica del recapito: il destinatario ha firmato l&apos;apertura con la sua chiave segreta ML-DSA-65 e la firma è notarizzata sulla blockchain QBFT.
                  Riproducibile da chiunque verificando la firma con la public key on-chain (Block #{mail.delivery_receipt.block_index}). Per uso legale dove la legge richiede la PEC, vedi il disclaimer sopra.
                </p>
              </div>
            </div>
          )}
          <div className="border-t hairline pt-4 grid grid-cols-1 md:grid-cols-3 gap-3 text-[11px]">
            <div><div className="eyebrow mb-1">HASH SHA3-512</div><div className="font-mono-data text-[var(--lattice-gold)] break-all" data-testid="mail-detail-doc-hash">{mail.doc_hash}</div></div>
            {mail.tx_id && <div><div className="eyebrow mb-1">TX</div><div className="font-mono-data text-white break-all" data-testid="mail-detail-tx-id">{mail.tx_id}</div></div>}
            {mail.block_index && <div><div className="eyebrow mb-1">BLOCCO</div><div className="font-mono-data text-[var(--lattice-gold)]">#{mail.block_index}</div></div>}
          </div>
          {mail.tx_id && (
            <div className="border hairline px-3 py-2 mt-3 flex items-center justify-between gap-3 text-[11px]">
              <div className="font-mono-data text-[var(--lattice-text-3)]">
                Verifica firma BFT on-chain · indipendente, senza login
              </div>
              <a
                href={`/api/ledger/verify/${mail.tx_id}`}
                target="_blank"
                rel="noreferrer"
                data-testid="mail-detail-verify-link-raw"
                className="font-mono-data text-[10px] uppercase tracking-wider text-[var(--lattice-text-3)] hover:text-white"
              >
                JSON raw ↗
              </a>
              <a
                href={`/explorer/tx/${mail.tx_id}`}
                target="_blank"
                rel="noreferrer"
                data-testid="mail-detail-explorer-link"
                className="font-mono-data text-[10px] uppercase tracking-wider text-[var(--lattice-gold)] hover:underline"
              >
                Explorer ↗
              </a>
              <button
                type="button"
                onClick={() => verifier.open(mail.tx_id, `Certify · ${mail.subject || mail.subject_redacted || "mail"} · #${mail.block_index}`)}
                data-testid="mail-detail-verify-link"
                className="px-3 py-1.5 border border-[var(--lattice-gold)] text-[var(--lattice-gold)] font-mono-data text-[11px] uppercase tracking-wider hover:bg-[rgba(212,175,55,0.08)] inline-flex items-center gap-1.5"
              >
                <Shield size={11} /> Verifica firma
              </button>
            </div>
          )}
        </div>
      </div>
      <VerifySignatureModal {...verifier.props} />
    </div>
  );
}

function Compose({ identities, t, onSent, prefill, onConsumePrefill, lockedFrom }) {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState([]);
  const [cc, setCc] = useState([]);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [cls, setCls] = useState("INTERNAL");
  const [busy, setBusy] = useState(false);
  const [receipt, setReceipt] = useState(null);
  const [bookOpen, setBookOpen] = useState(null); // 'to' | 'cc' | null

  useEffect(() => {
    // Lock the sender to the authenticated user when present (Marco
    // can only send AS Marco). Fallback to the legacy selector when
    // there's no session.
    if (lockedFrom) {
      setFrom(lockedFrom);
    } else if (identities.length && !from) {
      setFrom(identities[0].lns_name);
    }
  }, [identities, from, lockedFrom]);

  // Apply a reply prefill once when the parent provides one.
  useEffect(() => {
    if (!prefill) return;
    if (prefill.from) setFrom(prefill.from);
    if (prefill.to) setTo(prefill.to);
    if (prefill.cc) setCc(prefill.cc);
    if (prefill.subject !== undefined) setSubject(prefill.subject);
    if (prefill.body !== undefined) setBody(prefill.body);
    if (prefill.classification) setCls(prefill.classification);
    setReceipt(null);
    onConsumePrefill?.();
  }, [prefill, onConsumePrefill]);

  const [pendingFiles, setPendingFiles] = useState([]);
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

  const canSend = from && to.length > 0 && subject.trim() && body.trim() && !busy;

  const submit = async () => {
    setBusy(true);
    try {
      // Attempt E2E encryption: only if there's exactly ONE primary
      // recipient AND that recipient has published an X25519 enc key.
      // Otherwise fall back to server-side at-rest encryption.
      let bodyToSend = body;
      let bodyE2E = null;
      const primaryRecipient = to[0];
      const hasSingleRecipient = to.length === 1 && (!cc || cc.length === 0);
      if (hasSingleRecipient) {
        try {
          const ek = await api.get(`/lns/${encodeURIComponent(primaryRecipient)}/enc-key`);
          const { encryptMailBody } = await import("@/lib/certifyE2E");
          const enc = await encryptMailBody(ek.data.enc_public_key_hex, body);
          bodyToSend = enc.body_ciphertext_b64;
          bodyE2E = enc.envelope;
        } catch (_e) {
          // Recipient has no enc key (legacy account) → fall through to at-rest only.
        }
      }
      const r = await api.post("/certify/send", {
        sender_lns: from,
        recipients_lns: to,
        cc_lns: cc,
        subject,
        body: bodyToSend,
        classification: cls,
        attachment_ids: pendingFiles.map((f) => f.attachment_id),
        body_e2e_envelope: bodyE2E,
      });
      const suffix = bodyE2E ? " · 🔒 E2E" : "";
      toast.success(`${t.certify.compose.success} ${r.data.tx_id.slice(0, 16)}…${suffix} · fanout ${r.data.fanout}`);
      setReceipt(r.data);
      setSubject("");
      setBody("");
      setCc([]);
      setPendingFiles([]);
      onSent?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || t.certify.compose.failure);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="surface">
        <header className="px-6 py-4 border-b hairline flex items-center justify-between">
          <div>
            <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] uppercase tracking-wider">Nuovo messaggio</div>
            <h2 className="font-display text-2xl text-white mt-1">{t.certify.compose.title}</h2>
          </div>
          <span className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">
            <Shield size={11} className="inline -mt-0.5 mr-1 text-[var(--lattice-gold)]" />
            firmato + notarizzato on-chain
          </span>
        </header>
        <div className="px-6 py-5 space-y-4">
          {/* From */}
          <div className="flex items-center gap-3 border-b hairline pb-3">
            <span className="font-mono-data text-[10px] text-[var(--lattice-text-3)] uppercase tracking-wider w-16 shrink-0">Da</span>
            {lockedFrom ? (
              <span data-testid="certify-compose-from-locked" className="flex-1 font-mono-data text-[13px] text-[var(--lattice-gold)]">{from}</span>
            ) : (
              <select
                data-testid={TID.certifyComposeFrom}
                className="flex-1 bg-transparent border-0 outline-none font-mono-data text-[13px] text-white"
                value={from}
                onChange={(e) => setFrom(e.target.value)}
              >
                {identities.map((i) => (
                  <option key={i.lns_name} value={i.lns_name} style={{ background: "#0a1020" }}>
                    {i.lns_name}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* To */}
          <div className="flex items-start gap-3 border-b hairline pb-3">
            <span className="font-mono-data text-[10px] text-[var(--lattice-text-3)] uppercase tracking-wider w-16 shrink-0 mt-2">A</span>
            <div className="flex-1 min-w-0">
              <LnsChipInput
                value={to}
                onChange={setTo}
                identities={identities}
                exclude={from ? [from] : []}
                placeholder="destinatario.azienda.lns"
                testId={TID.certifyComposeTo}
                listId="certify-to-list"
              />
            </div>
            <button
              type="button"
              data-testid="certify-to-open-book"
              onClick={() => setBookOpen("to")}
              className="font-mono-data text-[10px] text-[var(--lattice-gold)] hover:underline shrink-0 mt-2 inline-flex items-center gap-1"
            >
              <Users size={11} /> Rubrica
            </button>
          </div>

          {/* CC */}
          <div className="flex items-start gap-3 border-b hairline pb-3">
            <span className="font-mono-data text-[10px] text-[var(--lattice-text-3)] uppercase tracking-wider w-16 shrink-0 mt-2">Cc</span>
            <div className="flex-1 min-w-0">
              <LnsChipInput
                value={cc}
                onChange={setCc}
                identities={identities}
                exclude={[...(from ? [from] : []), ...to]}
                placeholder="opzionale"
                testId={TID.certifyComposeCc}
                listId="certify-cc-list"
              />
            </div>
            <button
              type="button"
              data-testid="certify-cc-open-book"
              onClick={() => setBookOpen("cc")}
              className="font-mono-data text-[10px] text-[var(--lattice-gold)] hover:underline shrink-0 mt-2 inline-flex items-center gap-1"
            >
              <Users size={11} /> Rubrica
            </button>
          </div>

          {/* Subject */}
          <div className="flex items-center gap-3 border-b hairline pb-3">
            <span className="font-mono-data text-[10px] text-[var(--lattice-text-3)] uppercase tracking-wider w-16 shrink-0">Oggetto</span>
            <input
              data-testid={TID.certifyComposeSubject}
              className="flex-1 bg-transparent border-0 outline-none text-[14px] text-white"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Oggetto del messaggio"
            />
            <select
              data-testid={TID.certifyComposeClass}
              className="bg-transparent border border-[var(--lattice-border-strong)] px-2 py-1 font-mono-data text-[10px] text-[var(--lattice-text-2)]"
              value={cls}
              onChange={(e) => setCls(e.target.value)}
            >
              {CLASSES.map((c) => (
                <option key={c} value={c} style={{ background: "#0a1020" }}>{c}</option>
              ))}
            </select>
          </div>

          {/* Body */}
          <textarea
            data-testid={TID.certifyComposeBody}
            className="w-full bg-transparent border-0 outline-none text-[14px] text-white leading-relaxed resize-none"
            rows={12}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Scrivi il tuo messaggio…"
          />

          {/* Attachments preview */}
          {pendingFiles.length > 0 && (
            <div className="space-y-1 pt-2 border-t hairline" data-testid="certify-pending-attachments">
              <div className="eyebrow mb-1">Allegati ({pendingFiles.length})</div>
              {pendingFiles.map((f, idx) => (
                <div key={f.attachment_id} className="surface-2 border hairline px-3 py-2 flex items-center gap-2">
                  {f.mime?.startsWith("image/") ? <ImageIcon size={14} className="text-[var(--lattice-gold)]" /> : <FileText size={14} className="text-[var(--lattice-gold)]" />}
                  <span className="font-mono-data text-[12px] text-white flex-1 truncate">{f.filename}</span>
                  <span className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">{(f.size / 1024).toFixed(1)} kB</span>
                  <button onClick={() => setPendingFiles((p) => p.filter((_, i) => i !== idx))} className="text-rose-400 hover:text-rose-300" data-testid={`certify-remove-att-${idx}`}>
                    <X size={13} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Action bar */}
          <div className="flex items-center justify-between pt-3 border-t hairline">
            <div className="flex items-center gap-2">
              <input
                ref={fileInputRef}
                type="file"
                multiple
                className="hidden"
                onChange={(e) => handleFilePick(Array.from(e.target.files || []))}
                data-testid="certify-file-input"
              />
              <button
                type="button"
                data-testid="certify-attach-btn"
                onClick={() => fileInputRef.current?.click()}
                title="Allega file (PDF, Word, Excel, immagini…)"
                className="border hairline-strong px-3 py-2 hover:border-[var(--lattice-gold)] hover:text-[var(--lattice-gold)] text-[var(--lattice-text-2)] transition-colors inline-flex items-center gap-2"
                disabled={busy}
              >
                <Paperclip size={13} /> Allega
              </button>
              <button
                data-testid={TID.certifyComposeSend}
                className="btn-gold inline-flex items-center gap-2"
                onClick={submit}
                disabled={!canSend}
              >
                <Send size={13} />
                {busy ? "Notarizzo…" : "Invia"}
              </button>
            </div>
            <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">
              {to.length} destinatari{cc.length ? ` · ${cc.length} CC` : ""}
              {pendingFiles.length > 0 && <span> · {pendingFiles.length} allegati</span>}
            </div>
          </div>

          {/* Inline success banner (replaces sidebar receipt) */}
          {receipt && (
            <div data-testid={TID.certifyReceipt} className="border hairline-strong px-4 py-3 surface-2 mt-3">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-2">
                  <Shield size={14} className="text-[var(--lattice-gold)]" />
                  <span className="font-mono-data text-[11px] text-white">Messaggio inviato e notarizzato</span>
                </div>
                <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">
                  blocco <span className="text-[var(--lattice-gold)]">#{receipt.block_index}</span>
                  {" · "}fanout <span className="text-[var(--lattice-gold)]">{receipt.fanout}</span>
                </div>
              </div>
              <details className="mt-2">
                <summary className="font-mono-data text-[10px] text-[var(--lattice-text-4)] cursor-pointer hover:text-[var(--lattice-gold)]">
                  ℹ︎ dettagli tecnici (hash · tx · timestamp)
                </summary>
                <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-2 font-mono-data text-[10px]">
                  <div><span className="text-[var(--lattice-text-3)]">hash:</span> <span className="text-[var(--lattice-gold)] break-all">{receipt.doc_hash}</span></div>
                  <div><span className="text-[var(--lattice-text-3)]">tx:</span> <span className="text-white break-all">{receipt.tx_id}</span></div>
                  <div><span className="text-[var(--lattice-text-3)]">mail id:</span> <span className="text-[var(--lattice-text-2)] break-all">{receipt.mail_id}</span></div>
                  <div><span className="text-[var(--lattice-text-3)]">sealed at:</span> <span className="text-[var(--lattice-text-2)]">{receipt.sealed_at}</span></div>
                </div>
              </details>
            </div>
          )}
        </div>
      </div>

      <ContactBook
        open={bookOpen === "to"}
        identities={identities}
        selected={to}
        exclude={from ? [from] : []}
        onClose={() => setBookOpen(null)}
        onConfirm={(sel) => setTo(sel)}
        title="Destinatari (A)"
        testIdPrefix="certify-book-to"
      />
      <ContactBook
        open={bookOpen === "cc"}
        identities={identities}
        selected={cc}
        exclude={[...(from ? [from] : []), ...to]}
        onClose={() => setBookOpen(null)}
        onConfirm={(sel) => setCc(sel)}
        title="Copia conoscenza (Cc)"
        testIdPrefix="certify-book-cc"
      />
    </div>
  );
}

export default function Certify() {
  const { t, lang } = useLang();
  const me = useRole();
  const authSession = loadSession();
  const myLns = authSession?.lns || me.lns || null;
  const [stats, setStats] = useState(null);
  const [mails, setMails] = useState([]);
  const [identities, setIdentities] = useState([]);
  const [tab, setTab] = useState("mailbox");
  const [box, setBox] = useState("all");  // all | inbox | sent | trash
  const [replyPrefill, setReplyPrefill] = useState(null);

  const load = async (currentBox = box) => {
    try {
      const [s, m, lns] = await Promise.all([
        api.get("/certify/stats"),
        api.get("/certify/recent", { params: { limit: 40, box: currentBox } }),
        api.get("/lns/active"),
      ]);
      setStats(s.data);
      setMails(m.data);
      setIdentities(lns.data);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    load(box);
    const id = setInterval(() => load(box), 9000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [box]);

  const handleReply = (mail) => {
    const replySubject = (mail.subject || "").startsWith("Re:")
      ? mail.subject
      : `Re: ${mail.subject || mail.subject_redacted || "(senza oggetto)"}`;
    const replyBody = `\n\n\n— Il ${fmtTime(mail.sealed_at, lang)} ${mail.sender_lns} ha scritto:\n> ${(mail.body || "[contenuto originale sigillato]").split("\n").join("\n> ")}`;
    setReplyPrefill({
      from: mail.recipient_lns,
      to: [mail.sender_lns],
      cc: [],
      subject: replySubject,
      body: replyBody,
      classification: mail.classification || "INTERNAL",
    });
    setTab("compose");
  };

  const tabBtn = (key, tid, Icon, label) => (
    <button
      data-testid={tid}
      onClick={() => setTab(key)}
      className={`font-mono-data text-[11px] uppercase tracking-[0.2em] px-4 py-2 border transition-colors inline-flex items-center gap-2 ${
        tab === key
          ? "bg-[var(--lattice-gold)] text-[var(--lattice-bg)] border-[var(--lattice-gold)]"
          : "bg-transparent text-[var(--lattice-text-3)] border-[var(--lattice-border-strong)] hover:text-white hover:border-[var(--lattice-gold)]"
      }`}
    >
      <Icon size={12} /> {label}
    </button>
  );

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={t.certify.eyebrow}
        title={t.certify.title}
        subtitle={t.certify.subtitle}
        right={
          <div className="flex items-center gap-2">
            {tabBtn("mailbox", TID.certifyTabMailbox, Inbox, t.certify.tabs.mailbox)}
            {me.permissions.can_send_certify && tabBtn("compose", TID.certifyTabCompose, Send, t.certify.tabs.compose)}
          </div>
        }
      />
      {!me.permissions.can_send_certify && (
        <div className="surface px-4 py-3 flex items-center gap-3" data-testid="certify-rbac-banner">
          <Shield size={14} className="text-sky-300" />
          <span className="font-mono-data text-[11px] text-white">Modalità {me.label}</span>
          <span className="font-mono-data text-[10px] text-[var(--lattice-text-3)]">— composizione disattivata · {me.role === "vendor" ? "subject & body redatti" : "body redatto"}</span>
        </div>
      )}
      <DataResidencyBanner variant="certify" testId="certify-residency-banner" />
      <div
        data-testid="certify-pec-disclaimer"
        className="surface px-4 py-3 border border-amber-500/30 bg-amber-500/5 flex items-start gap-3"
      >
        <Shield size={13} className="text-amber-300 mt-0.5 shrink-0" />
        <div className="font-mono-data text-[11px] text-[var(--lattice-text-2)] leading-relaxed">
          <strong className="text-amber-200">Certify ≠ PEC.</strong>{" "}
          Per notifiche giudiziarie, raccomandate digitali e comunicazioni con PA dove la legge italiana
          impone la PEC (art. 16 L. 53/1994, D.L. 76/2020) usa il tuo provider PEC certificato.
          Certify fornisce notarizzazione crittografica per comunicazioni B2B contrattuali e di compliance.
        </div>
      </div>
      {tab === "mailbox" || !me.permissions.can_send_certify ? (
        <Mailbox
          stats={stats}
          mails={mails}
          lang={lang}
          t={t}
          onReply={me.permissions.can_send_certify ? handleReply : undefined}
          currentLns={myLns}
          box={box}
          onChangeBox={setBox}
          onOpenedMail={async (mailId, mailObj) => {
            try {
              // Build the canonical payload that the chain will notarise as
              // a DeliveryReceipt and sign it locally with the recipient's sk.
              const canonical = [
                mailObj.mail_id,
                mailObj.sealed_at || "",
                mailObj.sender_lns || "",
                mailObj.recipient_lns || "",
                mailObj.doc_hash || "",
              ].join("|");
              const sig = pqcSignMessage(canonical);
              const body = sig ? { signature_hex: sig } : {};
              const r = await api.post(`/certify/${mailId}/read`, body);
              if (r.data?.delivery_receipt) {
                toast.success(`Ricevuta PEC notarizzata · block #${r.data.delivery_receipt.block_index}`);
              }
              load(box);
            } catch (e) { console.warn(e); }
          }}
          onDeleteMail={async (mailId) => {
            try {
              await api.delete(`/certify/${mailId}`);
              toast.success("Mail eliminata dalla tua casella");
              load(box);
            } catch (e) {
              toast.error(e?.response?.data?.detail || "Eliminazione fallita");
            }
          }}
          onRestoreMail={async (mailId) => {
            try {
              await api.post(`/certify/${mailId}/restore`);
              toast.success("Mail ripristinata");
              load(box);
            } catch (e) {
              toast.error(e?.response?.data?.detail || "Ripristino fallito");
            }
          }}
        />
      ) : (
        <Compose identities={identities} t={t} onSent={load} prefill={replyPrefill} onConsumePrefill={() => setReplyPrefill(null)} lockedFrom={myLns} />
      )}
    </div>
  );
}
