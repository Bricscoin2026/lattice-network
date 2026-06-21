import { Link } from "react-router-dom";
import { ArrowLeft, Download, FileText } from "lucide-react";

/**
 * /whitepaper — viewer inline del PDF tecnico.
 * Mostra il PDF direttamente nella pagina (no download forzato) e offre
 * comunque il bottone di download esplicito.
 */
export default function WhitepaperViewer() {
  return (
    <div className="min-h-screen bg-[var(--lattice-bg)] text-white flex flex-col" data-testid="whitepaper-page">
      <header className="border-b hairline shrink-0">
        <div className="max-w-6xl mx-auto px-6 py-5 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-4" data-testid="whitepaper-home-link">
            <img src="/lattice-logo.jpeg" alt="Lattice Network" style={{ width: 56, height: 56, borderRadius: 8 }} className="border hairline" />
            <div>
              <div className="font-display text-2xl leading-tight">Lattice Network</div>
              <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] tracking-[0.18em] uppercase mt-0.5">
                Sovereign B2B Infrastructure · Made in EU
              </div>
            </div>
          </Link>
          <div className="flex items-center gap-3">
            <Link
              to="/security"
              className="font-mono-data text-[11px] uppercase tracking-[0.18em] text-[var(--lattice-text-3)] hover:text-white flex items-center gap-2"
            >
              <ArrowLeft size={12} /> sicurezza
            </Link>
            <a
              href="/whitepaper.pdf"
              download="Lattice-Network-Whitepaper.pdf"
              data-testid="whitepaper-download-btn"
              className="px-3 py-2 border border-[var(--lattice-gold)] text-[var(--lattice-gold)] font-mono-data text-[11px] tracking-[0.18em] uppercase hover:bg-[rgba(212,175,55,0.08)] flex items-center gap-2"
            >
              <Download size={12} /> Scarica PDF
            </a>
          </div>
        </div>
      </header>

      <div className="border-b hairline shrink-0">
        <div className="max-w-6xl mx-auto px-6 py-5">
          <div className="eyebrow flex items-center gap-2 text-[var(--lattice-gold)]">
            <FileText size={11} /> WHITEPAPER TECNICO
          </div>
          <h1 className="font-display text-3xl sm:text-4xl mt-2 leading-tight">
            Architettura, crittografia, limiti dichiarati
          </h1>
          <p className="text-[13px] text-[var(--lattice-text-3)] mt-2 max-w-3xl">
            12 sezioni · ML-DSA-65 · X25519 · AES-256-GCM · QBFT · Mixnet Loopix · Shamir 2-di-3.
            Sfoglia il documento qui sotto oppure scaricalo per la due diligence.
          </p>
        </div>
      </div>

      <main className="flex-1 max-w-6xl w-full mx-auto px-6 py-6" data-testid="whitepaper-viewer-wrap">
        <div className="border hairline surface-elev" style={{ height: "calc(100vh - 240px)", minHeight: 600 }}>
          <iframe
            src="/whitepaper.pdf#view=FitH&toolbar=1&navpanes=0"
            title="Lattice Network Whitepaper"
            data-testid="whitepaper-pdf-iframe"
            width="100%"
            height="100%"
            style={{ border: 0, display: "block", background: "#0a1020" }}
          />
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 font-mono-data text-[10px] text-[var(--lattice-text-3)]">
          <span>
            Problemi a visualizzare?{" "}
            <a
              href="/whitepaper.pdf"
              target="_blank"
              rel="noopener noreferrer"
              data-testid="whitepaper-newtab-link"
              className="text-[var(--lattice-gold)] hover:underline"
            >
              apri in una nuova scheda →
            </a>
          </span>
          <span>SHA3-512 verificabile · documento pubblico</span>
        </div>
      </main>

      <footer className="border-t hairline shrink-0">
        <div className="max-w-6xl mx-auto px-6 py-4 font-mono-data text-[10px] text-[var(--lattice-text-3)] flex flex-wrap items-center justify-between gap-2">
          <span>Lattice Network · Whitepaper · public</span>
          <Link to="/audit" className="hover:text-[var(--lattice-gold)]" data-testid="whitepaper-audit-link">
            Audit pubblico aziende →
          </Link>
        </div>
      </footer>
    </div>
  );
}
