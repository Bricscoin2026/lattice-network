import { Navigate } from "react-router-dom";
import { loadSession } from "@/lib/pqcAuth";

/**
 * Route guard:
 * - "platform" rotte (Ledger, Network, Leads, Onboarding, QBFT, Logs, Vendor)
 *   sono visibili solo all'operatore di rete (no tenant_id nel JWT, oppure
 *   accesso legacy/dev senza JWT).
 * - "tenant" rotte (Dashboard/LNS/Pulse/Certify) sono visibili a chiunque sia
 *   autenticato.
 */
export function PlatformOnly({ children }) {
  const session = loadSession();
  // Nessuna sessione → consideriamo l'utente come operatore (compatibilità con
  // la console legacy che non usa login). Tenant loggati hanno tenant_id.
  if (session && session.tenant_id) {
    return <Navigate to="/dashboard" replace />;
  }
  return children;
}

/**
 * Tenant employees (non-admin) are restricted to the Pulse + Certify
 * workspace. Any other route bounces them to /certify.
 */
export function TenantEmployeeBlocked({ children }) {
  const session = loadSession();
  if (session && session.tenant_id && session.role !== "admin") {
    return <Navigate to="/certify" replace />;
  }
  return children;
}

/**
 * Filtra il rendering della Dashboard: tenant autenticato → Tenant view,
 * altrimenti → Sovereign Operator view.
 */
export function isTenantUser() {
  const session = loadSession();
  return !!(session && session.tenant_id);
}
