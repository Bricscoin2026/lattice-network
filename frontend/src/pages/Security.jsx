import { Link } from "react-router-dom";
import { ShieldCheck, FileText, ArrowLeft, Download, CheckCircle2, Eye } from "lucide-react";

function DocCard({ title, sub, viewHref, downloadHref, downloadName, bullets, tid }) {
  return (
    <div data-testid={tid} className="surface-elev border hairline relative">
      <div className="absolute top-0 left-0 right-0 h-px gold-line" />
      <div className="px-6 py-6">
        <div className="eyebrow flex items-center gap-2 text-[var(--lattice-gold)]">
          <FileText size={11} /> DOCUMENTO TECNICO · PDF
        </div>
        <h2 className="font-display text-3xl text-white mt-2">{title}</h2>
        <p className="text-[13px] text-[var(--lattice-text-3)] mt-2 leading-relaxed">{sub}</p>
        <ul className="mt-4 space-y-1.5">
          {bullets.map((b, i) => (
            <li key={i} className="flex items-start gap-2 text-[12px] text-[var(--lattice-text-2)]">
              <CheckCircle2 size={12} className="text-[var(--lattice-gold)] mt-0.5 shrink-0" /> {b}
            </li>
          ))}
        </ul>
        <div className="flex flex-wrap gap-2 mt-5">
          {viewHref && (
            <Link
              to={viewHref}
              data-testid={`${tid}-view`}
              className="inline-flex items-center gap-2 px-4 py-2 border border-[var(--lattice-gold)] bg-[rgba(212,175,55,0.06)] text-[var(--lattice-gold)] font-mono-data text-[11px] tracking-[0.18em] uppercase hover:bg-[rgba(212,175,55,0.12)]"
            >
              <Eye size={12} /> Apri nel browser
            </Link>
          )}
          <a
            href={downloadHref}
            download={downloadName}
            data-testid={`${tid}-download`}
            className="inline-flex items-center gap-2 px-4 py-2 border hairline text-[var(--lattice-text-2)] font-mono-data text-[11px] tracking-[0.18em] uppercase hover:text-white"
          >
            <Download size={12} /> Scarica
          </a>
        </div>
      </div>
    </div>
  );
}

export default function Security() {
  return (
    <div className="min-h-screen bg-[var(--lattice-bg)] text-white">
      <header className="border-b hairline">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3" data-testid="security-home-link">
            <img src="/lattice-logo.jpeg" alt="Lattice" style={{ width: 28, height: 28, borderRadius: 4 }} />
            <span className="font-display text-xl">Lattice Network</span>
          </Link>
          <Link
            to="/"
            className="font-mono-data text-[11px] uppercase tracking-[0.18em] text-[var(--lattice-text-3)] hover:text-white flex items-center gap-2"
          >
            <ArrowLeft size={12} /> indietro
          </Link>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-12 space-y-10" data-testid="security-page">
        <div>
          <div className="eyebrow flex items-center gap-2 text-[var(--lattice-gold)]">
            <ShieldCheck size={11} /> TRASPARENZA · DOCUMENTAZIONE TECNICA
          </div>
          <h1 className="font-display text-4xl sm:text-5xl mt-2">Sicurezza &amp; Audit</h1>
          <p className="text-[14px] text-[var(--lattice-text-3)] mt-4 leading-relaxed max-w-3xl">
            Pubblichiamo qui due documenti ispezionabili da chiunque: il whitepaper tecnico
            (architettura, scelte crittografiche, limiti dichiarati) e l&apos;audit di sicurezza
            interno sulla blockchain (9 vulnerabilità identificate e chiuse, ognuna con test
            di regressione automatico).
          </p>
          <p className="text-[13px] text-[var(--lattice-text-3)] mt-3 leading-relaxed max-w-3xl">
            Un audit esterno indipendente è raccomandato prima di deploy mission-critical.
            Sono disponibili contatti per CISO che vogliono concordare un&apos;ispezione del
            codice o un pen-test prima dell&apos;acquisto.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <DocCard
            tid="doc-whitepaper"
            title="Whitepaper tecnico"
            sub="12 sezioni · architettura, crittografia (ML-DSA-65, X25519, AES-GCM, SHA3, Poseidon), consenso QBFT, mixnet Loopix, ZK-RLN, recovery 2-di-3 Shamir, limiti dichiarati."
            viewHref="/whitepaper"
            downloadHref="/whitepaper.pdf"
            downloadName="Lattice-Network-Whitepaper.pdf"
            bullets={[
              "Algoritmi standardizzati NIST (FIPS 204, FIPS 202)",
              "Confronto onesto con PEC tradizionale e S/MIME",
              "Sezione 10: cosa il prodotto NON è (limiti)",
            ]}
          />
          <DocCard
            tid="doc-audit"
            title="Security Audit Interno"
            sub="Audit del layer blockchain · 9 findings (2 CRITICAL, 3 HIGH, 3 MEDIUM, 1 LOW). Ogni fix coperto da test pytest automatico."
            downloadHref="/security-audit.pdf"
            downloadName="Lattice-Network-Security-Audit.pdf"
            bullets={[
              "Block-hash binding (merkle + chain_id + previous_hash)",
              "Validator anti-equivocation persistente",
              "Replay protection cross-chain",
              "8 test automatici eseguibili da CI",
            ]}
          />
        </div>

        <section className="surface-elev border hairline relative">
          <div className="absolute top-0 left-0 right-0 h-px gold-line" />
          <div className="px-6 py-6">
            <div className="eyebrow text-[var(--lattice-gold)] mb-3">VERIFICA INDIPENDENTE</div>
            <p className="text-[13px] text-[var(--lattice-text-2)] leading-relaxed">
              Ogni messaggio Pulse e ogni mail Certify mostra all&apos;utente il proprio
              <strong className="text-white"> tx_id</strong>, il
              <strong className="text-white"> doc_hash</strong> SHA3-512 e il numero del
              blocco di notarizzazione. Chiunque può copiare quegli identificatori e
              chiamare l&apos;endpoint pubblico
              <code className="font-mono-data text-[var(--lattice-gold)]"> /api/ledger/verify/{`{tx_id}`}</code>
              per ottenere la verifica crittografica indipendente della firma ML-DSA-65 dai 4
              validator BFT. La pagina
              <Link to="/audit" className="text-[var(--lattice-gold)] hover:underline" data-testid="security-audit-dir-link"> /audit </Link>
              espone l&apos;elenco pubblico delle aziende sulla rete (senza login) per la due diligence.
            </p>
          </div>
        </section>

        <div className="flex flex-wrap items-center gap-3 pt-4">
          <Link to="/how" className="px-4 py-2 border hairline text-[var(--lattice-text-2)] font-mono-data text-[11px] tracking-[0.18em] uppercase hover:text-white">
            Come funziona la rete
          </Link>
          <a href="https://wa.me/393519618068?text=Segnalazione%20vulnerabilit%C3%A0%20su%20Lattice%20Network" target="_blank" rel="noopener noreferrer" data-testid="security-contact-wa" className="px-4 py-2 border hairline text-[var(--lattice-text-2)] font-mono-data text-[11px] tracking-[0.18em] uppercase hover:text-white">
            WhatsApp +39 351 961 8068
          </a>
        </div>
      </main>

      <footer className="border-t hairline mt-16">
        <div className="max-w-5xl mx-auto px-6 py-6 font-mono-data text-[11px] text-[var(--lattice-text-3)] flex flex-wrap items-center justify-between gap-3">
          <span>Lattice Network · Made in EU</span>
          <span>Confidential · Commercial Material</span>
        </div>
      </footer>
    </div>
  );
}
