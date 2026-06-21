import { useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import { api } from "@/lib/api";
import { loadSession } from "@/lib/pqcAuth";
import {
  buildEnrollPayload,
  guardianContribute,
  recoverSecretKey,
} from "@/lib/keyrecovery";
import { generateEncKeypair } from "@/lib/certifyE2E";
import {
  ShieldCheck,
  Users,
  KeyRound,
  AlertTriangle,
  Boxes,
  RefreshCcw,
  Download,
  Inbox,
  Printer,
  QrCode,
  Save,
} from "lucide-react";
import { toast } from "sonner";

function Card({ title, hint, icon: Icon, tone = "gold", children, tid }) {
  const toneClass =
    tone === "gold"
      ? "text-[var(--lattice-gold)]"
      : tone === "sky"
      ? "text-sky-300"
      : "text-rose-300";
  return (
    <section data-testid={tid} className="surface-elev border hairline relative">
      <div className="absolute top-0 left-0 right-0 h-px gold-line" />
      <header className="px-6 py-5 border-b hairline">
        <div className={`eyebrow flex items-center gap-2 ${toneClass}`}>
          {Icon && <Icon size={11} />} {title}
        </div>
        {hint && (
          <p className="text-[12px] text-[var(--lattice-text-3)] mt-2 leading-relaxed">
            {hint}
          </p>
        )}
      </header>
      <div className="px-6 py-5">{children}</div>
    </section>
  );
}

function fpShort(h) {
  if (!h) return "—";
  return `${h.slice(0, 10)}…${h.slice(-6)}`;
}

// Section visible to NON-founder tenant employees who don't yet have a
// personal recovery enrollment. Fetches the tenant policy (3 corporate
// guardians chosen by the founder), splits the user's SK via Shamir/WASM
// locally, encrypts each share against the respective guardian's X25519 pk,
// and POSTs to /keyrecovery/enroll. After this, the employee can recover
// their key via the same 3 corporate nominees.
function EmployeeAutoEnrollSection({ session, currentEnrollment, reload }) {
  const [policy, setPolicy] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!session?.tenant_id) { setLoading(false); return; }
    let alive = true;
    api.get(`/keyrecovery/policy/${session.tenant_id}`)
      .then((r) => { if (alive) setPolicy(r.data); })
      .catch((e) => { if (alive) setErr(e?.response?.data?.detail || e.message); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [session?.tenant_id]);

  if (loading || currentEnrollment?.enrolled) return null;
  if (!policy?.policy_set) {
    return (
      <Card
        title="BACKUP CHIAVE · POLICY AZIENDALE NON ANCORA ATTIVA"
        hint="Il fondatore della tua azienda deve prima configurare i 3 nominati aziendali. Quando l'avrà fatto, qui potrai attivare il backup della tua chiave con un click."
        icon={AlertTriangle}
        tone="rose"
        tid="recovery-employee-no-policy"
      >
        <div className="font-mono-data text-[11px] text-[var(--lattice-text-3)]">
          Fondatore atteso: <span className="text-white">{policy?.founder || "—"}</span>
        </div>
      </Card>
    );
  }

  const submit = async () => {
    setErr(""); setBusy(true);
    try {
      const skHex = sessionStorage.getItem("lattice.sk");
      if (!skHex) throw new Error("Sessione non contiene la SK ML-DSA-65. Rifai login.");
      const guardians = policy.guardians.map((g) => ({
        lns: g.lns, enc_public_key_hex: g.enc_public_key_hex,
      }));
      if (guardians.some((g) => !g.enc_public_key_hex)) {
        throw new Error("Uno dei 3 nominati aziendali non ha pubblicato la chiave X25519.");
      }
      const payload = await buildEnrollPayload({
        ownerLns: session.lns, ownerSkHex: skHex, guardians,
      });
      const r = await api.post("/keyrecovery/enroll", payload);
      toast.success(`Backup attivato · block #${r.data.block_index}`);
      reload();
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message || "Errore enrollment";
      setErr(msg); toast.error(msg);
    } finally { setBusy(false); }
  };

  return (
    <Card
      title="BACKUP DELLA TUA CHIAVE · ATTIVA CON UN CLICK"
      hint={`Il fondatore (${policy.founder}) ha designato 3 nominati aziendali. Cliccando qui sotto, la tua chiave ML-DSA-65 verrà divisa in browser via Shamir GF(256) (2-di-3) e ciascun frammento cifrato per il rispettivo nominato. Nessuna parte della chiave lascia mai il browser.`}
      icon={KeyRound}
      tone="sky"
      tid="recovery-employee-auto-enroll"
    >
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {policy.guardians.map((g, i) => (
            <div key={g.lns} className="border hairline p-3" data-testid={`auto-enroll-guardian-${i + 1}`}>
              <div className="eyebrow text-[10px] mb-1">NOMINATO #{i + 1}</div>
              <div className="font-mono-data text-[12px] text-white break-all">{g.lns}</div>
              {g.display_name && (
                <div className="text-[11px] text-[var(--lattice-text-3)] mt-1">{g.display_name}</div>
              )}
              <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] mt-2">
                X25519 pk: {g.enc_public_key_hex ? fpShort(g.enc_public_key_hex) : "❌ assente"}
              </div>
            </div>
          ))}
        </div>
        {err && (
          <div className="border border-rose-500/40 bg-rose-500/5 px-3 py-2 font-mono-data text-[11px] text-rose-300" data-testid="auto-enroll-error">
            {err}
          </div>
        )}
        <button
          onClick={submit}
          disabled={busy}
          data-testid="auto-enroll-submit"
          className="px-4 py-2 border border-sky-300 text-sky-300 font-mono-data text-[11px] tracking-[0.18em] uppercase hover:bg-sky-300/10 disabled:opacity-50"
        >
          {busy ? "Cifratura share locali…" : "Attiva il mio backup con questi 3 nominati →"}
        </button>
      </div>
    </Card>
  );
}

