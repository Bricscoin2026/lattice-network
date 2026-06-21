import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useLang } from "@/i18n/LangProvider";
import { TID } from "@/constants/lattice-testids";
import { useEffect, useState } from "react";
import { api, getActiveRole, setActiveRole, ROLES } from "@/lib/api";
import { loadSession, clearSession } from "@/lib/pqcAuth";
import { Shield, Activity, Boxes, IdCard, MailCheck, Terminal, ChevronRight, Radio, Briefcase, Smartphone, UserCog, Eye, ShieldOff, Building2, LogIn, LogOut, Inbox, Cpu, BookOpen, KeyRound, Stethoscope } from "lucide-react";

const ROLE_META = {
  sovereign: { label: "Sovereign", Icon: Shield, hint: "Tenant admin · full access", color: "text-[var(--lattice-gold)]" },
  auditor:   { label: "Auditor",   Icon: Eye,   hint: "Read-only · no plaintext", color: "text-sky-300" },
  vendor:    { label: "Vendor",    Icon: ShieldOff, hint: "Metadata-only · no content", color: "text-rose-300" },
};

function SessionBadge() {
  const session = loadSession();
  if (!session) {
    return (
      <a
        href="/login"
        data-testid="topbar-login-link"
        className="flex items-center gap-2 px-3 border hairline surface font-mono-data text-[11px] tracking-[0.15em] uppercase text-[var(--lattice-gold)] hover:bg-[rgba(212,175,55,0.08)]"
        style={{ height: 32 }}
      >
        <LogIn size={12} /> Login
      </a>
    );
  }
  const onLogout = () => {
    clearSession();
    window.location.href = "/login";
  };
  return (
    <button
      onClick={onLogout}
      data-testid="topbar-logout-btn"
      className="flex items-center gap-2 px-3 border hairline surface font-mono-data text-[11px] tracking-[0.15em] uppercase text-[var(--lattice-text-2)] hover:text-white"
      style={{ height: 32 }}
      title={`${session.lns} · ${session.role}`}
    >
      <Shield size={11} className="text-[var(--lattice-gold)]" />
      <span className="truncate max-w-[180px]">{session.lns?.split(".")[0]}</span>
      <LogOut size={12} />
    </button>
  );
}

