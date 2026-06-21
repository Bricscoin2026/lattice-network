import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { pqcSignChallenge, pqcSignMessage, saveSession } from "@/lib/pqcAuth";
import { Shield, Upload, KeyRound, AlertCircle, Check } from "lucide-react";
import { toast } from "sonner";

export default function Login() {
  const navigate = useNavigate();
  const [keyfile, setKeyfile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [step, setStep] = useState("upload"); // upload → signing → done

  const handleFile = (e) => {
    setError("");
    const f = e.target.files?.[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const parsed = JSON.parse(reader.result);
        // Accept both `lns_name` (current) and legacy `lns` field name
        // so old downloads keep working.
        if (!parsed.lns_name && parsed.lns) parsed.lns_name = parsed.lns;
        if (!parsed.lns_name || !parsed.secret_key_hex) {
          setError("File chiave malformato: mancano lns_name o secret_key_hex");
          return;
        }
        setKeyfile(parsed);
        toast.success(`Chiave caricata · ${parsed.lns_name}`);
      } catch (err) {
        setError("Impossibile leggere il file (JSON non valido)");
      }
    };
    reader.readAsText(f);
  };

  const doLogin = async () => {
    if (!keyfile) return;
    setBusy(true);
    setError("");
    try {
      setStep("signing");
      // 1. Ask the backend for a fresh nonce.
      const chal = await api.post("/auth/challenge", { lns_name: keyfile.lns_name });
      // 2. Sign the nonce locally with ML-DSA-65 (client-side only).
      const sigHex = pqcSignChallenge(keyfile.secret_key_hex, chal.data.nonce_hex);
      // 3. Send the signature, receive a JWT.
      const ver = await api.post("/auth/verify", {
        challenge_id: chal.data.challenge_id,
        signature_hex: sigHex,
      });
      saveSession(ver.data.token, {
        lns: ver.data.lns,
        tenant_id: ver.data.tenant_id,
        role: ver.data.role,
        expires_in_seconds: ver.data.expires_in_seconds,
        logged_in_at: new Date().toISOString(),
      });
      // Keep the secret key in *sessionStorage* (cleared on tab close) so
      // we can sign delivery receipts without re-prompting for the keypair.
      // The sk NEVER touches the network — only used by ml_dsa65.sign() in-browser.
      try { sessionStorage.setItem("lattice.sk", keyfile.secret_key_hex); } catch {}
      // X25519 secret key (only present if the keypair was issued with the
      // post-2026 format). Needed by /recovery to decrypt the user's Shamir
      // share when acting as guardian. Stays in sessionStorage only.
      if (keyfile.enc_secret_key_hex) {
        try {
          sessionStorage.setItem("lattice.enc_sk", keyfile.enc_secret_key_hex);
        } catch {}
      }

      // Auto-rotate enc_pk on the server if this keypair was just produced
      // by a 2-of-3 recovery (post-2026 .keypair.json carries
      // `recovered_from_request_id`). The reconstructed file holds a FRESH
      // X25519 keypair while the keystore still has the OLD enc_pk; without
      // this rotation, future Shamir shares destined to the user would be
      // encrypted to the OLD enc_pk that no one can decrypt.
      if (
        keyfile.recovered_from_request_id &&
        keyfile.enc_public_key_hex &&
        keyfile.secret_key_hex
      ) {
        try {
          const nonce = Math.random().toString(36).slice(2) + Date.now().toString(36);
          const msg = `rotate-enc-pk|${keyfile.lns_name}|${keyfile.enc_public_key_hex}|${nonce}`;
          const sigHex = pqcSignMessage(msg);
          if (!sigHex) throw new Error("ML-DSA SK not available in sessionStorage");
          await api.post("/lns/rotate-enc-pk", {
            lns_name: keyfile.lns_name,
            new_enc_public_key_hex: keyfile.enc_public_key_hex,
            nonce,
            signature_hex: sigHex,
            reason: "post_recovery",
          });
          toast.success("Chiave X25519 ruotata on-chain · setup completato");
          // Cleanup: il ticket di recovery non serve più, eliminalo dal
          // localStorage per non bloccare richieste future per la stessa LNS.
          const rid = keyfile.recovered_from_request_id;
          ["enc_sk", "enc_pk", "lns", "opened_at"].forEach((k) => {
            localStorage.removeItem(`lattice.recovery.${rid}.${k}`);
          });
          if (localStorage.getItem("lattice.recovery.latest") === rid) {
            localStorage.removeItem("lattice.recovery.latest");
          }
        } catch (rotErr) {
          // Non-fatal: login already succeeded. Surface as a warning so the
          // user knows future Shamir share inbound still uses the old enc_pk.
          // eslint-disable-next-line no-console
          console.warn("enc_pk auto-rotation failed:", rotErr);
          toast.warning("Login OK ma la rotazione enc_pk è fallita — ritenta dal pannello Profilo.");
        }
      }
      toast.success(`Login riuscito · ruolo ${ver.data.role}`);
      setStep("done");
      setTimeout(() => navigate("/dashboard"), 600);
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message || "Login fallito";
      setError(msg);
      setStep("upload");
      toast.error(msg);
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-6 py-12" style={{ background: "var(--lattice-bg)" }}>
      <div className="w-full max-w-lg surface-elev relative" data-testid="login-card">
        <div className="absolute top-0 left-0 right-0 h-px gold-line" />
        <div className="px-8 py-8 space-y-6">
          <div className="flex items-center gap-3">
            <Shield size={28} className="text-[var(--lattice-gold)]" />
            <div>
              <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] uppercase tracking-[0.22em]">Lattice Network · Sovereign Identity</div>
              <h1 className="font-display text-3xl text-white">Accedi</h1>
            </div>
          </div>
          <p className="text-[13px] text-[var(--lattice-text-3)] leading-relaxed">
            Accedi alla tua rete aziendale privata. La chiave segreta <strong className="text-[var(--lattice-gold)]">non lascia mai il tuo browser</strong> — viene usata solo per dimostrare la tua identità a Lattice e firmare ciò che fai. Carica il file <code className="text-[var(--lattice-gold)]">.keypair.json</code> ricevuto al momento dell'onboarding.
          </p>

          {/* Upload */}
          <label className="block">
            <div className="border hairline-strong px-5 py-6 surface text-center cursor-pointer hover:border-[var(--lattice-gold)]" data-testid="login-upload-zone">
              <Upload size={20} className="mx-auto text-[var(--lattice-gold)]" />
              <div className="font-mono-data text-[11px] text-white mt-3">
                {keyfile ? "Cambia file chiave" : "Carica file .keypair.json"}
              </div>
              <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] mt-1">Click o drag-and-drop</div>
            </div>
            <input type="file" accept=".json,application/json" onChange={handleFile} className="hidden" data-testid="login-file-input" />
          </label>

          {keyfile && (
            <div className="border hairline px-4 py-3 surface-2 space-y-1 font-mono-data text-[11px]" data-testid="login-key-summary">
              <div><span className="text-[var(--lattice-text-3)]">LNS:</span> <span className="text-[var(--lattice-gold)]">{keyfile.lns_name}</span></div>
              <div><span className="text-[var(--lattice-text-3)]">Algoritmo:</span> <span className="text-white">{keyfile.algorithm}</span></div>
              {keyfile.role && <div><span className="text-[var(--lattice-text-3)]">Ruolo previsto:</span> <span className="text-white">{keyfile.role}</span></div>}
              <div><span className="text-[var(--lattice-text-3)]">Fingerprint:</span> <span className="text-white">{keyfile.public_key_fingerprint?.slice(0,16)}…</span></div>
            </div>
          )}

          {error && (
            <div className="border border-red-500/40 bg-red-500/5 px-4 py-3 flex items-start gap-2 text-[12px] text-red-300" data-testid="login-error">
              <AlertCircle size={14} className="mt-0.5 shrink-0" /><span>{error}</span>
            </div>
          )}

          <button
            data-testid="login-submit"
            disabled={!keyfile || busy}
            onClick={doLogin}
            className="btn-gold w-full inline-flex items-center justify-center gap-2"
          >
            {step === "done" ? <><Check size={14} /> Login riuscito</> :
             step === "signing" ? <><KeyRound size={14} className="animate-pulse" /> Firma in corso…</> :
             <><KeyRound size={14} /> Firma & accedi</>}
          </button>

          <a
            href="/recovery?mode=loss"
            data-testid="login-lost-key-cta-loss"
            className="block text-center font-mono-data text-[11px] tracking-[0.15em] uppercase text-sky-300 border border-sky-300/40 px-4 py-2.5 hover:bg-sky-300/5 hover:border-sky-300"
          >
            🔄  Ho perso il file .keypair.json · recovery 2-di-3 →
          </a>

          <a
            href="/recovery?mode=theft"
            data-testid="login-lost-key-cta-theft"
            className="block text-center font-mono-data text-[11px] tracking-[0.15em] uppercase text-rose-300 border border-rose-400/40 px-4 py-2.5 hover:bg-rose-400/5 hover:border-rose-400"
          >
            🚨  Mi hanno rubato la chiave · revoca + nuovo account →
          </a>

          <div className="text-center font-mono-data text-[10px] text-[var(--lattice-text-4)] pt-3 border-t hairline">
            Non hai ancora una chiave? Contatta il tuo admin aziendale o registra una nuova azienda da <a href="/onboarding" className="text-[var(--lattice-gold)] hover:underline">Onboarding</a>.
          </div>
        </div>
      </div>
    </div>
  );
}
