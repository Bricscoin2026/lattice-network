import { useEffect, useMemo, useState } from "react";
import { useLang } from "@/i18n/LangProvider";
import { api, fmtTime } from "@/lib/api";
import { PageHeader, SectionPanel, EmptyRow, HashCell } from "@/components/Primitives";
import { TID } from "@/constants/lattice-testids";
import { toast } from "sonner";
import { Search, ShieldOff, UserPlus, X, IdCard as IdCardIcon, Fingerprint, KeyRound } from "lucide-react";
import { useLiveLnsCheck } from "@/components/LatticePrimitives";

const DEPARTMENTS = ["Executive", "Finance", "Legal", "R&D", "Operations", "Compliance", "Security", "HR"];

function RevokeDialog({ open, lnsRecord, onClose, onConfirmed }) {
  const { t } = useLang();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) setReason("");
  }, [open]);

  if (!open || !lnsRecord) return null;

  const submit = async () => {
    setBusy(true);
    try {
      const r = await api.post("/lns/revoke", {
        lns_name: lnsRecord.lns_name,
        reason: reason || "Administrative revocation",
        admin: "console.admin",
      });
      toast.success(`${t.lns.revoke.success} ${r.data.tx_id.slice(0, 16)}…`);
      onConfirmed?.(r.data);
      onClose();
    } catch (e) {
      const msg = e?.response?.data?.detail || t.lns.revoke.failure;
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-6">
      <div data-testid={TID.lnsRevokeDialog} className="w-full max-w-xl surface-elev relative">
        <div className="absolute top-0 left-0 right-0 h-px gold-line" />
        <header className="flex items-start justify-between px-6 py-5 border-b hairline">
          <div>
            <div className="eyebrow">SOVEREIGN REVOCATION</div>
            <h3 className="font-display text-2xl text-white mt-1">{t.lns.revoke.title}</h3>
          </div>
          <button onClick={onClose} className="text-[var(--lattice-text-3)] hover:text-white">
            <X size={18} />
          </button>
        </header>
        <div className="px-6 py-5 space-y-5">
          <p className="text-[13px] text-[var(--lattice-text-3)] leading-relaxed">{t.lns.revoke.body}</p>
          <div className="surface-2 px-4 py-3">
            <div className="eyebrow text-[10px]">LNS</div>
            <div className="font-mono-data text-[14px] text-[var(--lattice-gold)] mt-1">{lnsRecord.lns_name}</div>
            <div className="mt-3 eyebrow text-[10px]">DID</div>
            <div className="font-mono-data text-[11px] text-[var(--lattice-text-2)] mt-1 break-all">{lnsRecord.did}</div>
          </div>
          <div>
            <label className="eyebrow block mb-2">{t.lns.revoke.reasonLabel}</label>
            <textarea
              data-testid={TID.lnsRevokeReason}
              className="input-sovereign"
              rows={3}
              placeholder={t.lns.revoke.reasonPlaceholder}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
        </div>
        <footer className="flex items-center justify-end gap-3 px-6 py-4 border-t hairline">
          <button data-testid={TID.lnsRevokeCancel} className="btn-ghost" onClick={onClose} disabled={busy}>
            {t.common.cancel}
          </button>
          <button data-testid={TID.lnsRevokeConfirm} className="btn-danger" onClick={submit} disabled={busy}>
            <span className="inline-flex items-center gap-2">
              <ShieldOff size={14} />
              {busy ? "…" : t.lns.revoke.cta}
            </span>
          </button>
        </footer>
      </div>
    </div>
  );
}