function RoleSwitch() {
  const [role, setRole] = useState(getActiveRole());
  const [open, setOpen] = useState(false);
  const meta = ROLE_META[role] || ROLE_META.sovereign;
  const Icon = meta.Icon;
  const choose = (r) => {
    setActiveRole(r);
    setRole(r);
    setOpen(false);
    // Reload so every page re-fetches with the new role (cleanest for RBAC).
    setTimeout(() => window.location.reload(), 50);
  };
  return (
    <div className="relative" data-testid="role-switch">
      <button
        data-testid="role-switch-button"
        onClick={() => setOpen((v) => !v)}
        className={`flex items-center gap-2 px-3 border hairline surface font-mono-data text-[11px] tracking-[0.15em] uppercase ${meta.color}`}
        style={{ height: 32 }}
        title={meta.hint}
      >
        <Icon size={12} />
        <span>{meta.label}</span>
        <ChevronRight size={11} className="opacity-60" />
      </button>
      {open && (
        <div className="absolute right-0 mt-1 z-50 min-w-[220px] surface-elev border hairline" data-testid="role-switch-menu">
          {ROLES.map((r) => {
            const m = ROLE_META[r];
            const Ic = m.Icon;
            const sel = r === role;
            return (
              <button
                key={r}
                data-testid={`role-switch-opt-${r}`}
                onClick={() => choose(r)}
                className={`w-full text-left px-3 py-2 flex items-start gap-2 border-b hairline last:border-0 hover:bg-[rgba(255,255,255,0.04)] ${sel ? "bg-[rgba(212,175,55,0.06)]" : ""}`}
              >
                <Ic size={13} className={`mt-0.5 ${m.color}`} />
                <div className="flex-1">
                  <div className={`font-mono-data text-[11px] uppercase tracking-[0.15em] ${m.color}`}>{m.label}</div>
                  <div className="font-mono-data text-[10px] text-[var(--lattice-text-3)] mt-0.5">{m.hint}</div>
                </div>
                {sel && <span className="font-mono-data text-[9px] text-[var(--lattice-gold)] mt-1">attivo</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function LangSwitch() {
  const { lang, setLang } = useLang();
  return (
    <div className="flex items-center hairline border surface" style={{ height: 32 }}>
      <button
        data-testid={TID.langToggleIt}
        onClick={() => setLang("it")}
        className={`font-mono-data text-[11px] px-3 h-full tracking-[0.18em] transition-colors ${
          lang === "it"
            ? "bg-[var(--lattice-gold)] text-[var(--lattice-bg)]"
            : "text-[var(--lattice-text-3)] hover:text-white"
        }`}
      >
        IT
      </button>
      <div className="w-px h-full bg-[var(--lattice-border)]" />
      <button
        data-testid={TID.langToggleEn}
        onClick={() => setLang("en")}
        className={`font-mono-data text-[11px] px-3 h-full tracking-[0.18em] transition-colors ${
          lang === "en"
            ? "bg-[var(--lattice-gold)] text-[var(--lattice-bg)]"
            : "text-[var(--lattice-text-3)] hover:text-white"
        }`}
      >
        EN
      </button>
    </div>
  );
}

function LiveStatus() {
  const { t } = useLang();
  const [ok, setOk] = useState(true);
  useEffect(() => {
    let alive = true;
    const ping = async () => {
      try {
        await api.get("/health");
        if (alive) setOk(true);
      } catch {
        if (alive) setOk(false);
      }
    };
    ping();
    const id = setInterval(ping, 5000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);
  return (
    <div data-testid={TID.liveStatus} className="flex items-center gap-2">
      <span className={`dot ${ok ? "dot-online" : "dot-offline"} pulse-dot`} style={{ color: ok ? "#34d399" : "#ef4444" }} />
      <span className="font-mono-data text-[10px] tracking-[0.22em]" style={{ color: ok ? "#6ee7b7" : "#fca5a5" }}>
        {ok ? t.live : "OFFLINE"}
      </span>
    </div>
  );
}

// Sovereign (operator/Fabio) sees EVERYTHING. Tenant users only see their workspace.
const OPERATOR_NAV = [
  { to: "/dashboard", key: "dashboard", tid: TID.navDashboard, Icon: Activity, end: true },
  { to: "/onboarding", key: "onboarding", tid: "nav-onboarding", Icon: Building2, label: "Onboarding" },
  { to: "/leads", key: "leads", tid: "nav-leads", Icon: Inbox, label: "Lead aziende" },
  { to: "/ledger", key: "ledger", tid: TID.navLedger, Icon: Boxes },
  { to: "/qbft", key: "qbft", tid: TID.navQbft, Icon: Shield },
  { to: "/lns", key: "lns", tid: TID.navLns, Icon: IdCard },
  { to: "/certify", key: "certify", tid: TID.navCertify, Icon: MailCheck },
  { to: "/pulse", key: "pulse", tid: TID.navPulse, Icon: Radio },
  { to: "/logs", key: "logs", tid: TID.navLogs, Icon: Terminal },
  { to: "/admin/health", key: "admin-health", tid: "nav-admin-health", Icon: Stethoscope, label: "System Health" },
  { to: "/vendor", key: "vendor", tid: TID.navVendor, Icon: Briefcase },
  { to: "/network", key: "network", tid: "nav-network", Icon: Activity, label: "Network Live" },
  { to: "/rust", key: "rust", tid: "nav-rust", Icon: Cpu, label: "Rust Bridge" },
  { to: "/how", key: "how", tid: "nav-how", Icon: BookOpen, label: "Come funziona" },
];

// Tenant workspace — differs by role.
//   admin    : Dashboard + Dipendenti + Recovery + Mail Certify + Pulse + Help
//   others   : Mail Certify + Pulse + Help only (no LNS management, no recovery)
function tenantNav(role) {
  const isAdmin = role === "admin";
  if (isAdmin) {
    return [
      { to: "/dashboard", key: "dashboard", tid: TID.navDashboard, Icon: Activity, end: true, label: "Dashboard" },
      { to: "/lns", key: "lns", tid: TID.navLns, Icon: IdCard, label: "Dipendenti" },
      { to: "/recovery", key: "recovery", tid: "nav-recovery", Icon: KeyRound, label: "Recupero chiavi" },
      { to: "/certify", key: "certify", tid: TID.navCertify, Icon: MailCheck, label: "Mail Certify" },
      { to: "/pulse", key: "pulse", tid: TID.navPulse, Icon: Radio, label: "Pulse" },
      { to: "/how", key: "how", tid: "nav-how-tenant", Icon: BookOpen, label: "Come funziona" },
    ];
  }
  // Dipendente / Operatore / Auditor: workspace minimo + Recovery
  // (perché un dipendente non-admin può essere stato scelto come guardiano
  // dal fondatore e deve poter accettare richieste di recupero, oltre a
  // poter aprire la propria richiesta se ha perso la chiave).
  return [
    { to: "/certify", key: "certify", tid: TID.navCertify, Icon: MailCheck, label: "Mail Certify", end: true },
    { to: "/pulse", key: "pulse", tid: TID.navPulse, Icon: Radio, label: "Pulse" },
    { to: "/recovery", key: "recovery", tid: "nav-recovery", Icon: KeyRound, label: "Recupero chiavi" },
    { to: "/how", key: "how", tid: "nav-how-tenant", Icon: BookOpen, label: "Come funziona" },
  ];
}

function useNavForRole() {
  const session = loadSession();
  // Platform operator (Fabio) = no JWT OR JWT without tenant_id → full nav.
  // Tenant users (any role bound to a tenant_id) → workspace nav.
  if (!session || !session.tenant_id) return OPERATOR_NAV;
  return tenantNav(session.role);
}

function useLeadsUnread() {
  const [n, setN] = useState(0);
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const r = await api.get("/leads/unread-count");
        if (alive) setN(r.data?.unread || 0);
      } catch (_e) {
        if (alive) setN(0);
      }
    };
    tick();
    const id = setInterval(tick, 30_000);
    return () => { alive = false; clearInterval(id); };
  }, []);
  return n;
}

// Count of recovery requests where the current user is a nominated guardian
// AND has not yet contributed. Polled every 30s. Returns 0 for non-tenant
// users or any error (so the badge silently disappears).
function useRecoveryGuardianPending() {
  const [n, setN] = useState(0);
  useEffect(() => {
    const session = loadSession();
    if (!session?.lns) return;
    let alive = true;
    const tick = async () => {
      try {
        const r = await api.get("/keyrecovery/requests/pending-as-guardian");
        const items = r.data?.items || [];
        const need = items.filter((x) => !x.already_contributed).length;
        if (alive) setN(need);
      } catch (_e) {
        if (alive) setN(0);
      }
    };
    tick();
    const id = setInterval(tick, 30_000);
    return () => { alive = false; clearInterval(id); };
  }, []);
  return n;
}

function Sidebar() {
  const { t } = useLang();
  const navItems = useNavForRole();
  const session = loadSession();
  const isOperator = !session || !session.tenant_id;
  const leadsUnread = useLeadsUnread();
  const recoveryPending = useRecoveryGuardianPending();
  return (
    <aside className="hidden md:flex flex-col w-[240px] shrink-0 border-r hairline surface" style={{ minHeight: "100vh" }}>
      <div className="px-6 pt-7 pb-6 border-b hairline">
        <div className="flex items-center gap-3">
          <img
            src="/lattice-logo.jpeg"
            alt="Lattice"
            data-testid="brand-logo"
            style={{ width: 36, height: 36, objectFit: "contain", borderRadius: 4 }}
          />
          <div className="font-display text-2xl text-white leading-none tracking-tight">{t.brand}</div>
        </div>
        <div className="eyebrow mt-3 leading-relaxed">
          {isOperator ? t.brandSub : (session?.tenant_id ? `Workspace · ${session.lns?.split(".").slice(-2).join(".")}` : t.brandSub)}
        </div>
      </div>
      <nav className="flex-1 py-3">
        {navItems.map(({ to, key, tid, Icon, end, label }) => (
          <NavLink
            key={key}
            to={to}
            end={end}
            data-testid={tid}
            className={({ isActive }) =>
              `group flex items-center justify-between px-6 py-3 border-l-2 transition-all ${
                isActive
                  ? "border-[var(--lattice-gold)] bg-[rgba(212,175,55,0.06)] text-white"
                  : "border-transparent text-[var(--lattice-text-3)] hover:text-white hover:bg-[rgba(255,255,255,0.02)]"
              }`
            }
          >
            <span className="flex items-center gap-3">
              <Icon size={15} strokeWidth={1.5} />
              <span className="font-sans-ui text-[13px]">{label || t.nav[key] || key}</span>
              {key === "leads" && isOperator && leadsUnread > 0 && (
                <span
                  data-testid="nav-leads-unread-badge"
                  className="ml-1 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1.5 rounded-full bg-[var(--lattice-gold)] text-[#0a1020] font-mono-data text-[10px] font-bold leading-none"
                  title={`${leadsUnread} nuovi lead non letti`}
                >
                  {leadsUnread > 99 ? "99+" : leadsUnread}
                </span>
              )}
              {key === "recovery" && recoveryPending > 0 && (
                <span
                  data-testid="nav-recovery-pending-badge"
                  className="ml-1 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1.5 rounded-full bg-sky-300 text-[#0a1020] font-mono-data text-[10px] font-bold leading-none"
                  title={`${recoveryPending} richieste di recupero in cui sei nominato`}
                >
                  {recoveryPending > 99 ? "99+" : recoveryPending}
                </span>
              )}
            </span>
            <ChevronRight size={13} className="opacity-40 group-hover:opacity-100 group-hover:text-[var(--lattice-gold)] transition-colors" />
          </NavLink>
        ))}
      </nav>
      <div className="px-6 py-5 border-t hairline">
        <div className="eyebrow mb-2">CHAIN ID</div>
        <div className="font-mono-data text-[11px] text-[var(--lattice-text-2)] break-all">
          lattice-sovereign-it-prod
        </div>
        <div className="gold-line my-3" />
        <div className="eyebrow mb-2">BUILD</div>
        <div className="font-mono-data text-[11px] text-[var(--lattice-text-3)]">
          v0.1.0 · rustc 1.78 · QBFT
        </div>
      </div>
    </aside>
  );
}

function TopBar() {
  const { t } = useLang();
  const loc = useLocation();
  const segment = loc.pathname.split("/")[1] || "dashboard";
  const title = t.nav[segment] || t.nav.dashboard;
  return (
    <header className="sticky top-0 z-30 surface border-b hairline" style={{ backdropFilter: "blur(8px)" }}>
      <div className="flex items-center justify-between px-6 py-3">
        <div className="flex items-center gap-4">
          <div className="md:hidden font-display text-xl">{t.brand}</div>
          <div className="hidden md:flex items-center gap-3">
            <span className="eyebrow">{title}</span>
            <span className="w-3 h-px bg-[var(--lattice-gold)] opacity-60" />
            <span className="font-mono-data text-[11px] text-[var(--lattice-text-3)]">
              {new Date().toISOString().slice(0, 10)}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="hidden sm:flex items-center gap-2 pill pill-gold">
            <Shield size={11} strokeWidth={2} />
            <span>PQC · ML-DSA-65</span>
          </div>
          <div className="hidden lg:flex items-center gap-1">
            <a
              href="/whitepaper"
              data-testid="topbar-whitepaper-link"
              className="px-2 py-1 font-mono-data text-[10px] tracking-[0.15em] uppercase text-[var(--lattice-text-3)] hover:text-[var(--lattice-gold)] border hairline"
              title="Whitepaper tecnico"
            >
              <BookOpen size={11} className="inline mr-1" /> Whitepaper
            </a>
            <a
              href="/audit"
              data-testid="topbar-audit-link"
              className="px-2 py-1 font-mono-data text-[10px] tracking-[0.15em] uppercase text-[var(--lattice-text-3)] hover:text-[var(--lattice-gold)] border hairline"
              title="Audit pubblico aziende"
            >
              <Eye size={11} className="inline mr-1" /> Audit
            </a>
          </div>
          <LiveStatus />
          <SessionBadge />
          <RoleSwitch />
          <LangSwitch />
        </div>
      </div>
    </header>
  );
}

import { useIdleLogout } from "@/lib/useIdleLogout";

export default function AppShell() {
  useIdleLogout();
  return (
    <div data-testid={TID.appShell} className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar />
        <main className="flex-1 p-6 lg:p-8 fade-in min-w-0">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
