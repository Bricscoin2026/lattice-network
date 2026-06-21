import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useLang } from "@/i18n/LangProvider";
import { Lock, Hash, Send, ShieldCheck, Smartphone, Radio, BadgeCheck } from "lucide-react";

function PhoneFrame({ title, children }) {
  return (
    <div className="relative mx-auto" style={{ width: 320, height: 660 }}>
      <div className="absolute inset-0 rounded-[36px] border-2"
        style={{ borderColor: "var(--lattice-gold)", background: "linear-gradient(180deg,#06090f 0%, #0b1220 100%)", boxShadow: "0 20px 60px rgba(0,0,0,0.6)" }} />
      <div className="absolute left-1/2 -translate-x-1/2"
        style={{ top: 14, width: 110, height: 22, borderRadius: 12, background: "#06090f", border: "1px solid var(--lattice-border)" }} />
      <div className="absolute inset-[14px] rounded-[28px] overflow-hidden flex flex-col" style={{ background: "#070d18", border: "1px solid var(--lattice-border)" }}>
        <div className="flex items-center justify-between px-4 pt-6 pb-2 border-b hairline">
          <span className="font-mono-data text-[9px] text-[var(--lattice-gold)]">{title}</span>
          <span className="font-mono-data text-[9px] text-[var(--lattice-text-3)]">100%</span>
        </div>
        <div className="flex-1 overflow-auto">{children}</div>
      </div>
    </div>
  );
}

function Feature({ Icon, title, body }) {
  return (
    <div className="flex items-start gap-3">
      <Icon size={16} className="text-[var(--lattice-gold)] mt-1 shrink-0" />
      <div>
        <div className="font-mono-data text-[11px] tracking-wider uppercase text-white">{title}</div>
        <div className="text-[12px] text-[var(--lattice-text-3)] leading-relaxed">{body}</div>
      </div>
    </div>
  );
}

function Hero({ eyebrow, title, subtitle }) {
  return (
    <div className="pb-6 border-b hairline mb-6">
      <div className="eyebrow mb-3">{eyebrow}</div>
      <h1 className="font-display text-4xl sm:text-5xl text-white leading-[1.05]">{title}</h1>
      <p className="mt-3 text-[13px] text-[var(--lattice-text-3)] leading-relaxed max-w-3xl">{subtitle}</p>
    </div>
  );
}

export function PulseMobile() {
  return (
    <div className="space-y-8 fade-in">
      <Hero eyebrow="MOBILE NATIVE · iOS + ANDROID" title="Pulse Mobile App"
        subtitle="App nativa per smartphone. Sessione PQXDH (ML-KEM-768) + Double Ratchet, chiavi nella Secure Enclave, instradamento Loopix 3-hop. TestFlight (iOS) + Play Store Enterprise (Android)." />
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        <div className="lg:col-span-5 flex justify-center">
          <PhoneFrame title="PULSE · SEALED">
            <div className="px-4 py-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-display text-lg text-white">Messaggi</span>
                <Radio size={14} className="text-[var(--lattice-gold)]" />
              </div>
              {[["cfo.azienda.id","Bilancio Q4 pronto","12:42",true],["legal.azienda.id","NDA siglato","11:08",true],["ceo.azienda.id","Riunione CdA","10:32",false]].map((c,i)=>(
                <div key={i} className="border hairline-strong p-2.5 surface-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono-data text-[11px] text-white truncate">{c[0]}</span>
                    <span className="font-mono-data text-[9px] text-[var(--lattice-text-4)]">{c[2]}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <Lock size={9} className="text-[var(--lattice-gold)]" />
                    <span className="font-mono-data text-[10px] text-[var(--lattice-text-3)] truncate">{c[1]}</span>
                  </div>
                  {c[3] && <div className="mt-1.5"><span className="pill pill-gold" style={{padding:"1px 5px",fontSize:8}}><Hash size={8} /> ANCHORED</span></div>}
                </div>
              ))}
            </div>
          </PhoneFrame>
        </div>
        <div className="lg:col-span-7 space-y-5 surface p-6">
          <Feature Icon={ShieldCheck} title="Chiavi nella Secure Enclave" body="ML-DSA-65 + ML-KEM-768 generate dentro il chip sicuro del telefono. Mai esposte." />
          <Feature Icon={Lock} title="Sealed-sender E2EE" body="PQXDH + Double Ratchet → forward secrecy + post-compromise security anche contro un computer quantistico." />
          <Feature Icon={Radio} title="Loopix mixnet 3-hop" body="Onion routing con cover traffic Poisson: impossibile fare correlation analysis sui metadati." />
          <Feature Icon={Hash} title="Ancore on-chain" body="Ogni 3 messaggi una NotarySeal TX ancora la conversazione al ledger sovrano." />
          <Feature Icon={Smartphone} title="Zero-knowledge del vendor" body="Lattice Sovereign Networks NON vede mai i messaggi. Vivono sul cluster on-premise del tenant." />
          <Feature Icon={BadgeCheck} title="Distribuzione enterprise" body="TestFlight per iOS, Play Store Enterprise per Android. Firma binaria pubblicata sulla blockchain." />
          <Link to="/pulse" className="btn-gold inline-flex items-center gap-2 mt-4"><Send size={13} /> Apri Pulse Web</Link>
        </div>
      </div>
    </div>
  );
}