export default function Lns() {
  const { t, lang } = useLang();
  const [records, setRecords] = useState([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("ALL");
  const [target, setTarget] = useState(null);
  const [registerOpen, setRegisterOpen] = useState(false);
  const [passport, setPassport] = useState(null);

  const load = async () => {
    try {
      const params = { limit: 500 };
      if (status !== "ALL") params.status = status;
      if (q.trim()) params.q = q.trim();
      const r = await api.get("/lns", { params });
      setRecords(r.data);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  useEffect(() => {
    const id = setTimeout(load, 250);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const filterBtn = (val, tid, label) => (
    <button
      data-testid={tid}
      onClick={() => setStatus(val)}
      className={`font-mono-data text-[10px] uppercase tracking-[0.2em] px-3 py-1.5 border transition-colors ${
        status === val
          ? "bg-[var(--lattice-gold)] text-[var(--lattice-bg)] border-[var(--lattice-gold)]"
          : "bg-transparent text-[var(--lattice-text-3)] border-[var(--lattice-border-strong)] hover:text-white hover:border-[var(--lattice-gold)]"
      }`}
    >
      {label}
    </button>
  );

  const stats = useMemo(() => {
    const active = records.filter((r) => r.status === "ACTIVE").length;
    return { active, revoked: records.length - active };
  }, [records]);

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={t.lns.eyebrow}
        title={t.lns.title}
        subtitle={t.lns.subtitle}
        right={
          <button
            data-testid={TID.lnsRegisterOpenBtn}
            onClick={() => setRegisterOpen(true)}
            className="btn-gold inline-flex items-center gap-2"
          >
            <UserPlus size={13} />
            {t.lns.register.cta}
          </button>
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="surface p-5">
          <div className="eyebrow">{t.common.active}</div>
          <div className="mt-3 font-display text-4xl text-white">{stats.active}</div>
        </div>
        <div className="surface p-5">
          <div className="eyebrow">{t.common.revoked}</div>
          <div className="mt-3 font-display text-4xl text-[var(--lattice-gold)]">{stats.revoked}</div>
        </div>
        <div className="surface p-5">
          <div className="eyebrow">IDENTITÀ AZIENDALI · CONTROLLATE</div>
          <div className="mt-3 font-mono-data text-[12px] text-[var(--lattice-text-2)] leading-relaxed">
            Ogni dipendente, fornitore o consulente ha un'identità emessa dalla tua azienda. Revocabile in un click. Verificabile pubblicamente.
          </div>
        </div>
      </div>

      <SectionPanel
        title={t.lns.title}
        eyebrow={t.home.panels.lnsSub}
        testId={TID.lnsTable}
        right={
          <div className="flex items-center gap-2 flex-wrap">
            {filterBtn("ALL", TID.lnsFilterAll, t.common.all)}
            {filterBtn("ACTIVE", TID.lnsFilterActive, t.common.active)}
            {filterBtn("REVOKED", TID.lnsFilterRevoked, t.common.revoked)}
          </div>
        }
      >
        <div className="px-5 py-3 border-b hairline flex items-center gap-3 surface-2">
          <Search size={14} className="text-[var(--lattice-gold)]" />
          <input
            data-testid={TID.lnsSearchInput}
            className="input-sovereign border-0 bg-transparent p-0 focus:border-transparent"
            placeholder={t.lns.searchPlaceholder}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            style={{ fontSize: 13 }}
          />
        </div>
        <div className="overflow-x-auto max-h-[640px]">
          <table className="lattice-table">
            <thead>
              <tr>
                <th>{t.lns.columns.name}</th>
                <th>{t.lns.columns.did}</th>
                <th>{t.lns.columns.fp}</th>
                <th>{t.lns.columns.dept}</th>
                <th>Ruolo</th>
                <th>{t.lns.columns.registered}</th>
                <th>{t.lns.columns.status}</th>
                <th className="text-right">{t.lns.columns.actions}</th>
              </tr>
            </thead>
            <tbody>
              {records.length === 0 && <EmptyRow colSpan={8} text={t.common.empty} />}
              {records.map((r) => (
                <tr
                  key={r.did}
                  data-testid={TID.lnsRowBtn(r.lns_name)}
                  onClick={() => setPassport(r)}
                  className="cursor-pointer"
                >
                  <td className="font-mono-data text-[13px] text-white">{r.lns_name}</td>
                  <td><HashCell value={r.did} /></td>
                  <td className="font-mono-data text-[11px] text-[var(--lattice-text-3)]">{r.public_key_fingerprint.slice(0, 16)}…</td>
                  <td className="font-mono-data text-[12px]">{r.department}</td>
                  <td>
                    <span className={`pill ${
                      r.role === "admin" ? "pill-gold" :
                      r.role === "auditor" ? "pill-online" :
                      r.role === "vendor" ? "pill-offline" : "pill-slate"
                    }`} data-testid={`lns-role-${r.lns_name}`}>
                      {(r.role || "operator").toUpperCase()}
                    </span>
                  </td>
                  <td className="font-mono-data text-[11px] text-[var(--lattice-text-3)]">{fmtTime(r.registered_at, lang)}</td>
                  <td>
                    <span className={`pill ${r.status === "ACTIVE" ? "pill-online" : "pill-offline"}`}>
                      <span className={`dot ${r.status === "ACTIVE" ? "dot-online" : "dot-offline"}`} />
                      {r.status}
                    </span>
                  </td>
                  <td className="text-right">
                    <button
                      data-testid={TID.lnsRevokeBtn(r.lns_name)}
                      disabled={r.status === "REVOKED"}
                      onClick={(e) => { e.stopPropagation(); setTarget(r); }}
                      className={`font-mono-data text-[10px] uppercase tracking-[0.2em] px-3 py-1.5 border transition-colors inline-flex items-center gap-1.5 ${
                        r.status === "REVOKED"
                          ? "border-[var(--lattice-border)] text-[var(--lattice-text-4)] cursor-not-allowed"
                          : "border-red-500/50 text-red-300 hover:bg-red-500/10 hover:border-red-400"
                      }`}
                    >
                      <ShieldOff size={11} />
                      {t.lns.revoke.cta}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionPanel>

      <RevokeDialog
        open={!!target}
        lnsRecord={target}
        onClose={() => setTarget(null)}
        onConfirmed={() => load()}
      />

      <RegisterDialog
        open={registerOpen}
        onClose={() => setRegisterOpen(false)}
        onConfirmed={() => load()}
      />

      <PassportDialog
        record={passport}
        onClose={() => setPassport(null)}
      />
    </div>
  );
}

function PassportDialog({ record, onClose }) {
  const { t, lang } = useLang();
  if (!record) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-6">
      <div data-testid={TID.lnsPassportDialog} className="w-full max-w-2xl surface-elev relative">
        <div className="absolute top-0 left-0 right-0 h-px gold-line" />
        <header className="flex items-start justify-between px-6 py-5 border-b hairline">
          <div>
            <div className="eyebrow">SOVEREIGN PASSPORT</div>
            <h3 className="font-display text-3xl text-white mt-1">{record.lns_name}</h3>
          </div>
          <button data-testid={TID.lnsPassportClose} onClick={onClose} className="text-[var(--lattice-text-3)] hover:text-white">
            <X size={18} />
          </button>
        </header>

        <div className="px-6 py-5">
          {/* Passport pipeline LNS → DID → SIL */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
            <div className="border hairline-strong surface-2 p-4">
              <div className="flex items-center gap-2 mb-2">
                <IdCardIcon size={14} className="text-[var(--lattice-gold)]" />
                <span className="eyebrow">LNS · Human</span>
              </div>
              <div className="font-mono-data text-[13px] text-white break-all">{record.lns_name}</div>
            </div>
            <div className="border hairline-strong surface-2 p-4">
              <div className="flex items-center gap-2 mb-2">
                <Fingerprint size={14} className="text-[var(--lattice-gold)]" />
                <span className="eyebrow">DID · Machine</span>
              </div>
              <div className="font-mono-data text-[11px] text-[var(--lattice-text-2)] break-all">{record.did}</div>
            </div>
            <div className="border hairline-strong surface-2 p-4">
              <div className="flex items-center gap-2 mb-2">
                <KeyRound size={14} className="text-[var(--lattice-gold)]" />
                <span className="eyebrow">SIL · ML-DSA-65</span>
              </div>
              <div className="font-mono-data text-[11px] text-[var(--lattice-gold)] break-all">
                {record.public_key_fingerprint}
              </div>
            </div>
          </div>

          {/* Arrows row between cards on wider screens */}
          <div className="hidden md:flex items-center justify-center gap-4 -mt-4 mb-4 text-[var(--lattice-gold)] font-mono-data text-[11px] tracking-widest">
            <span style={{ width: "30%" }} className="flex justify-center">▶</span>
            <span style={{ width: "30%" }} className="flex justify-center">▶</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <div className="eyebrow mb-1">Dipartimento</div>
              <div className="font-mono-data text-[13px] text-white">{record.department}</div>
            </div>
            <div>
              <div className="eyebrow mb-1">Stato</div>
              <span className={`pill ${record.status === "ACTIVE" ? "pill-online" : "pill-offline"}`}>
                <span className={`dot ${record.status === "ACTIVE" ? "dot-online" : "dot-offline"}`} />
                {record.status}
              </span>
            </div>
            <div>
              <div className="eyebrow mb-1">Registrato</div>
              <div className="font-mono-data text-[12px] text-[var(--lattice-text-2)]">
                {new Date(record.registered_at).toLocaleString(lang === "it" ? "it-IT" : "en-GB")}
              </div>
            </div>
            {record.revoked_at && (
              <div>
                <div className="eyebrow mb-1">Revocato</div>
                <div className="font-mono-data text-[12px] text-red-300">
                  {new Date(record.revoked_at).toLocaleString(lang === "it" ? "it-IT" : "en-GB")}
                </div>
              </div>
            )}
          </div>

          <div className="mt-6 pt-5 border-t hairline">
            <div className="eyebrow mb-2">CRYPTO STACK</div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 font-mono-data text-[11px] text-[var(--lattice-text-2)]">
              <div>NIST FIPS 204 · ML-DSA-65 (sig)</div>
              <div>NIST FIPS 203 · ML-KEM-768 (KEM)</div>
              <div>NIST FIPS 202 · SHA3-512</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function RegisterDialog({ open, onClose, onConfirmed }) {
  const { t } = useLang();
  const [name, setName] = useState("");
  const [dept, setDept] = useState("Operations");
  const [role, setRole] = useState("operator");
  const [tenants, setTenants] = useState([]);
  const [tenantId, setTenantId] = useState("");
  const [busy, setBusy] = useState(false);
  const check = useLiveLnsCheck(name);

  useEffect(() => {
    if (open) {
      setName("");
      setDept("Operations");
      setRole("operator");
      setTenantId("");
      api.get("/tenants").then((r) => setTenants(r.data)).catch(() => setTenants([]));
    }
  }, [open]);

  if (!open) return null;

  const submit = async () => {
    setBusy(true);
    try {
      const r = await api.post("/lns/register", {
        lns_name: name.trim().toLowerCase(),
        department: dept,
        admin: "console.admin",
        role,
        tenant_id: tenantId || null,
      });
      toast.success(`${t.lns.register.success} ${r.data.tx_id.slice(0, 16)}… · ruolo ${r.data.role}`);
      onConfirmed?.(r.data);
      onClose();
    } catch (e) {
      const msg = e?.response?.data?.detail || t.lns.register.failure;
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-6">
      <div data-testid={TID.lnsRegisterDialog} className="w-full max-w-xl surface-elev relative">
        <div className="absolute top-0 left-0 right-0 h-px gold-line" />
        <header className="flex items-start justify-between px-6 py-5 border-b hairline">
          <div>
            <div className="eyebrow">SOVEREIGN ENROLLMENT</div>
            <h3 className="font-display text-2xl text-white mt-1">{t.lns.register.title}</h3>
          </div>
          <button onClick={onClose} className="text-[var(--lattice-text-3)] hover:text-white">
            <X size={18} />
          </button>
        </header>
        <div className="px-6 py-5 space-y-5">
          <p className="text-[13px] text-[var(--lattice-text-3)] leading-relaxed">{t.lns.register.body}</p>
          <div>
            <label className="eyebrow block mb-2">{t.lns.register.nameLabel}</label>
            <input
              data-testid={TID.lnsRegisterNameInput}
              className="input-sovereign"
              placeholder={t.lns.register.namePlaceholder}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <div data-testid="lns-register-uniqueness" className="mt-2 font-mono-data text-[10px] tracking-wide">
              {check.loading && <span className="text-[var(--lattice-text-3)]">⋯ verifica disponibilità on-chain…</span>}
              {!check.loading && check.available === true && (
                <span className="text-[#6ee7b7]">✓ DISPONIBILE · chiave ML-DSA-65 unica + DID unico</span>
              )}
              {!check.loading && check.available === false && (
                <span className="text-[#fca5a5]">
                  ✗ {check.reason === "already_taken" && "LNS già registrato sulla catena sovrana"}
                  {check.reason === "bad_suffix" && "Deve terminare in .azienda.id"}
                  {check.reason === "too_short" && "Troppo corto (min 3)"}
                  {check.reason === "forbidden_chars" && "Caratteri non consentiti"}
                  {check.reason === "network" && "Errore di rete"}
                </span>
              )}
            </div>
          </div>
          <div>
            <label className="eyebrow block mb-2">{t.lns.register.deptLabel}</label>
            <select
              data-testid={TID.lnsRegisterDeptSelect}
              className="input-sovereign"
              value={dept}
              onChange={(e) => setDept(e.target.value)}
            >
              {DEPARTMENTS.map((d) => (
                <option key={d} value={d} style={{ background: "#0a1020" }}>{d}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="eyebrow block mb-2">Ruolo</label>
              <select
                data-testid="lns-register-role-select"
                className="input-sovereign"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                <option value="admin" style={{ background: "#0a1020" }}>Admin · pieni poteri</option>
                <option value="operator" style={{ background: "#0a1020" }}>Operatore · invia/ricevi</option>
                <option value="auditor" style={{ background: "#0a1020" }}>Auditor · sola lettura</option>
                <option value="vendor" style={{ background: "#0a1020" }}>Vendor · solo metadata</option>
              </select>
            </div>
            <div>
              <label className="eyebrow block mb-2">Azienda (tenant)</label>
              <select
                data-testid="lns-register-tenant-select"
                className="input-sovereign"
                value={tenantId}
                onChange={(e) => setTenantId(e.target.value)}
              >
                <option value="" style={{ background: "#0a1020" }}>— senza tenant (.azienda.id) —</option>
                {tenants.map((tn) => (
                  <option key={tn.tenant_id} value={tn.tenant_id} style={{ background: "#0a1020" }}>
                    {tn.name} · {tn.domain}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
        <footer className="flex items-center justify-end gap-3 px-6 py-4 border-t hairline">
          <button data-testid={TID.lnsRegisterCancel} className="btn-ghost" onClick={onClose} disabled={busy}>
            {t.common.cancel}
          </button>
          <button
            data-testid={TID.lnsRegisterConfirm}
            className="btn-gold inline-flex items-center gap-2"
            onClick={submit}
            disabled={busy || !name.trim() || check.available === false}
          >
            <UserPlus size={13} />
            {busy ? "…" : t.lns.register.cta}
          </button>
        </footer>
      </div>
    </div>
  );
}