// ------------------------------------------------------------------ Enroll
function EnrollSection({ session, employees, currentEnrollment, reload }) {
  const [g1, setG1] = useState("");
  const [g2, setG2] = useState("");
  const [g3, setG3] = useState("");
  const [busy, setBusy] = useState(false);
  const [lastTx, setLastTx] = useState(null);

  const myLns = session?.lns;
  // Show ALL employees of the tenant (excluding myself). Mark those who
  // haven't yet published their X25519 encryption key (`enc_pk_hex`) as
  // non-selectable, because we cannot encrypt a Shamir share without it.
  // A nominee becomes selectable as soon as they perform their first
  // login (or were registered with `enc_public_key_hex` from the start).
  const candidates = useMemo(
    () => employees
      .filter((e) => (e.lns_name || e.entity) && (e.lns_name || e.entity) !== myLns)
      .filter((e) => (e.status || "ACTIVE") !== "REVOKED")
      .map((e) => ({
        ...e,
        entity: e.lns_name || e.entity,
        _ready: Boolean(e.enc_pk_hex || e.enc_public_key_hex),
      })),
    [employees, myLns],
  );
  const readyCount = candidates.filter((c) => c._ready).length;

  const submit = async () => {
    const selected = [g1, g2, g3];
    if (new Set(selected).size !== 3 || selected.some((x) => !x)) {
      toast.error("Scegli 3 nominati distinti");
      return;
    }
    const skHex = sessionStorage.getItem("lattice.sk");
    if (!skHex) {
      toast.error("Sessione senza chiave segreta: rifai login con il .keypair.json");
      return;
    }
    setBusy(true);
    try {
      const guardians = selected.map((lns) => {
        const e = employees.find((x) => (x.lns_name || x.entity) === lns);
        return { lns, enc_public_key_hex: e?.enc_pk_hex || e?.enc_public_key_hex };
      });
      const payload = await buildEnrollPayload({
        ownerLns: myLns,
        ownerSkHex: skHex,
        guardians,
      });
      const r = await api.post("/keyrecovery/enroll", payload);
      setLastTx(r.data);
      toast.success(`Backup 2-di-3 notarizzato on-chain · block #${r.data.block_index}`);
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message || "Errore enrollment");
    } finally {
      setBusy(false);
    }
  };

  if (currentEnrollment?.enrolled) {
    return (
      <Card
        title="BACKUP ATTIVO · 2-DI-3 NOMINATI"
        hint="Le tue 3 firme di backup sono già state notarizzate on-chain. Per cambiare nominati, esegui di nuovo l'enrollment (sovrascrive il precedente)."
        icon={ShieldCheck}
        tid="recovery-enrolled"
      >
        <div className="space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {[1, 2, 3].map((i) => {
              const lns = currentEnrollment.guardians[i - 1];
              const fp = currentEnrollment.fingerprints?.[`share${i}`];
              return (
                <div
                  key={i}
                  className="border hairline p-3"
                  data-testid={`recovery-guardian-${i}`}
                >
                  <div className="eyebrow text-[10px] mb-1">NOMINATO #{i}</div>
                  <div className="font-mono-data text-[12px] text-white break-all">
                    {lns}
                  </div>
                  <div className="gold-line my-2" />
                  <div className="eyebrow text-[10px] mb-1">FINGERPRINT SHARE (SHA3-256)</div>
                  <div className="font-mono-data text-[11px] text-[var(--lattice-text-2)]">
                    {fpShort(fp)}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="border hairline px-4 py-3 bg-[rgba(212,175,55,0.04)] text-[12px] text-[var(--lattice-text-2)] flex gap-2">
            <ShieldCheck size={13} className="text-[var(--lattice-gold)] mt-0.5 shrink-0" />
            <span>
              Soglia <strong className="text-white">2 di 3</strong>. La blockchain custodisce
              SOLO i fingerprint SHA3-256 dei 3 share — nessun pezzo della tua chiave segreta
              è mai uscito dal browser.
            </span>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card
      title="IMPOSTA BACKUP 2-DI-3"
      hint="Scegli 3 colleghi della tua azienda come nominati. La tua chiave segreta viene divisa in 3 frammenti via Shamir Secret Sharing (compilato in Rust→WASM) e ogni frammento viene cifrato in locale con la chiave del rispettivo nominato. Servono almeno 2 firme per ricostruire la chiave."
      icon={ShieldCheck}
      tid="recovery-enroll"
    >
      {readyCount < 3 && (
        <div data-testid="recovery-not-enough" className="border border-amber-500/40 bg-amber-500/5 px-4 py-3 mb-4 text-[12px] text-[var(--lattice-text-2)] flex items-start gap-2">
          <ShieldCheck size={13} className="text-amber-300 mt-0.5 shrink-0" />
          <div>
            <strong className="text-amber-200">Servono almeno 3 colleghi che si siano già loggati con la propria chiave.</strong>{" "}
            Attualmente sono pronti: <span className="text-white font-mono-data">{readyCount}</span> su <span className="text-white font-mono-data">{candidates.length}</span> dipendenti.
            <br />
            Spiegazione tecnica: ogni nominato deve aver pubblicato la propria chiave pubblica di cifratura (X25519). Questo avviene automaticamente al primo login. I dipendenti appena registrati appaiono nella lista ma sono <em>non selezionabili</em> finché non fanno login.
          </div>
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        {[
          { v: g1, set: setG1, idx: 1 },
          { v: g2, set: setG2, idx: 2 },
          { v: g3, set: setG3, idx: 3 },
        ].map(({ v, set, idx }) => (
          <div key={idx} className="border hairline p-3">
            <div className="eyebrow text-[10px] mb-2">NOMINATO #{idx}</div>
            <select
              data-testid={`recovery-pick-guardian-${idx}`}
              value={v}
              onChange={(e) => set(e.target.value)}
              className="w-full bg-transparent border hairline px-2 py-2 font-mono-data text-[12px] text-white"
            >
              <option value="">— scegli —</option>
              {candidates.map((c) => (
                <option
                  key={c.entity}
                  value={c._ready ? c.entity : ""}
                  disabled={!c._ready}
                >
                  {c.entity}{c.display_name ? ` · ${c.display_name}` : ""}{c._ready ? "" : " · ⚠ non ancora loggato (no chiave di cifratura pubblicata)"}
                </option>
              ))}
            </select>
          </div>
        ))}
      </div>
      <button
        data-testid="recovery-enroll-submit"
        onClick={submit}
        disabled={busy}
        className="px-4 py-2 border border-[var(--lattice-gold)] text-[var(--lattice-gold)] font-mono-data text-[11px] tracking-[0.18em] uppercase hover:bg-[rgba(212,175,55,0.08)] disabled:opacity-50"
      >
        {busy ? "Suddividendo + cifrando…" : "Notarizza backup on-chain"}
      </button>
      {lastTx && (
        <div className="mt-4 border hairline px-3 py-2 font-mono-data text-[11px] text-emerald-300">
          ✔ block #{lastTx.block_index} · tx {lastTx.tx_id}
        </div>
      )}
    </Card>
  );
}

// ------------------------------------------------------------ Open Request
function OpenRequestSection({ session, currentEnrollment, onOpened }) {
  const [busy, setBusy] = useState(false);
  if (!currentEnrollment?.enrolled) return null;

  const open = async () => {
    setBusy(true);
    try {
      // The requester needs a FRESH X25519 keypair so the guardians can
      // re-seal their shares for the new (post-recovery) identity.
      const newEnc = generateEncKeypair();
      sessionStorage.setItem("lattice.recovery.enc_sk", newEnc.enc_secret_key_hex);
      sessionStorage.setItem("lattice.recovery.enc_pk", newEnc.enc_public_key_hex);

      const r = await api.post("/keyrecovery/request", {
        lns: session.lns,
        reason: "lost_keypair",
        requester_enc_pk_hex: newEnc.enc_public_key_hex,
      });
      toast.success(`Richiesta di recupero aperta · ID ${r.data.request_id}`);
      onOpened(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card
      title="APRI RICHIESTA DI RECUPERO"
      hint="Se hai perso il file .keypair.json, apri una richiesta: i tuoi 3 nominati riceveranno una notifica. Quando 2 di loro contribuiscono, ricostruisci la chiave qui sotto in locale."
      icon={KeyRound}
      tone="sky"
      tid="recovery-open-request"
    >
      <button
        data-testid="recovery-open-btn"
        onClick={open}
        disabled={busy}
        className="px-4 py-2 border border-sky-300 text-sky-300 font-mono-data text-[11px] tracking-[0.18em] uppercase hover:bg-sky-300/10 disabled:opacity-50"
      >
        {busy ? "Aprendo…" : "Apri richiesta 2-di-3"}
      </button>
    </Card>
  );
}

// --------------------------------------------------- Pending as Guardian
function PendingAsGuardianSection({ session }) {
  const [pending, setPending] = useState([]);
  const [busyId, setBusyId] = useState(null);

  const load = async () => {
    try {
      const r = await api.get("/keyrecovery/requests/pending-as-guardian");
      setPending(r.data.items || []);
    } catch (e) { /* anon caller is fine */ }
  };
  useEffect(() => { load(); }, []);

  const contribute = async (row) => {
    setBusyId(row.request_id);
    try {
      // 1) fetch the encrypted share that the server is holding for me
      const r = await api.get(`/keyrecovery/share-for-guardian/${row.request_id}`, {
        params: { guardian_lns: session.lns },
      });
      const sealedEnvelopeForMe = r.data.sealed_envelope;
      // X25519 sk is held in sessionStorage (set at login from
      // `.keypair.json#enc_secret_key_hex`). Older keypair files predating
      // 2026-02 don't carry this field — fallback to legacy `session` shape.
      const myEncSkHex = sessionStorage.getItem("lattice.enc_sk") || session?.enc_secret_key_hex;
      if (!myEncSkHex) {
        toast.error(
          "Chiave X25519 non disponibile in questa sessione. Rifai login caricando " +
          "il tuo .keypair.json (la chiave viene riposta in sessionStorage e non lascia " +
          "mai il browser). Se il file non contiene 'enc_secret_key_hex', chiedi " +
          "all'amministratore di rigenerare la tua identità.",
          { duration: 8000 },
        );
        return;
      }
      // 2) fetch the requester's NEW X25519 pk so we can re-seal for them
      const reqStatus = await api.get(`/keyrecovery/status/${row.request_id}`);
      const requesterEncPkHex = reqStatus.data?.requester_enc_pk_hex;
      if (!requesterEncPkHex) {
        toast.error(
          "Richiesta senza chiave pubblica del richiedente. Chiedi al richiedente di rilanciare /api/keyrecovery/request includendo `requester_enc_pk_hex`.",
        );
        return;
      }
      // 3) decrypt my share locally and re-seal it for the requester
      const newEnvelope = await guardianContribute({
        myEncSkHex,
        sealedEnvelopeForMe,
        requesterEncPkHex: requesterEncPkHex.trim(),
      });
      await api.post("/keyrecovery/contribute", {
        request_id: row.request_id,
        guardian_lns: session.lns,
        contributed_share: newEnvelope,
      });
      toast.success(`Contribuito alla richiesta ${row.request_id}`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Card
      title="RICHIESTE IN ATTESA · SEI NOMINATO"
      hint="Richieste di recupero dove tu sei uno dei 3 nominati. Clicca su 'Contribuisci' per decifrare il tuo frammento (localmente) e ri-sigillarlo per il richiedente."
      icon={Inbox}
      tone="sky"
      tid="recovery-pending-as-guardian"
    >
      <div className="flex items-center justify-between mb-3">
        <span className="font-mono-data text-[11px] text-[var(--lattice-text-3)]">
          {pending.length} in attesa
        </span>
        <button
          data-testid="recovery-pending-reload"
          onClick={load}
          className="font-mono-data text-[11px] text-[var(--lattice-text-3)] hover:text-white flex items-center gap-1"
        >
          <RefreshCcw size={11} /> aggiorna
        </button>
      </div>
      {pending.length === 0 ? (
        <div className="text-[12px] text-[var(--lattice-text-3)]">
          Nessuna richiesta pendente in cui sei nominato.
        </div>
      ) : (
        <div className="space-y-2">
          {pending.map((row) => (
            <div
              key={row.request_id}
              data-testid={`recovery-pending-row-${row.request_id}`}
              className="border hairline p-3 flex items-center justify-between gap-3"
            >
              <div className="min-w-0">
                <div className="font-mono-data text-[12px] text-white truncate">
                  {row.lns}
                </div>
                <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] mt-1">
                  {row.request_id} · aperta da {row.opened_by || "—"}
                </div>
              </div>
              {row.already_contributed ? (
                <span className="font-mono-data text-[10px] text-emerald-300 uppercase tracking-wider">
                  contribuito ✔
                </span>
              ) : (
                <button
                  data-testid={`recovery-contribute-${row.request_id}`}
                  onClick={() => contribute(row)}
                  disabled={busyId === row.request_id}
                  className="px-3 py-1.5 border border-sky-300 text-sky-300 font-mono-data text-[10px] tracking-wider uppercase hover:bg-sky-300/10 disabled:opacity-50"
                >
                  {busyId === row.request_id ? "…" : "Contribuisci"}
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ------------------------------------------------- Reconstruct (requester)
function ReconstructSection({ session, openRequest, clearOpen }) {
  const [data, setData] = useState(null);
  const [recovered, setRecovered] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!openRequest?.request_id) return;
    const id = setInterval(async () => {
      try {
        const r = await api.get(`/keyrecovery/status/${openRequest.request_id}`);
        setData(r.data);
      } catch (_e) { /* ignore */ }
    }, 3000);
    return () => clearInterval(id);
  }, [openRequest?.request_id]);

  if (!openRequest) return null;

  const reconstruct = async () => {
    setBusy(true);
    try {
      // Try localStorage first (LostKeySection persists ticket there so
      // it survives browser restarts), then fall back to sessionStorage.
      const reqId = openRequest?.request_id;
      const myEncSk =
        (reqId && localStorage.getItem(`lattice.recovery.${reqId}.enc_sk`)) ||
        localStorage.getItem("lattice.recovery.enc_sk") ||
        sessionStorage.getItem("lattice.recovery.enc_sk");
      if (!myEncSk) {
        toast.error("Chiave temporanea di recupero perduta · ri-apri la richiesta.");
        return;
      }
      const contribs = (data?.contributions || []).map((c) => ({
        envelope: c.share,
        guardian_lns: c.guardian_lns,
      }));
      if (contribs.length < 2) {
        toast.error("Servono almeno 2 contributi.");
        return;
      }
      const skHex = await recoverSecretKey({
        myEncSkHex: myEncSk,
        contributions: contribs,
      });
      setRecovered(skHex);
      toast.success("Chiave segreta ricostruita localmente · scarica il keypair");
    } catch (e) {
      toast.error("Ricostruzione fallita: " + e.message);
    } finally {
      setBusy(false);
    }
  };

  const downloadKeypair = () => {
    if (!recovered) return;
    // Login.jsx expects `lns_name` + `secret_key_hex`. Generate a fresh
    // X25519 keypair on the spot so the new `.keypair.json` is also
    // compatible with the Pulse/Certify E2E flows that need
    // `enc_public_key_hex` / `enc_secret_key_hex`. After login the
    // browser will re-publish the new `enc_public_key_hex` to the
    // keystore so guardians can encrypt future shares against it.
    const lnsName = session?.lns || session?.lns_name;
    const newEnc = generateEncKeypair();
    const payload = {
      version: 1,
      algorithm: "ML-DSA-65",
      lns_name: lnsName,
      secret_key_hex: recovered,
      enc_public_key_hex: newEnc.enc_public_key_hex,
      enc_secret_key_hex: newEnc.enc_secret_key_hex,
      recovered_at: new Date().toISOString(),
      recovered_from_request_id: openRequest?.request_id,
      note: "Chiave segreta ricomposta via 2-di-3 nominee backup. La X25519 è una NUOVA coppia generata durante il recupero — accedi e ri-pubblica la enc_pk dal pannello Profilo. Custodisci questo file con cura.",
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${lnsName}.recovered.keypair.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const newPk = sessionStorage.getItem("lattice.recovery.enc_pk") || "";

  return (
    <Card
      title="RICOSTRUZIONE · RICHIEDENTE"
      hint="I tuoi nominati stanno contribuendo. Quando ricevi almeno 2/3 contributi, ricostruisci la chiave in locale (WASM Rust shamir_recover)."
      icon={Boxes}
      tone="gold"
      tid="recovery-reconstruct"
    >
      <div className="space-y-3">
        <div className="border hairline px-3 py-2 font-mono-data text-[11px] text-[var(--lattice-text-2)]">
          Request ID · {openRequest.request_id}
        </div>
        <div className="border hairline px-3 py-2">
          <div className="eyebrow text-[10px] mb-1">CHIAVE TEMPORANEA X25519 · PUBBLICATA NELLA RICHIESTA</div>
          <div className="font-mono-data text-[11px] text-[var(--lattice-gold)] break-all">
            {newPk}
          </div>
          <p className="text-[11px] text-[var(--lattice-text-3)] mt-2">
            Questa chiave è già stata inviata al backend insieme alla richiesta:
            i tuoi nominati la prendono automaticamente da
            <code className="text-[var(--lattice-gold)]"> /api/keyrecovery/status</code>.
            Non devi condividerla a mano.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          {(openRequest.guardians || []).map((g) => {
            const c = (data?.contributions || []).find((x) => x.guardian_lns === g);
            return (
              <div key={g} className="border hairline p-2">
                <div className="font-mono-data text-[11px] text-white truncate">{g}</div>
                <div className="font-mono-data text-[10px] mt-1">
                  {c ? (
                    <span className="text-emerald-300">contribuito ✔</span>
                  ) : (
                    <span className="text-[var(--lattice-text-3)]">in attesa…</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        <div className="flex items-center gap-3">
          <button
            data-testid="recovery-reconstruct-btn"
            onClick={reconstruct}
            disabled={busy || (data?.contributions?.length || 0) < 2}
            className="px-4 py-2 border border-[var(--lattice-gold)] text-[var(--lattice-gold)] font-mono-data text-[11px] tracking-[0.18em] uppercase hover:bg-[rgba(212,175,55,0.08)] disabled:opacity-40"
          >
            {busy ? "Ricostruendo…" : `Ricostruisci (${data?.contributions?.length || 0}/2)`}
          </button>
          {recovered && (
            <button
              data-testid="recovery-download-btn"
              onClick={downloadKeypair}
              className="px-4 py-2 border border-emerald-300 text-emerald-300 font-mono-data text-[11px] tracking-[0.18em] uppercase hover:bg-emerald-300/10 flex items-center gap-2"
            >
              <Download size={12} /> Scarica .keypair.json
            </button>
          )}
          <button
            data-testid="recovery-close-btn"
            onClick={clearOpen}
            className="ml-auto font-mono-data text-[10px] uppercase tracking-wider text-[var(--lattice-text-3)] hover:text-white"
          >
            chiudi
          </button>
        </div>
        {recovered && (
          <div className="border hairline bg-[rgba(16,185,129,0.04)] px-3 py-2 font-mono-data text-[11px] text-emerald-300">
            ✔ Secret key ricomposta · {recovered.length / 2} byte
          </div>
        )}
      </div>
    </Card>
  );
}

// ------------------------------------------------------------- Main Page
export default function KeyRecovery() {
  const session = loadSession();
  const params = useParams();
  const [searchParams] = useSearchParams();
  const ticketIdFromUrl = params?.request_id || null;
  const modeFromUrl = searchParams.get("mode"); // "loss" | "theft" | null
  const [employees, setEmployees] = useState([]);
  const [enroll, setEnroll] = useState(null);
  const [openReq, setOpenReq] = useState(null);
  const [tenantInfo, setTenantInfo] = useState(null);

  const reload = async () => {
    if (!session?.lns) return;
    try {
      const r = await api.get(`/keyrecovery/enrollment/${encodeURIComponent(session.lns)}`);
      setEnroll(r.data);
    } catch (_e) { /* ignore */ }
  };

  useEffect(() => {
    if (!session?.tenant_id) return;
    api
      .get(`/tenants/${session.tenant_id}/employees`)
      .then((r) => {
        const list = Array.isArray(r.data)
          ? r.data
          : (r.data?.employees || r.data?.items || []);
        setEmployees(list);
      })
      .catch(() => setEmployees([]));
    api
      .get(`/tenants/${session.tenant_id}`)
      .then((r) => setTenantInfo(r.data))
      .catch(() => setTenantInfo(null));
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.tenant_id, session?.lns]);

  if (!session?.lns) {
    return <LostKeySection initialRequestId={ticketIdFromUrl} initialMode={modeFromUrl} />;
  }
  // Founder check (gating only the EnrollSection, not the whole page)
  const isTenantFounder = !session.tenant_id ||
    !tenantInfo ||
    (tenantInfo.admin_lns && tenantInfo.admin_lns === session.lns);

  return (
    <div className="space-y-8 max-w-5xl" data-testid="recovery-page">
      <div>
        <div className="eyebrow flex items-center gap-2 mb-1">
          <ShieldCheck size={11} className="text-[var(--lattice-gold)]" /> KEY RECOVERY · 2-DI-3
        </div>
        <h1 className="font-display text-4xl text-white">Recupero chiavi LNS</h1>
        <p className="text-[13px] text-[var(--lattice-text-3)] mt-2 leading-relaxed max-w-3xl">
          Backup distribuito della tua chiave segreta ML-DSA-65: 3 nominati, soglia 2.
          Lo splitting avviene in <strong className="text-white">Rust→WASM</strong> (Shamir
          GF(256)) interamente nel browser. Il server vede solo 3 ciphertext + 3 fingerprint
          SHA3-256 (questi ultimi vengono notarizzati on-chain). Nessuna parte della tua
          chiave segreta esce mai dal tuo dispositivo.
        </p>
      </div>

      {/* Pending requests where I am a nominated guardian — visible to ALL
          authenticated employees (admin or operator), even non-founders. */}
      <PendingAsGuardianSection session={session} />

      {/* Enroll section: founder-only */}
      {session.role === "admin" && isTenantFounder && (
        <EnrollSection
          session={session}
          employees={employees}
          currentEnrollment={enroll}
          reload={reload}
        />
      )}
      {session.role === "admin" && session.tenant_id && tenantInfo && !isTenantFounder && (
        <div className="surface-elev border hairline p-6 max-w-2xl" data-testid="recovery-not-founder">
          <div className="flex items-start gap-3">
            <AlertTriangle size={16} className="text-amber-300 mt-1" />
            <div>
              <div className="eyebrow text-[var(--lattice-gold)] mb-1">SETUP NOMINATI · RISERVATO AL FONDATORE</div>
              <p className="text-[13px] text-[var(--lattice-text-2)] leading-relaxed">
                Solo l&apos;admin che ha registrato originariamente <strong className="text-white">{tenantInfo.name}</strong> può
                scegliere i 3 nominati aziendali. Fondatore attuale:{" "}
                <strong className="text-white font-mono-data text-[12px]" data-testid="recovery-founder-lns">
                  {tenantInfo.admin_lns}
                </strong>.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Auto-enroll per i dipendenti non-fondatori che ancora non hanno
          un backup personale: usa la policy aziendale (3 guardiani scelti
          dal fondatore) per cifrare i 3 share Shamir della propria SK. */}
      {session.tenant_id && !isTenantFounder && (
        <EmployeeAutoEnrollSection
          session={session}
          currentEnrollment={enroll}
          reload={reload}
        />
      )}

      <OpenRequestSection
        session={session}
        currentEnrollment={enroll}
        onOpened={(d) => setOpenReq(d)}
      />

      {openReq && (
        <ReconstructSection
          session={session}
          openRequest={openReq}
          clearOpen={() => setOpenReq(null)}
        />
      )}

      <div className="surface-elev border hairline p-5">
        <div className="eyebrow mb-2 flex items-center gap-2">
          <Users size={11} className="text-[var(--lattice-gold)]" /> COME FUNZIONA · IN SINTESI
        </div>
        <ol className="space-y-2 text-[12px] text-[var(--lattice-text-2)] leading-relaxed list-decimal pl-5">
          <li>
            La tua chiave segreta (4032 byte ML-DSA-65) viene divisa via
            <strong className="text-white"> Shamir GF(256)</strong> in 3 frammenti tali che
            qualsiasi 2 di essi la ricompongono.
          </li>
          <li>
            Ogni frammento viene sigillato in locale con la chiave X25519 del rispettivo
            nominato (ECIES + AES-256-GCM).
          </li>
          <li>
            Il server riceve 3 ciphertext opachi + 3 fingerprint SHA3-256. Solo i fingerprint
            (no plaintext, no ciphertext) finiscono on-chain come TX <code>KeyShareEnroll</code>.
          </li>
          <li>
            In recupero: 2 dei 3 nominati ri-sigillano il loro frammento per la nuova chiave
            X25519 del richiedente, e il browser ricompone la sk con
            <strong className="text-white"> Rust→WASM shamir_recover</strong>.
          </li>
        </ol>
      </div>
    </div>
  );
}

// ----------------------- Lost-key public entry point (no session)

/**
 * Card "stampabile / salvabile" del ticket di recovery.
 * - QR code che contiene un JSON con request_id + enc_sk_hex + lns.
 *   Scansionabile da qualsiasi smartphone per ricostruire il ticket
 *   anche se si perde il PC originale.
 * - Bottone "Stampa" — apre il dialog di stampa con un layout pulito.
 * - Bottone "Salva su disco" — scarica un file `.recovery-ticket.json`
 *   da archiviare offline (USB, cassaforte, drive aziendale).
 * - Bottone "Copia URL" — il vecchio bookmark URL.
 *
 * ⚠️ Il JSON nel QR e nel file contiene la X25519 secret-key TEMPORANEA
 * di recovery in chiaro. NON è la SK ML-DSA-65 originale. Permette solo
 * di completare QUESTA richiesta. Va comunque custodita finché 2/3
 * nominati non hanno contribuito.
 */
function RecoveryTicketCard({ requestId, lns }) {
  const encSk = typeof window !== "undefined"
    ? localStorage.getItem(`lattice.recovery.${requestId}.enc_sk`)
    : null;
  const encPk = typeof window !== "undefined"
    ? localStorage.getItem(`lattice.recovery.${requestId}.enc_pk`)
    : null;
  const openedAt = typeof window !== "undefined"
    ? localStorage.getItem(`lattice.recovery.${requestId}.opened_at`)
    : null;
  const origin = typeof window !== "undefined" ? window.location.origin : "";

  const ticketJson = useMemo(() => ({
    kind: "lattice-recovery-ticket",
    version: 1,
    request_id: requestId,
    lns,
    enc_secret_key_hex: encSk,
    enc_public_key_hex: encPk,
    opened_at: openedAt,
    resume_url: `${origin}/recovery/ticket/${requestId}`,
    note: "Custodisci offline. NON è la chiave ML-DSA originale. Permette solo il completamento di questa richiesta di recovery (2-di-3).",
  }), [requestId, lns, encSk, encPk, openedAt, origin]);

  const qrPayload = JSON.stringify(ticketJson);
  const ticketUrl = `${origin}/recovery/ticket/${requestId}`;

  const downloadFile = () => {
    const blob = new Blob([JSON.stringify(ticketJson, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `lattice-recovery-ticket-${requestId.slice(0, 12)}.json`;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success("Ticket scaricato · custodisci offline");
  };

  const copyUrl = () => {
    navigator.clipboard.writeText(ticketUrl);
    toast.success("URL copiato negli appunti");
  };

  const print = () => {
    const w = window.open("", "_blank", "width=720,height=900");
    if (!w) { toast.error("Popup bloccato — abilita popup per stampare"); return; }
    w.document.write(`<!doctype html><html lang="it"><head><meta charset="utf-8"><title>Recovery Ticket · ${lns}</title>
<style>
body { font-family: ui-sans-serif, system-ui, -apple-system, sans-serif; background:#fff; color:#0a1020; margin:0; padding:40px; }
.box { max-width:560px; margin:0 auto; border:2px solid #0a1020; padding:32px; }
h1 { font-size:22px; margin:0 0 4px; letter-spacing:0.02em; }
.sub { color:#7a8190; font-size:11px; text-transform:uppercase; letter-spacing:0.18em; margin-bottom:24px; }
.qr { display:flex; justify-content:center; padding:20px 0; }
table { width:100%; border-collapse:collapse; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size:11px; }
td { padding:6px 4px; border-bottom:1px solid #e5e7eb; vertical-align:top; }
td.k { color:#7a8190; text-transform:uppercase; letter-spacing:0.1em; width:170px; }
td.v { word-break:break-all; }
.warn { margin-top:24px; padding:12px 14px; border:1.5px solid #c2410c; background:#fff7ed; color:#7c2d12; font-size:11px; line-height:1.55; }
.foot { margin-top:24px; font-family: ui-monospace, monospace; font-size:9px; color:#7a8190; text-align:center; }
</style></head><body>
<div class="box">
<h1>LATTICE · Ticket di recovery chiave</h1>
<div class="sub">2-di-3 Shamir · ML-DSA-65 / X25519</div>
<div class="qr" id="qrslot"></div>
<table>
  <tr><td class="k">LNS</td><td class="v">${lns}</td></tr>
  <tr><td class="k">Request ID</td><td class="v">${requestId}</td></tr>
  <tr><td class="k">Aperta il</td><td class="v">${openedAt || "—"}</td></tr>
  <tr><td class="k">Resume URL</td><td class="v">${ticketUrl}</td></tr>
  <tr><td class="k">X25519 enc_pk</td><td class="v">${encPk || "—"}</td></tr>
</table>
<div class="warn">
  ⚠️ <strong>Custodisci offline.</strong> Questo foglio + il QR consentono di completare
  la richiesta di recovery quando 2 dei 3 nominati avranno contribuito.
  Non contiene la chiave ML-DSA originale, ma sì la chiave X25519 temporanea
  necessaria a decrittare gli share. <strong>Chi ha questo foglio può intercettare
  il recovery</strong>. Stampato il ${new Date().toLocaleString("it-IT")}.
</div>
<div class="foot">lattice.network · sovereign post-quantum messaging</div>
</div>
<script>
  // Render QR inline via library data URL
  const slot = document.getElementById("qrslot");
  slot.innerHTML = ${JSON.stringify(`<img src="" id="qrimg" alt="QR ticket" style="width:240px;height:240px;border:1px solid #ccc"/>`)};
  // The parent will inject the QR image
</script>
</body></html>`);
    // Inject QR as PNG from parent
    const svg = document.querySelector(`[data-recovery-qr="${requestId}"]`);
    if (svg) {
      const xml = new XMLSerializer().serializeToString(svg);
      const dataUrl = `data:image/svg+xml;utf8,${encodeURIComponent(xml)}`;
      w.onload = () => {
        const img = w.document.getElementById("qrimg");
        if (img) img.src = dataUrl;
        setTimeout(() => w.print(), 350);
      };
    } else {
      setTimeout(() => w.print(), 350);
    }
    w.document.close();
  };

  if (!encSk) {
    return (
      <div className="font-mono-data text-[11px] text-rose-300">
        Ticket non disponibile · enc_sk non trovata in localStorage.
      </div>
    );
  }

  return (
    <div className="border hairline-strong p-5 bg-black/30" data-testid="recovery-ticket-card">
      <div className="eyebrow text-[10px] text-amber-300 mb-3 flex items-center gap-2">
        <QrCode size={11} /> SALVA / STAMPA / TRASFERISCI IL TICKET DI RECOVERY
      </div>
      <div className="grid grid-cols-1 md:grid-cols-[240px_1fr] gap-5">
        <div className="flex flex-col items-center gap-2">
          <div className="bg-white p-3 border-2 border-amber-300" data-testid="recovery-qr-wrap">
            <QRCodeSVG
              value={qrPayload}
              size={210}
              level="M"
              includeMargin={false}
              data-recovery-qr={requestId}
            />
          </div>
          <div className="font-mono-data text-[9px] text-[var(--lattice-text-3)] text-center max-w-[210px] leading-tight">
            Scansiona da smartphone per importare il ticket su un altro device
          </div>
        </div>
        <div className="space-y-3">
          <p className="text-[12px] text-[var(--lattice-text-2)] leading-relaxed">
            Scegli <strong className="text-white">almeno UNA</strong> di queste opzioni
            per non perdere la possibilità di recuperare la tua chiave:
          </p>
          <div className="space-y-2">
            <button
              onClick={downloadFile}
              data-testid="recovery-ticket-download"
              className="w-full flex items-center gap-3 px-4 py-2.5 border hairline hover:border-[var(--lattice-gold)] text-left"
            >
              <Save size={14} className="text-[var(--lattice-gold)]" />
              <div className="flex-1">
                <div className="font-mono-data text-[11px] text-white uppercase tracking-wider">Salva su disco</div>
                <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] mt-0.5">File .json · usb / cloud privato / cassaforte</div>
              </div>
            </button>
            <button
              onClick={print}
              data-testid="recovery-ticket-print"
              className="w-full flex items-center gap-3 px-4 py-2.5 border hairline hover:border-[var(--lattice-gold)] text-left"
            >
              <Printer size={14} className="text-[var(--lattice-gold)]" />
              <div className="flex-1">
                <div className="font-mono-data text-[11px] text-white uppercase tracking-wider">Stampa foglio con QR</div>
                <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] mt-0.5">A4 · da archiviare offline (HR / cassaforte fisica)</div>
              </div>
            </button>
            <button
              onClick={copyUrl}
              data-testid="recovery-ticket-copy-url"
              className="w-full flex items-center gap-3 px-4 py-2.5 border hairline hover:border-[var(--lattice-gold)] text-left"
            >
              <KeyRound size={14} className="text-[var(--lattice-gold)]" />
              <div className="flex-1">
                <div className="font-mono-data text-[11px] text-white uppercase tracking-wider">Copia URL bookmark</div>
                <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] mt-0.5 break-all">{ticketUrl}</div>
              </div>
            </button>
          </div>
          <div className="border border-rose-500/40 bg-rose-500/5 px-3 py-2 font-mono-data text-[10px] text-rose-300 leading-relaxed">
            ⚠ Il file/QR/foglio contiene la X25519 sk TEMPORANEA in chiaro. Chi
            ne entra in possesso può intercettare questa specifica richiesta di
            recovery. Custodisci come una chiave fisica.
          </div>
        </div>
      </div>
    </div>
  );
}

function TicketImporter({ onImport }) {
  const [err, setErr] = useState("");
  const handleFile = async (e) => {
    setErr("");
    const f = e.target.files?.[0];
    if (!f) return;
    try {
      const text = await f.text();
      const parsed = JSON.parse(text);
      if (parsed.kind !== "lattice-recovery-ticket" || !parsed.request_id || !parsed.enc_secret_key_hex || !parsed.lns) {
        throw new Error("Formato non valido: atteso lattice-recovery-ticket v1.");
      }
      onImport(parsed);
    } catch (er) {
      setErr(er.message);
      toast.error(er.message);
    }
  };
  return (
    <div className="surface-elev border hairline-strong relative" data-testid="ticket-importer">
      <div className="absolute top-0 left-0 right-0 h-px gold-line opacity-40" />
      <div className="px-6 py-5">
        <div className="eyebrow text-[10px] mb-2 flex items-center gap-2"><QrCode size={11} className="text-[var(--lattice-gold)]" /> HAI UN TICKET GIÀ APERTO?</div>
        <p className="text-[12px] text-[var(--lattice-text-2)] mb-3 leading-relaxed">
          Se avevi salvato un ticket da un altro dispositivo (file
          <code className="text-[var(--lattice-gold)]"> .recovery-ticket.json</code> o stampa),
          caricalo qui per riprendere la richiesta esistente invece di aprirne una nuova.
        </p>
        <label className="block">
          <div className="border hairline px-4 py-3 hover:border-[var(--lattice-gold)] cursor-pointer">
            <div className="font-mono-data text-[11px] text-white flex items-center gap-2">
              <Save size={12} /> Carica file .recovery-ticket.json
            </div>
            <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] mt-1">
              (per QR: scansiona col cellulare e segui il link incluso)
            </div>
          </div>
          <input type="file" accept=".json,application/json" onChange={handleFile} className="hidden" data-testid="ticket-importer-input" />
        </label>
        {err && (
          <div className="mt-2 font-mono-data text-[11px] text-rose-300" data-testid="ticket-importer-error">{err}</div>
        )}
      </div>
    </div>
  );
}

function LostKeySection({ initialRequestId = null, initialMode = null } = {}) {
  // Iter_53: two-mode intro screen.
  //   "loss"  → existing 2-of-3 Shamir flow (same SK recovered, history intact)
  //   "theft" → instructions to contact tenant founder for revoke + re-register
  // The mode can be preselected via URL (?mode=loss|theft) when coming from
  // the Login page CTA so the user does NOT see the chooser again.
  const [mode, setMode] = useState(initialMode); // null | "loss" | "theft"
  const [lns, setLns] = useState("");
  const [busy, setBusy] = useState(false);
  const [opened, setOpened] = useState(null);
  const [err, setErr] = useState("");

  // On mount: if we were given a ticket ID via URL OR if a previous
  // recovery session is saved in localStorage, restore it.
  useEffect(() => {
    const reqId = initialRequestId || localStorage.getItem("lattice.recovery.latest");
    if (!reqId) return;
    const savedLns = localStorage.getItem(`lattice.recovery.${reqId}.lns`);
    const savedEncSk = localStorage.getItem(`lattice.recovery.${reqId}.enc_sk`);
    if (!savedLns || !savedEncSk) return;
    setOpened({ request_id: reqId, lns: savedLns });
  }, [initialRequestId]);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      const newEnc = generateEncKeypair();
      // Persist in localStorage (not sessionStorage) so the recovery
      // ticket survives browser close. The user MUST keep this device
      // until 2/3 guardians contribute and the SK is reconstructed.
      // Keyed by request_id so the user can have multiple recovery
      // tickets in parallel (different LNS / devices).
      const lnsClean = lns.trim().toLowerCase();
      const r = await api.post("/keyrecovery/request", {
        lns: lnsClean,
        reason: "lost_keypair",
        requester_enc_pk_hex: newEnc.enc_public_key_hex,
      });
      const reqId = r.data.request_id;
      localStorage.setItem(`lattice.recovery.${reqId}.enc_sk`, newEnc.enc_secret_key_hex);
      localStorage.setItem(`lattice.recovery.${reqId}.enc_pk`, newEnc.enc_public_key_hex);
      localStorage.setItem(`lattice.recovery.${reqId}.lns`, lnsClean);
      localStorage.setItem(`lattice.recovery.${reqId}.opened_at`, new Date().toISOString());
      // Also keep a "latest" pointer for the simple /recovery (no params) flow.
      localStorage.setItem("lattice.recovery.latest", reqId);
      setOpened({ ...r.data, lns: lnsClean });
      toast.success(`Richiesta aperta · ID ${reqId}`);
    } catch (e2) {
      setErr(e2?.response?.data?.detail || e2.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6 max-w-2xl" data-testid="recovery-lost-key">
      <div>
        <div className="eyebrow flex items-center gap-2 text-[var(--lattice-gold)]">
          <KeyRound size={11} /> RECUPERO CHIAVI · HAI PERSO IL .keypair.json
        </div>
        <h1 className="font-display text-4xl text-white mt-2">Apri una richiesta di recupero</h1>
        <p className="text-[13px] text-[var(--lattice-text-2)] mt-3 leading-relaxed">
          Se hai perso il tuo file <code>.keypair.json</code> e <strong className="text-white">non
          puoi più fare login</strong>, inserisci qui sotto il tuo identificativo LNS.
          La richiesta sarà inviata ai 3 nominati scelti dal fondatore della tua azienda.
          Quando 2 di loro contribuiscono, potrai ricostruire la chiave in questa stessa
          pagina senza dover ri-effettuare login.
        </p>
      </div>

      {!opened && !mode && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="recovery-mode-chooser">
          <button
            onClick={() => setMode("loss")}
            data-testid="recovery-mode-loss"
            className="surface-elev border hairline-strong p-6 text-left hover:border-sky-300 transition-colors group"
          >
            <div className="text-3xl mb-3">🔄</div>
            <div className="font-display text-xl text-white mb-2">Ho perso la chiave</div>
            <div className="text-[12px] text-[var(--lattice-text-2)] leading-relaxed">
              PC rotto, file `.keypair.json` cancellato per errore, smartphone perso —
              ma <strong className="text-white">nessuno ha rubato la chiave</strong>.
              I tuoi 3 nominati ricostruiscono <strong className="text-white">la stessa SK</strong>:
              mantieni storia mail/Pulse, stesso LNS.
            </div>
            <div className="font-mono-data text-[10px] text-sky-300 mt-4 group-hover:underline">RECOVERY 2-DI-3 →</div>
          </button>
          <button
            onClick={() => setMode("theft")}
            data-testid="recovery-mode-theft"
            className="surface-elev border hairline-strong p-6 text-left hover:border-rose-400 transition-colors group"
          >
            <div className="text-3xl mb-3">🚨</div>
            <div className="font-display text-xl text-white mb-2">Mi hanno rubato la chiave</div>
            <div className="text-[12px] text-[var(--lattice-text-2)] leading-relaxed">
              Sospetto compromissione (phishing, dispositivo rubato, hack).
              Il <strong className="text-white">fondatore revoca la tua LNS on-chain</strong> e
              ricevi una <strong className="text-white">nuova identità</strong>.
              Perdi le mail E2E cifrate per la vecchia chiave (acceptable trade-off di sicurezza).
            </div>
            <div className="font-mono-data text-[10px] text-rose-300 mt-4 group-hover:underline">REVOCA + NUOVO ACCOUNT →</div>
          </button>
        </div>
      )}

      {!opened && mode === "theft" && (
        <div className="surface-elev border border-rose-400/40 bg-rose-500/5 px-6 py-5" data-testid="recovery-theft-instructions">
          <div className="eyebrow text-rose-300 mb-2 flex items-center gap-2">
            <AlertTriangle size={11} /> CHIAVE COMPROMESSA · CONTATTA IL FONDATORE
          </div>
          <ol className="text-[13px] text-[var(--lattice-text-2)] space-y-2 list-decimal pl-5 leading-relaxed">
            <li>
              Contatta <strong className="text-white">subito</strong> il fondatore della tua azienda
              tramite un canale che non usa Lattice (telefono / di persona / email aziendale).
              Comunica: il tuo LNS e che la chiave è compromessa.
            </li>
            <li>
              Il fondatore va su <code className="text-[var(--lattice-gold)]">/dipendenti</code> →
              clicca il bottone rosso <strong className="text-white">"🚨 Revoca compromessa"</strong>{" "}
              accanto al tuo nome → conferma.
            </li>
            <li>
              La tua identità viene <strong className="text-white">marcata REVOKED on-chain</strong>:
              il ladro non può più usare la chiave per inviare mail/Pulse a tuo nome.
            </li>
            <li>
              Il fondatore ti registra come nuovo dipendente (es. con suffisso{" "}
              <code>_v2</code>) da <code className="text-[var(--lattice-gold)]">/dipendenti</code> →
              scarichi il nuovo <code>.keypair.json</code> e ricominci.
            </li>
            <li>
              Le mail Certify ricevute prima della revoca <strong className="text-rose-300">rimangono
              illeggibili</strong> (erano cifrate con la pk compromessa, e quella sk va distrutta
              per evitare che il ladro le decritti). Le mail inviate restano on-chain come storia
              verificabile.
            </li>
          </ol>
          <button
            onClick={() => setMode(null)}
            className="mt-4 px-3 py-1.5 border hairline text-[var(--lattice-text-2)] font-mono-data text-[10px] uppercase tracking-wider hover:text-white"
            data-testid="recovery-theft-back"
          >← Torna alla scelta</button>
        </div>
      )}

      {!opened && mode === "loss" && (
        <>
          <button
            onClick={() => setMode(null)}
            className="px-3 py-1.5 border hairline text-[var(--lattice-text-3)] font-mono-data text-[10px] uppercase tracking-wider hover:text-white"
            data-testid="recovery-loss-back"
          >← Torna alla scelta</button>
          <form onSubmit={submit} className="surface-elev border hairline relative" data-testid="recovery-lost-form">
            <div className="absolute top-0 left-0 right-0 h-px gold-line opacity-60" />
            <div className="px-6 py-5 space-y-4">
              <div>
                <label className="eyebrow text-[10px] block mb-2">IL TUO LNS (es. mario.acme.lns)</label>
                <input
                  type="text"
                  value={lns}
                  onChange={(ev) => setLns(ev.target.value)}
                  placeholder="nome.cognome.azienda.lns"
                  className="w-full bg-transparent border hairline px-3 py-2 font-mono-data text-[13px] text-white outline-none focus:border-[var(--lattice-gold)]"
                  data-testid="recovery-lost-lns-input"
                  autoFocus
                  required
                />
              </div>
              {err && (
                <div className="border border-rose-500/40 bg-rose-500/5 px-3 py-2 font-mono-data text-[11px] text-rose-300" data-testid="recovery-lost-error">
                  {err}
                </div>
              )}
              <button
                type="submit"
                disabled={busy || !lns.trim()}
                data-testid="recovery-lost-submit"
                className="px-4 py-2 border border-sky-300 text-sky-300 font-mono-data text-[11px] tracking-[0.18em] uppercase hover:bg-sky-300/10 disabled:opacity-50"
              >
                {busy ? "Apertura…" : "Apri richiesta 2-di-3 →"}
            </button>
          </div>
        </form>
        <TicketImporter onImport={(t) => {
          // Restore an already-opened ticket from a previously saved JSON or QR.
          localStorage.setItem(`lattice.recovery.${t.request_id}.enc_sk`, t.enc_secret_key_hex);
          localStorage.setItem(`lattice.recovery.${t.request_id}.enc_pk`, t.enc_public_key_hex || "");
          localStorage.setItem(`lattice.recovery.${t.request_id}.lns`, t.lns);
          localStorage.setItem(`lattice.recovery.${t.request_id}.opened_at`, t.opened_at || new Date().toISOString());
          localStorage.setItem("lattice.recovery.latest", t.request_id);
          setOpened({ request_id: t.request_id, lns: t.lns });
          toast.success("Ticket importato · ripresa del recupero");
        }} />
        </>
      )}

      {opened && (
        <div className="surface-elev border hairline relative" data-testid="recovery-lost-opened">
          <div className="absolute top-0 left-0 right-0 h-px gold-line" />
          <div className="px-6 py-5 space-y-3 font-mono-data text-[12px]">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="eyebrow text-emerald-300 flex items-center gap-2">
                <ShieldCheck size={11} /> RICHIESTA APERTA ON-CHAIN
              </div>
              <button
                onClick={() => {
                  const rid = opened.request_id;
                  if (!window.confirm(
                    "Sei sicuro di voler scartare questo ticket? La chiave temporanea verrà cancellata e dovrai aprire una nuova richiesta da zero. Se i nominati hanno già contribuito, perderai i loro share.",
                  )) return;
                  ["enc_sk", "enc_pk", "lns", "opened_at"].forEach((k) => {
                    localStorage.removeItem(`lattice.recovery.${rid}.${k}`);
                  });
                  if (localStorage.getItem("lattice.recovery.latest") === rid) {
                    localStorage.removeItem("lattice.recovery.latest");
                  }
                  setOpened(null);
                  setLns("");
                  toast.success("Ticket scartato · puoi aprire una nuova richiesta");
                }}
                data-testid="recovery-reset-ticket"
                className="px-3 py-1.5 border border-rose-400/50 text-rose-300 font-mono-data text-[10px] uppercase tracking-[0.15em] hover:bg-rose-400/10"
              >
                ↺ Scarta e ricomincia
              </button>
            </div>
            <div><span className="text-[var(--lattice-text-3)]">request_id:</span> <span className="text-white" data-testid="recovery-lost-request-id">{opened.request_id}</span></div>
            {opened.guardians && (
              <div><span className="text-[var(--lattice-text-3)]">nominati:</span> <span className="text-white">{(opened.guardians || []).join(", ")}</span></div>
            )}
            {opened.tx_id && (
              <div className="border border-emerald-300/40 bg-emerald-300/5 px-3 py-3 mt-2" data-testid="recovery-onchain-receipt">
                <div className="eyebrow text-[10px] text-emerald-300 mb-2 flex items-center gap-2">
                  <ShieldCheck size={11} /> NOTARIZZATA ON-CHAIN · FIRMA ML-DSA-65
                </div>
                <div className="space-y-1.5">
                  <div>
                    <span className="text-[var(--lattice-text-3)]">tx_id:</span>{" "}
                    <a
                      href={`/explorer/tx/${opened.tx_id}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[var(--lattice-gold)] hover:underline break-all"
                      data-testid="recovery-onchain-tx-link"
                    >{opened.tx_id} ↗</a>
                  </div>
                  <div>
                    <span className="text-[var(--lattice-text-3)]">block:</span>{" "}
                    <a
                      href={`/explorer/block/${opened.block_index}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[var(--lattice-gold)] hover:underline"
                      data-testid="recovery-onchain-block-link"
                    >#{opened.block_index} ↗</a>
                  </div>
                  {opened.doc_hash && (
                    <div>
                      <span className="text-[var(--lattice-text-3)]">doc_hash:</span>{" "}
                      <span className="text-white break-all">{opened.doc_hash.slice(0, 32)}…{opened.doc_hash.slice(-8)}</span>
                    </div>
                  )}
                </div>
                <div className="text-[10px] text-[var(--lattice-text-3)] mt-2 leading-relaxed">
                  Chiunque (anche senza login) può aprire il link Explorer per verificare matematicamente
                  che questa richiesta è stata firmata dalla tua identità (o dal gateway aziendale) on-chain.
                </div>
              </div>
            )}
            <div className="border border-amber-300/40 bg-amber-300/5 px-3 py-3 mt-3">
              <div className="text-amber-300 text-[11px] uppercase tracking-[0.18em] mb-2">⚠ NON PERDERE QUESTO TICKET</div>
              <div className="text-[11px] text-[var(--lattice-text-2)] leading-relaxed">
                Per evitare di perdere la possibilità di recupero se cambi PC o cancelli il browser,
                <strong className="text-white"> scegli almeno una delle 3 opzioni qui sotto</strong>.
                La chiave temporanea X25519 vive solo in <strong className="text-white">questo dispositivo</strong>
                {" "}finché non la esporti.
              </div>
            </div>
            <RecoveryTicketCard requestId={opened.request_id} lns={opened.lns || localStorage.getItem(`lattice.recovery.${opened.request_id}.lns`)} />
            <div className="text-[11px] text-[var(--lattice-text-2)] mt-3 leading-relaxed">
              Avvisa i 3 nominati che possono contribuire dalla loro pagina{" "}
              <strong className="text-white">/recovery</strong>. Quando 2 di loro avranno
              risposto, qui sotto comparirà il bottone per ricostruire la chiave.
            </div>
            <FakeReconstructPoller requestId={opened.request_id} lns={opened.lns || localStorage.getItem(`lattice.recovery.${opened.request_id}.lns`)} />
          </div>
        </div>
      )}
    </div>
  );
}

function FakeReconstructPoller({ requestId, lns }) {
  // Lightweight inline poller for the unauthenticated path; reuses the
  // ReconstructSection but drives it with a fake `session` to avoid auth
  // assumptions inside that component.
  const fakeSession = { lns };
  return (
    <ReconstructSection
      session={fakeSession}
      openRequest={{ request_id: requestId }}
      clearOpen={() => { /* noop */ }}
    />
  );
}
