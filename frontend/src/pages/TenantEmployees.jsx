import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { loadSession } from "@/lib/pqcAuth";
import { generateKeypairWasm } from "@/lib/latticeWasm";
import { generateEncKeypair } from "@/lib/certifyE2E";
import { encryptKeypairJson } from "@/lib/keypairVault";
import { PageHeader, SectionPanel } from "@/components/Primitives";
import { UserPlus, Users, KeyRound, Trash2, ShieldCheck, X, Briefcase, AlertTriangle, Lock } from "lucide-react";
import { toast } from "sonner";

const ROLES = [
  { value: "admin", label: "Admin", hint: "Pieni poteri sull'azienda" },
  { value: "operator", label: "Operatore", hint: "Invia/riceve mail e messaggi" },
  { value: "auditor", label: "Auditor", hint: "Solo lettura · vede metadati" },
];

function KeypairModal({ keypair, lns, onClose }) {
  const [passphrase, setPassphrase] = useState("");
  const [busy, setBusy] = useState(false);
  if (!keypair) return null;

  const buildPayload = () => ({
    version: 1,
    algorithm: "ML-DSA-65",
    enc_algorithm: "X25519",
    lns,
    did: keypair.did,
    tenant_id: keypair.tenant_id,
    public_key_hex: keypair.public_key_hex,
    secret_key_hex: keypair.secret_key_hex,
    enc_public_key_hex: keypair.enc_public_key_hex,
    enc_secret_key_hex: keypair.enc_secret_key_hex,
    created_at: keypair.registered_at || new Date().toISOString(),
  });

  const triggerDownload = (obj, filename) => {
    const blob = new Blob([JSON.stringify(obj, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const download = () => {
    triggerDownload(buildPayload(), `${lns}.keypair.json`);
    toast.success("Keypair scaricata in chiaro · consegnala via canale sicuro");
  };

  const downloadEncrypted = async () => {
    if (passphrase.length < 12) {
      toast.error("Passphrase troppo corta (minimo 12 caratteri)");
      return;
    }
    setBusy(true);
    try {
      const sealed = await encryptKeypairJson(buildPayload(), passphrase);
      triggerDownload(sealed, `${lns}.keypair.encrypted.json`);
      toast.success("Backup cifrato scaricato · conserva la passphrase OFFLINE");
      setPassphrase("");
    } catch (e) {
      toast.error("Errore cifratura: " + e.message);
    } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-6">
      <div data-testid="employee-keypair-modal" className="w-full max-w-xl surface-elev relative">
        <div className="absolute top-0 left-0 right-0 h-px gold-line" />
        <header className="flex items-start justify-between px-6 py-5 border-b hairline">
          <div>
            <div className="eyebrow flex items-center gap-2"><KeyRound size={11} className="text-[var(--lattice-gold)]" /> CHIAVE GENERATA · UNA SOLA VOLTA</div>
            <h3 className="font-display text-2xl text-white mt-1">{lns}</h3>
          </div>
          <button onClick={onClose} className="text-[var(--lattice-text-3)] hover:text-white">
            <X size={18} />
          </button>
        </header>
        <div className="px-6 py-5 space-y-4">
          <div className="border border-amber-500/40 bg-amber-500/5 px-4 py-3 font-mono-data text-[11px] text-amber-200 leading-relaxed">
            <AlertTriangle size={12} className="inline mr-1" />
            <strong className="text-amber-100">Attenzione:</strong> questa è l'unica copia della chiave segreta. Il server non la conserva.
            Scaricala ORA e consegnala via canale sicuro al dipendente (di persona / canale cifrato). Senza, non potrà mai accedere.
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 font-mono-data text-[10px]">
            <div>
              <span className="text-[var(--lattice-text-3)] uppercase">DID</span>
              <div className="text-white mt-1 break-all">{keypair.did}</div>
            </div>
            <div>
              <span className="text-[var(--lattice-text-3)] uppercase">Fingerprint</span>
              <div className="text-[var(--lattice-gold)] mt-1 break-all">{keypair.public_key_fingerprint}</div>
            </div>
          </div>
          <button
            data-testid="download-employee-keypair"
            onClick={download}
            className="btn-gold inline-flex items-center gap-2 w-full justify-center"
          >
            <KeyRound size={13} /> Scarica .keypair.json (in chiaro)
          </button>
          <div className="border-t hairline pt-4">
            <div className="eyebrow flex items-center gap-2 mb-2">
              <Lock size={11} className="text-emerald-400" /> BACKUP CIFRATO (opzionale, AES-256-GCM)
            </div>
            <p className="font-mono-data text-[10px] text-[var(--lattice-text-3)] mb-3">
              Cifra il file con una passphrase (PBKDF2 600k iter). Utile per backup off-site.
              <strong className="text-amber-200"> Senza passphrase, il file è inutilizzabile.</strong>
            </p>
            <input
              type="password"
              value={passphrase}
              onChange={(e) => setPassphrase(e.target.value)}
              placeholder="Passphrase (minimo 12 caratteri)"
              data-testid="keypair-passphrase"
              className="w-full bg-transparent border border-[var(--lattice-border-strong)] px-3 py-2 font-mono-data text-[12px] text-white mb-2"
            />
            <button
              data-testid="download-employee-keypair-encrypted"
              onClick={downloadEncrypted}
              disabled={busy || passphrase.length < 12}
              className="btn-ghost inline-flex items-center gap-2 w-full justify-center disabled:opacity-50"
            >
              <Lock size={12} /> {busy ? "Cifratura…" : "Scarica backup cifrato"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function TenantEmployees() {
  const session = loadSession();
  const tenantId = session?.tenant_id;
  const tenantDomain = session?.lns?.split(".").slice(1).join(".");

  const [employees, setEmployees] = useState([]);
  const [tenantInfo, setTenantInfo] = useState(null);
  const [loading, setLoading] = useState(true);

  // Add form — Nome + Cognome separati, azienda da tenantInfo, LNS auto-derivato
  const [empFirst, setEmpFirst] = useState("");
  const [empLast, setEmpLast] = useState("");
  const [empDept, setEmpDept] = useState("");
  const [empCompany, setEmpCompany] = useState("");
  const [empRole, setEmpRole] = useState("operator");
  const [empBusy, setEmpBusy] = useState(false);

  // When tenantInfo loads, pre-fill the (editable) company label so the
  // operator doesn't see an empty box.
  useEffect(() => {
    if (tenantInfo?.name && !empCompany) setEmpCompany(tenantInfo.name);
  }, [tenantInfo, empCompany]);

  // Slugify "Mario" + "Bianchi" → "mario.bianchi"
  const _slug = (s) =>
    s
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "");
  const empHandle = (() => {
    const f = _slug(empFirst);
    const l = _slug(empLast);
    if (f && l) return `${f}.${l}`;
    return f || l || "";
  })();
  const empPreviewLns =
    empHandle && tenantInfo?.domain ? `${empHandle}.${tenantInfo.domain}` : "";

  // Keypair modal
  const [showKeypair, setShowKeypair] = useState(null);  // {keypair, lns}

  const load = async () => {
    if (!tenantId) return;
    try {
      const [emps, tnt] = await Promise.all([
        api.get(`/tenants/${tenantId}/employees`),
        api.get(`/tenants/${tenantId}`),
      ]);
      setEmployees(emps.data);
      setTenantInfo(tnt.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Errore caricamento");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [tenantId]);

  // Pre-load WASM on mount so user-perceived latency at submit time is
  // zero AND we can surface failures early instead of at submit.
  const [wasmReady, setWasmReady] = useState(false);
  const [wasmError, setWasmError] = useState("");
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { initLatticeWasm } = await import("@/lib/latticeWasm");
        await initLatticeWasm();
        if (!cancelled) setWasmReady(true);
      } catch (e) {
        if (!cancelled) {
          console.error("WASM init failed:", e);
          setWasmError(e?.message || String(e));
        }
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const submitEmployee = async () => {
    if (!empHandle || !tenantInfo?.domain) {
      toast.error("Inserisci Nome e Cognome");
      return;
    }
    if (!wasmReady) {
      toast.error(
        wasmError
          ? `Modulo crittografico non caricato: ${wasmError}. Ricarica la pagina (Ctrl+Shift+R) e riprova.`
          : "Modulo crittografico ancora in caricamento. Attendi un secondo e riprova."
      );
      return;
    }
    setEmpBusy(true);
    try {
      const fullLns = `${empHandle}.${tenantInfo.domain}`;
      const fullName = `${empFirst.trim()} ${empLast.trim()}`.trim();
      // Generate keypair CLIENT-SIDE (WASM, pre-loaded above).
      // Secret key NEVER touches the server — only the public key.
      const clientKp = await generateKeypairWasm();
      const encKp = generateEncKeypair();
      const r = await api.post("/lns/register", {
        lns_name: fullLns,
        display_name: fullName,
        department: empDept,
        role: empRole,
        tenant_id: tenantId,
        public_key_hex: clientKp.public_key_hex,
        enc_public_key_hex: encKp.enc_public_key_hex,
      });
      toast.success(`${fullName} registrato · ${r.data.lns_name}`);
      setEmpFirst("");
      setEmpLast("");
      setShowKeypair({
        keypair: {
          ...r.data,
          secret_key_hex: clientKp.secret_key_hex,
          public_key_hex: clientKp.public_key_hex,
          enc_public_key_hex: encKp.enc_public_key_hex,
          enc_secret_key_hex: encKp.enc_secret_key_hex,
        },
        lns: r.data.lns_name,
      });
      await load();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      let msg = "";
      if (Array.isArray(detail)) {
        msg = detail.map((d) => d.msg || JSON.stringify(d)).join(" · ");
      } else if (typeof detail === "string") {
        msg = detail;
      } else if (e?.message) {
        msg = e.message;
      } else {
        msg = "vedi console";
      }
      console.error("register_lns error:", e);
      toast.error(`Errore registrazione: ${msg}`);
    } finally { setEmpBusy(false); }
  };

  const changeRole = async (lns, newRole) => {
    try {
      await api.patch(`/lns/${encodeURIComponent(lns)}/role`, { role: newRole });
      toast.success(`${lns} → ${newRole}`);
      await load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Errore cambio ruolo"); }
  };

  const deleteEmp = async (lns) => {
    if (!window.confirm(`Eliminare ${lns} dall'azienda?\nVerrà notarizzato on-chain come IdentityDelete. Il dipendente non potrà più accedere.`)) return;
    try {
      const r = await api.delete(`/lns/${encodeURIComponent(lns)}`);
      toast.success(`${lns} eliminato · block #${r.data.block_index}`);
      await load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Errore eliminazione"); }
  };

  const revokeEmp = async (lns) => {
    if (!window.confirm(`Revocare la chiave di ${lns}?\nIl dipendente non potrà più accedere ma la sua storia resta on-chain.`)) return;
    try {
      const r = await api.post(`/lns/${encodeURIComponent(lns)}/revoke`);
      toast.success(`${lns} revocato · tx ${r.data.tx_id.slice(0, 12)}…`);
      await load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Errore revoca"); }
  };

  // Iter_53: revoca per chiave compromessa (admin-founder). Differente dal
  // revoke standard: usa l'endpoint dedicato che firma con la SK del fondatore
  // ML-DSA-65 (non con la chiave sovereign), così la revoca è attribuibile
  // all'azienda nell'audit on-chain.
  const revokeCompromised = async (lns) => {
    const reason = window.prompt(
      `🚨 REVOCA PER CHIAVE COMPROMESSA · ${lns}\n\n` +
      "Questo NON è un revoke ordinario:\n" +
      "• La LNS viene marcata REVOKED on-chain (firma ML-DSA del fondatore)\n" +
      "• Tutti gli enrollment recovery e le richieste pending vengono cancellate\n" +
      "• Il dipendente DEVE registrarsi nuovamente con una nuova identità\n" +
      "• Le mail Certify ricevute prima della revoca restano illeggibili\n\n" +
      "Specifica il motivo (verrà notarizzato on-chain):",
      "key-stolen",
    );
    if (!reason || !reason.trim()) return;
    try {
      const r = await api.post("/lns/revoke-by-tenant-founder", {
        lns_name: lns,
        admin: session?.lns || "",
        reason: reason.trim(),
      });
      toast.success(`🚨 ${lns} REVOCATA on-chain · tx ${r.data.tx_id.slice(0, 12)}… · blocco #${r.data.block_index}`);
      await load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Errore revoca compromessa"); }
  };

  if (!session?.tenant_id) {
    return (
      <div className="surface-elev border hairline p-8 max-w-xl">
        <h2 className="font-display text-2xl text-white">Accesso negato</h2>
        <p className="text-[13px] text-[var(--lattice-text-3)] mt-2">Devi essere admin della tua azienda per gestire i dipendenti.</p>
      </div>
    );
  }

  const active = employees.filter((e) => e.status !== "REVOKED");
  const revoked = employees.filter((e) => e.status === "REVOKED");

  return (
    <div className="space-y-8" data-testid="tenant-employees-page">
      <PageHeader
        eyebrow="WORKSPACE AZIENDALE · DIPENDENTI"
        title={`Gestisci dipendenti — ${tenantInfo?.name || tenantDomain || "—"}`}
        subtitle="Registra nuovi dipendenti, assegna loro un ruolo e consegna la keypair. Tutte le azioni sono notarizzate on-chain. La chiave segreta è disponibile UNA SOLA volta — scaricala subito e consegnala via canale sicuro."
      />

      {/* Add employee form */}
      <SectionPanel title="Nuovo dipendente" eyebrow="+ ADD EMPLOYEE" testId="add-employee-panel">
        <div className="px-5 py-5 space-y-4 max-w-3xl">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="eyebrow block mb-2">Nome</label>
              <input
                data-testid="emp-first-input"
                className="input-sovereign"
                placeholder="Mario"
                value={empFirst}
                onChange={(e) => setEmpFirst(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && submitEmployee()}
              />
            </div>
            <div>
              <label className="eyebrow block mb-2">Cognome</label>
              <input
                data-testid="emp-last-input"
                className="input-sovereign"
                placeholder="Bianchi"
                value={empLast}
                onChange={(e) => setEmpLast(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && submitEmployee()}
              />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="eyebrow block mb-2 flex items-center gap-2"><Briefcase size={11} className="text-[var(--lattice-gold)]" /> Azienda</label>
              <input
                data-testid="emp-tenant-input"
                className="input-sovereign"
                placeholder={tenantInfo?.name || "Nome azienda"}
                value={empCompany}
                onChange={(e) => setEmpCompany(e.target.value)}
              />
              <p className="font-mono-data text-[10px] text-[var(--lattice-text-4)] mt-1">
                Etichetta libera. Il dominio tecnico resta sempre <span className="text-[var(--lattice-gold)]">{tenantInfo?.domain || tenantDomain || "…"}</span>.
              </p>
            </div>
            <div>
              <label className="eyebrow block mb-2 flex items-center gap-2"><ShieldCheck size={11} className="text-[var(--lattice-gold)]" /> Ruolo</label>
              <select
                data-testid="emp-role-select"
                className="input-sovereign"
                value={empRole}
                onChange={(e) => setEmpRole(e.target.value)}
              >
                {ROLES.map((r) => (
                  <option key={r.value} value={r.value} style={{ background: "#0a1020" }}>
                    {r.label} — {r.hint}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="eyebrow block mb-2 flex items-center gap-2"><Briefcase size={11} className="text-[var(--lattice-gold)]" /> Dipartimento</label>
            <input
              data-testid="emp-dept-input"
              className="input-sovereign"
              placeholder="es. Operations · Finance · Legal · IT · HR · Sales · R&D · ..."
              value={empDept}
              onChange={(e) => setEmpDept(e.target.value)}
            />
            <p className="font-mono-data text-[10px] text-[var(--lattice-text-4)] mt-1">
              Testo libero. Scrivi quello che vuoi.
            </p>
          </div>
          <div className="border hairline px-3 py-2 bg-[rgba(212,175,55,0.04)]" data-testid="emp-lns-preview">
            <div className="eyebrow text-[10px] mb-1">LNS che verrà registrato</div>
            <div className="font-mono-data text-[13px] text-[var(--lattice-gold)] break-all">
              {empPreviewLns || <span className="text-[var(--lattice-text-3)]">— inserisci Nome e Cognome —</span>}
            </div>
          </div>
          <button
            data-testid="emp-submit-btn"
            onClick={submitEmployee}
            disabled={empBusy || !empHandle || !tenantInfo || !wasmReady}
            className="btn-gold inline-flex items-center gap-2"
          >
            <UserPlus size={13} /> {empBusy ? "Registro…" : "Aggiungi dipendente e genera chiave"}
          </button>
          {!wasmReady && !wasmError && (
            <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] mt-2">
              Caricamento modulo crittografico WASM…
            </div>
          )}
          {wasmError && (
            <div data-testid="emp-wasm-error" className="font-mono-data text-[11px] text-rose-300 mt-2 border border-rose-500/30 bg-rose-500/5 px-3 py-2">
              <strong>Crittografia bloccata.</strong> Il modulo WASM non è stato caricato dal browser:
              <code className="block mt-1 break-all">{wasmError}</code>
              Soluzione: ricarica la pagina con <kbd>Ctrl+Shift+R</kbd> (Windows/Linux) o <kbd>Cmd+Shift+R</kbd> (Mac).
              Se persiste, prova un altro browser (Chrome/Firefox/Edge aggiornato).
            </div>
          )}
        </div>
      </SectionPanel>

      {/* Active employees */}
      <SectionPanel
        title={`Dipendenti attivi · ${active.length}`}
        eyebrow="ACTIVE WORKFORCE · ON-CHAIN"
        testId="active-employees-panel"
      >
        {loading ? (
          <div className="px-5 py-10 text-center font-mono-data text-[11px] text-[var(--lattice-text-4)] uppercase tracking-wider">Caricamento…</div>
        ) : active.length === 0 ? (
          <div className="px-5 py-10 text-center font-mono-data text-[11px] text-[var(--lattice-text-4)] uppercase tracking-wider">
            Nessun dipendente. Registra il primo qui sopra.
          </div>
        ) : (
          <div>
            {active.map((e) => (
              <div
                key={e.lns_name}
                data-testid={`employee-row-${e.lns_name}`}
                className="px-5 py-3 border-b hairline flex items-center gap-3 hover:bg-[rgba(255,255,255,0.02)]"
              >
                <Users size={14} className="text-[var(--lattice-gold)] shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] text-white truncate" data-testid={`employee-name-${e.lns_name}`}>
                    {e.display_name || e.lns_name}
                  </div>
                  <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] truncate">
                    {e.lns_name} · {e.department || "—"} · {e.public_key_fingerprint?.slice(0, 16)}…
                  </div>
                </div>
                <select
                  data-testid={`employee-role-${e.lns_name}`}
                  value={e.role || "operator"}
                  onChange={(ev) => changeRole(e.lns_name, ev.target.value)}
                  className="bg-transparent border border-[var(--lattice-border-strong)] px-2 py-1 font-mono-data text-[10px] text-white"
                >
                  {ROLES.map((r) => (
                    <option key={r.value} value={r.value} style={{ background: "#0a1020" }}>{r.label}</option>
                  ))}
                </select>
                <button
                  data-testid={`employee-revoke-${e.lns_name}`}
                  onClick={() => revokeEmp(e.lns_name)}
                  className="font-mono-data text-[10px] uppercase tracking-wider px-2 py-1 border border-amber-500/40 text-amber-300 hover:bg-amber-500/10"
                  title="Revoca chiave (storia preservata)"
                >
                  Revoca
                </button>
                <button
                  data-testid={`employee-revoke-compromised-${e.lns_name}`}
                  onClick={() => revokeCompromised(e.lns_name)}
                  className="font-mono-data text-[10px] uppercase tracking-wider px-2 py-1 border border-rose-500/60 text-rose-300 hover:bg-rose-500/15 font-bold"
                  title="🚨 Revoca compromessa (firmata dal fondatore on-chain)"
                >
                  🚨 Compromessa
                </button>
                <button
                  data-testid={`employee-delete-${e.lns_name}`}
                  onClick={() => deleteEmp(e.lns_name)}
                  className="font-mono-data text-[10px] uppercase tracking-wider px-2 py-1 border border-red-500/40 text-red-300 hover:bg-red-500/10 inline-flex items-center gap-1"
                  title="Elimina dal registro"
                >
                  <Trash2 size={10} /> Elimina
                </button>
              </div>
            ))}
          </div>
        )}
      </SectionPanel>

      {/* Revoked */}
      {revoked.length > 0 && (
        <SectionPanel
          title={`Dipendenti revocati · ${revoked.length}`}
          eyebrow="REVOKED · HISTORY PRESERVED"
          testId="revoked-employees-panel"
        >
          <div>
            {revoked.map((e) => (
              <div key={e.lns_name} className="px-5 py-3 border-b hairline flex items-center gap-3 opacity-60">
                <Users size={14} className="text-rose-300 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="font-mono-data text-[12px] text-white truncate">{e.lns_name}</div>
                  <div className="font-mono-data text-[10px] text-rose-300">REVOCATO {(e.revoked_at || "").slice(0, 10)}</div>
                </div>
                <button
                  onClick={() => deleteEmp(e.lns_name)}
                  className="font-mono-data text-[10px] uppercase tracking-wider px-2 py-1 border border-red-500/40 text-red-300 hover:bg-red-500/10"
                >
                  <Trash2 size={10} className="inline mr-1" /> Elimina
                </button>
              </div>
            ))}
          </div>
        </SectionPanel>
      )}

      <KeypairModal
        keypair={showKeypair?.keypair}
        lns={showKeypair?.lns}
        onClose={() => setShowKeypair(null)}
      />
    </div>
  );
}
