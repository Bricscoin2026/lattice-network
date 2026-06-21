import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import { LangProvider } from "@/i18n/LangProvider";
import AppShell from "@/components/AppShell";
import Dashboard from "@/pages/Dashboard";
import Ledger from "@/pages/Ledger";
import Qbft from "@/pages/Qbft";
import Lns from "@/pages/Lns";
import Certify from "@/pages/Certify";
import Pulse from "@/pages/Pulse";
import Vendor from "@/pages/Vendor";
import { PulseMobile, CertifyMobile } from "@/pages/MobileApps";
import Logs from "@/pages/Logs";
import NetworkStatus from "@/pages/NetworkStatus";
import Onboarding from "@/pages/Onboarding";
import Login from "@/pages/Login";
import Landing from "@/pages/Landing";
import RolePage from "@/pages/RolePage";
import { PrivacyPolicy, CookiePolicy } from "@/pages/LegalPages";
import CookieBanner from "@/components/CookieBanner";
import Leads from "@/pages/Leads";
import TenantDashboard from "@/pages/TenantDashboard";
import TenantEmployees from "@/pages/TenantEmployees";
import RustBridge from "@/pages/RustBridge";
import HowItWorks from "@/pages/HowItWorks";
import MyProfile from "@/pages/MyProfile";
import KeyRecovery from "@/pages/KeyRecovery";
import AuditPublic from "@/pages/AuditPublic";
import AuditDirectory from "@/pages/AuditDirectory";
import WhitepaperViewer from "@/pages/WhitepaperViewer";
import Security from "@/pages/Security";
import AdminHealth from "@/pages/AdminHealth";
import Explorer from "@/pages/Explorer";
import { PlatformOnly, TenantEmployeeBlocked, isTenantUser } from "@/components/RouteGuard";
import { loadSession } from "@/lib/pqcAuth";
import "@/App.css";

function DashboardRoute() {
  return isTenantUser() ? <TenantDashboard /> : <Dashboard />;
}

function LnsRoute() {
  // Platform operator → full LNS network registry.
  // Tenant admin → company-scoped employee management (add, role, revoke).
  // Other tenant users (operator/auditor) → their own profile card.
  const session = loadSession();
  if (!session?.tenant_id) return <Lns />;
  if (session.role === "admin") return <TenantEmployees />;
  return <MyProfile />;
}

function App() {
  return (
    <LangProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/per-il-ceo" element={<RolePage role="ceo" />} />
          <Route path="/per-il-ciso" element={<RolePage role="ciso" />} />
          <Route path="/per-il-legal" element={<RolePage role="legal" />} />
          <Route path="/privacy-policy" element={<PrivacyPolicy />} />
          <Route path="/cookie-policy" element={<CookiePolicy />} />
          <Route path="/login" element={<Login />} />
          <Route path="/audit" element={<AuditDirectory />} />
          <Route path="/audit/:slug" element={<AuditPublic />} />
          <Route path="/whitepaper" element={<WhitepaperViewer />} />
          <Route path="/security" element={<Security />} />
          <Route path="/explorer" element={<Explorer view="home" />} />
          <Route path="/explorer/search" element={<Explorer view="search" />} />
          <Route path="/explorer/tx/:tx_id" element={<Explorer view="tx" />} />
          <Route path="/explorer/block/:block_index" element={<Explorer view="block" />} />
          <Route path="/explorer/lns/:lns_name" element={<Explorer view="lns" />} />
          <Route element={<AppShell />}>
            <Route path="/dashboard" element={<TenantEmployeeBlocked><DashboardRoute /></TenantEmployeeBlocked>} />
            <Route path="/ledger" element={<PlatformOnly><Ledger /></PlatformOnly>} />
            <Route path="/qbft" element={<PlatformOnly><Qbft /></PlatformOnly>} />
            <Route path="/lns" element={<TenantEmployeeBlocked><LnsRoute /></TenantEmployeeBlocked>} />
            <Route path="/certify" element={<Certify />} />
            <Route path="/pulse" element={<Pulse />} />
            <Route path="/apps/pulse" element={<PulseMobile />} />
            <Route path="/apps/certify" element={<CertifyMobile />} />
            <Route path="/vendor" element={<PlatformOnly><Vendor /></PlatformOnly>} />
            <Route path="/onboarding" element={<PlatformOnly><Onboarding /></PlatformOnly>} />
            <Route path="/leads" element={<PlatformOnly><Leads /></PlatformOnly>} />
            <Route path="/network" element={<PlatformOnly><NetworkStatus /></PlatformOnly>} />
            <Route path="/rust" element={<PlatformOnly><RustBridge /></PlatformOnly>} />
            <Route path="/how" element={<TenantEmployeeBlocked><HowItWorks /></TenantEmployeeBlocked>} />
            <Route path="/recovery" element={<KeyRecovery />} />
            <Route path="/recovery/ticket/:request_id" element={<KeyRecovery />} />
            <Route path="/logs" element={<PlatformOnly><Logs /></PlatformOnly>} />
            <Route path="/admin/health" element={<PlatformOnly><AdminHealth /></PlatformOnly>} />
          </Route>
        </Routes>
        <CookieBanner />
      </BrowserRouter>
      <Toaster
        theme="dark"
        position="bottom-right"
        toastOptions={{
          style: {
            background: "#111a2c",
            border: "1px solid #1e293b",
            color: "#ffffff",
            borderRadius: 0,
            fontFamily: "JetBrains Mono, monospace",
            fontSize: 12,
          },
        }}
      />
    </LangProvider>
  );
}

export default App;
