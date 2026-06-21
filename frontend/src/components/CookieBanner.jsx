import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Cookie, Check, Settings2, X } from "lucide-react";

const STORAGE_KEY = "lattice_cookie_consent_v1";

/**
 * GDPR cookie banner.
 *
 * Stores consent in localStorage as:
 *   { necessary: true, statistics: bool, ts: ISO8601 }
 *
 * When statistics === false the global PostHog instance is opted out
 * via `posthog.opt_out_capturing()`. When true → opt in.
 *
 * Necessary cookies (session, language, theme) are exempt from consent
 * under the ePrivacy Directive and Garante Privacy 2021 guidelines.
 */
export default function CookieBanner() {
  const [show, setShow] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [stats, setStats] = useState(true);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) {
        setShow(true);
      } else {
        const consent = JSON.parse(raw);
        applyConsent(consent);
      }
    } catch {
      setShow(true);
    }
  }, []);

  const applyConsent = (consent) => {
    const ph = typeof window !== "undefined" ? window.posthog : null;
    if (ph && typeof ph.opt_out_capturing === "function") {
      if (consent.statistics) {
        ph.opt_in_capturing && ph.opt_in_capturing();
      } else {
        ph.opt_out_capturing();
      }
    }
  };

  const save = (statisticsAllowed) => {
    const consent = {
      necessary: true,
      statistics: !!statisticsAllowed,
      ts: new Date().toISOString(),
    };
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(consent));
    } catch {}
    applyConsent(consent);
    setShow(false);
    setShowSettings(false);
  };

  if (!show) return null;

  return (
    <div
      data-testid="cookie-banner"
      className="fixed bottom-0 left-0 right-0 z-[9998] px-4 py-4"
      style={{ pointerEvents: "none" }}
    >
      <div
        className="max-w-5xl mx-auto"
        style={{
          background: "rgba(7, 13, 24, 0.97)",
          backdropFilter: "blur(16px)",
          border: "1px solid rgba(212, 175, 95, 0.35)",
          pointerEvents: "auto",
        }}
      >
        {/* Top gold line */}
        <div
          className="h-px"
          style={{ background: "linear-gradient(90deg, transparent, var(--lattice-gold), transparent)" }}
        />
        <div className="p-5 md:p-6">
          {!showSettings ? (
            <div className="flex flex-col md:flex-row items-start md:items-center gap-5">
              <Cookie size={28} className="text-[var(--lattice-gold)] shrink-0" />
              <div className="flex-1">
                <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] tracking-[0.3em] uppercase mb-1">
                  PRIVACY · COOKIE
                </div>
                <p className="text-[13px] text-[var(--lattice-text-2)] leading-relaxed">
                  Usiamo cookie tecnici (necessari) e — solo con il tuo consenso — cookie statistici per
                  capire come gli utenti usano il sito. Nessun cookie pubblicitario. Nessun trasferimento
                  dati extra-UE.{" "}
                  <Link
                    to="/cookie-policy"
                    data-testid="cookie-banner-cookie-policy-link"
                    className="text-[var(--lattice-gold)] underline hover:opacity-80"
                  >
                    Cookie Policy
                  </Link>
                  {" · "}
                  <Link
                    to="/privacy-policy"
                    data-testid="cookie-banner-privacy-link"
                    className="text-[var(--lattice-gold)] underline hover:opacity-80"
                  >
                    Privacy Policy
                  </Link>
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2 shrink-0">
                <button
                  data-testid="cookie-banner-customize"
                  onClick={() => setShowSettings(true)}
                  className="btn-ghost inline-flex items-center gap-1.5"
                  style={{ height: 36, padding: "0 14px", fontSize: 11 }}
                >
                  <Settings2 size={12} /> Personalizza
                </button>
                <button
                  data-testid="cookie-banner-reject"
                  onClick={() => save(false)}
                  className="btn-ghost"
                  style={{ height: 36, padding: "0 14px", fontSize: 11 }}
                >
                  Solo necessari
                </button>
                <button
                  data-testid="cookie-banner-accept-all"
                  onClick={() => save(true)}
                  className="btn-gold inline-flex items-center gap-1.5"
                  style={{ height: 36, padding: "0 18px", fontSize: 11 }}
                >
                  <Check size={12} /> Accetta tutti
                </button>
              </div>
            </div>
          ) : (
            <div data-testid="cookie-banner-settings">
              <div className="flex items-start justify-between gap-4 mb-4">
                <div>
                  <div className="font-mono-data text-[10px] text-[var(--lattice-gold)] tracking-[0.3em] uppercase mb-1">
                    PERSONALIZZA CONSENSO
                  </div>
                  <h3 className="font-display text-xl text-white">Gestisci i tuoi cookie</h3>
                </div>
                <button
                  onClick={() => setShowSettings(false)}
                  data-testid="cookie-banner-close-settings"
                  className="text-[var(--lattice-text-3)] hover:text-white"
                  aria-label="Chiudi"
                >
                  <X size={20} />
                </button>
              </div>
              <div className="space-y-3">
                <div className="flex items-start gap-4 p-4 border hairline">
                  <div className="flex-1">
                    <div className="font-display text-[15px] text-white">Cookie necessari</div>
                    <p className="text-[12px] text-[var(--lattice-text-3)] mt-1 leading-relaxed">
                      Indispensabili al funzionamento del sito (sessione, lingua, sicurezza). Non profilano
                      e non possono essere disabilitati.
                    </p>
                  </div>
                  <div
                    className="font-mono-data text-[10px] tracking-[0.18em] uppercase text-emerald-300 border border-emerald-400/40 px-2 py-1 shrink-0"
                  >
                    Sempre attivo
                  </div>
                </div>
                <label
                  className="flex items-start gap-4 p-4 border hairline cursor-pointer hover:border-[var(--lattice-gold)]"
                  data-testid="cookie-banner-toggle-stats"
                >
                  <div className="flex-1">
                    <div className="font-display text-[15px] text-white">Cookie statistici</div>
                    <p className="text-[12px] text-[var(--lattice-text-3)] mt-1 leading-relaxed">
                      Misuriamo pagine viste e interazioni in forma aggregata via PostHog (auto-hosted EU)
                      per migliorare il sito. Nessun dato personale identificabile.
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={stats}
                    onChange={(e) => setStats(e.target.checked)}
                    className="mt-1 w-5 h-5 accent-[var(--lattice-gold)] cursor-pointer shrink-0"
                  />
                </label>
              </div>
              <div className="flex flex-wrap items-center justify-end gap-2 mt-5">
                <button
                  data-testid="cookie-banner-save"
                  onClick={() => save(stats)}
                  className="btn-gold inline-flex items-center gap-1.5"
                  style={{ height: 36, padding: "0 18px", fontSize: 11 }}
                >
                  <Check size={12} /> Salva preferenze
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/** Public helper to reopen the banner (e.g. footer link "Modifica consenso cookie") */
export function reopenCookieBanner() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {}
  window.location.reload();
}