export function CertifyMobile() {
  return (
    <div className="space-y-8 fade-in">
      <Hero eyebrow="MOBILE NATIVE · iOS + ANDROID" title="Certify Mobile App"
        subtitle="Mail PEC-grade con sigillo NotarySeal on-chain firmato ML-DSA-65 direttamente dalla Secure Enclave del telefono. Connettore nativo Exchange / Google Workspace." />
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        <div className="lg:col-span-5 flex justify-center">
          <PhoneFrame title="CERTIFY · NOTARY">
            <div className="px-4 py-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-display text-lg text-white">In Uscita</span>
                <ShieldCheck size={14} className="text-[var(--lattice-gold)]" />
              </div>
              {[["cfo","Bilancio Q4","13:01",8412],["legal · cc audit","NDA fornitore","12:18",8409],["5 destinatari","Policy Sicurezza","Ieri",8389]].map((m,i)=>(
                <div key={i} className="border hairline-strong p-2.5 surface-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono-data text-[10px] text-white truncate">→ {m[0]}</span>
                    <span className="font-mono-data text-[9px] text-[var(--lattice-text-4)]">{m[2]}</span>
                  </div>
                  <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] truncate mt-1">{m[1]}</div>
                  <div className="mt-1.5"><span className="pill pill-gold" style={{padding:"1px 5px",fontSize:8}}><Hash size={8} /> #{m[3]}</span></div>
                </div>
              ))}
            </div>
          </PhoneFrame>
        </div>
        <div className="lg:col-span-7 space-y-5 surface p-6">
          <Feature Icon={Hash} title="SHA3-512 + ML-DSA-65" body="Hash locale, firma nella Secure Enclave, NotarySeal sul ledger sovrano." />
          <Feature Icon={ShieldCheck} title="Court-grade audit trail" body="Hash 512-bit + tx_id + block_index + timestamp UTC + firma. Garante Privacy-ready." />
          <Feature Icon={Lock} title="Allegati + body sigillati" body="L'intero RFC-5322 + allegati partecipano all'hash. Una virgola modificata = ricevuta invalida." />
          <Feature Icon={Send} title="Multi-destinatario nativo" body="TO + CC fan-out con un unico NotarySeal — efficiente in storage." />
          <Feature Icon={Smartphone} title="Ponte Exchange / Google" body="Connettore proprietario verso i mail server legacy. L'utente non cambia client." />
          <Feature Icon={BadgeCheck} title="Push-notification cifrate" body="VoIP-push camuffate: nessun metadato leakato ad Apple / Google." />
          <Link to="/certify" className="btn-gold inline-flex items-center gap-2 mt-4"><Send size={13} /> Apri Certify Web</Link>
        </div>
      </div>
    </div>
  );
}
