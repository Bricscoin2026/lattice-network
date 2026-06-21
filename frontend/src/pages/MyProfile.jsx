import { useEffect, useState } from "react";
import { api, fmtTime } from "@/lib/api";
import { loadSession } from "@/lib/pqcAuth";
import { IdCard, Fingerprint, KeyRound, ShieldCheck, Building2, Calendar, Briefcase } from "lucide-react";

function Field({ label, value, mono = false, tid }) {
  return (
    <div className="border-b hairline py-3 first:pt-0 last:border-0" data-testid={tid}>
      <div className="eyebrow text-[10px] mb-1">{label}</div>
      <div className={`text-[13px] text-white break-all ${mono ? "font-mono-data" : ""}`}>{value || "—"}</div>
    </div>
  );
}

export default function MyProfile() {
  const session = loadSession();
  const [profile, setProfile] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!session?.lns) return;
    api.get(`/keystore/${encodeURIComponent(session.lns)}`)
      .then((r) => setProfile(r.data))
      .catch((e) => setErr(e?.response?.data?.detail || "Impossibile caricare il profilo"));
  }, [session?.lns]);

  if (!session?.lns) {
    return (
      <div className="surface-elev border hairline p-8 max-w-xl" data-testid="my-profile-anon">
        <h2 className="font-display text-2xl text-white">Non sei autenticato</h2>
        <p className="text-[13px] text-[var(--lattice-text-3)] mt-2">
          Vai su <a href="/login" className="text-[var(--lattice-gold)] hover:underline">/login</a> per accedere con la tua chiave PQC.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-3xl" data-testid="my-profile">
      <div>
        <div className="eyebrow flex items-center gap-2 mb-1">
          <IdCard size={11} className="text-[var(--lattice-gold)]" /> IDENTITÀ SOVRANA · IL TUO PROFILO
        </div>
        <h1 className="font-display text-4xl text-white">{session.lns}</h1>
        <p className="text-[13px] text-[var(--lattice-text-3)] mt-2 leading-relaxed">
          Questa è la tua identità sulla rete Lattice. È firmata con una chiave <strong className="text-white">ML-DSA-65</strong> (post-quantum)
          e registrata on-chain. Solo tu, che possiedi la chiave segreta nel file <code className="text-[var(--lattice-gold)]">.keypair.json</code>,
          puoi inviare mail Certify e messaggi Pulse a tuo nome.
        </p>
      </div>

      {err && (
        <div className="border border-red-500/40 bg-red-500/5 px-4 py-3 text-[12px] text-red-300">{err}</div>
      )}

      {profile && (
        <div className="surface-elev border hairline p-6 relative">
          <div className="absolute top-0 left-0 right-0 h-px gold-line" />
          <Field label="LNS · Lattice Name" value={profile.entity} mono tid="profile-lns" />
          <Field label="DID · Decentralized ID" value={profile.did || "—"} mono />
          <Field label="Algoritmo" value={`${profile.algorithm} · NIST FIPS 204`} />
          <Field label="Public key fingerprint" value={profile.fingerprint} mono tid="profile-fp" />
          <Field label="Public key (1952 byte)" value={(profile.public_key_hex || "").slice(0, 64) + "… (troncata)"} mono />
          <Field label="Ruolo aziendale" value={(session.role || "").toUpperCase()} />
          <Field label="Azienda (tenant)" value={profile.entity?.split(".").slice(-2).join(".") || session.tenant_id} mono />
          <Field label="Registrato il" value={fmtTime(profile.created_at, "it")} />
        </div>
      )}

      <div className="surface-elev border hairline p-5">
        <div className="eyebrow mb-3 flex items-center gap-2"><ShieldCheck size={11} className="text-[var(--lattice-gold)]" /> COSA PUOI FARE</div>
        <ul className="space-y-2 text-[13px] text-[var(--lattice-text-2)] leading-relaxed">
          <li className="flex gap-2"><span className="text-[var(--lattice-gold)]">→</span> Inviare e ricevere mail certificate (<a href="/certify" className="text-[var(--lattice-gold)] hover:underline">Mail Certify</a>)</li>
          <li className="flex gap-2"><span className="text-[var(--lattice-gold)]">→</span> Chattare con i tuoi colleghi (<a href="/pulse" className="text-[var(--lattice-gold)] hover:underline">Pulse</a>) — end-to-end cifrato</li>
          <li className="flex gap-2"><span className="text-[var(--lattice-gold)]">→</span> Verificare la blockchain (<a href="/how" className="text-[var(--lattice-gold)] hover:underline">Come funziona</a>)</li>
        </ul>
        <div className="mt-4 pt-4 border-t hairline">
          <div className="eyebrow mb-2 flex items-center gap-2"><KeyRound size={11} className="text-rose-300" /> RICORDA</div>
          <p className="text-[12px] text-[var(--lattice-text-3)] leading-relaxed">
            La tua chiave segreta è nel file <code className="text-[var(--lattice-gold)]">.keypair.json</code> che ti è stato consegnato all'onboarding.
            <strong className="text-white"> Senza quel file non puoi più accedere</strong> e non è recuperabile. Conservalo in un luogo sicuro.
          </p>
        </div>
      </div>
    </div>
  );
}
