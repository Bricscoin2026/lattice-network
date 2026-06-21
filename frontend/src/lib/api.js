import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API,
  timeout: 15_000,
});

// RBAC — every request carries the active role chosen by the user.
export const ROLES = ["sovereign", "auditor", "vendor"];
export const ROLE_STORAGE_KEY = "lattice.rbac.role";

export function getActiveRole() {
  try {
    const r = localStorage.getItem(ROLE_STORAGE_KEY);
    return ROLES.includes(r) ? r : "sovereign";
  } catch {
    return "sovereign";
  }
}

export function setActiveRole(role) {
  if (!ROLES.includes(role)) return;
  try { localStorage.setItem(ROLE_STORAGE_KEY, role); } catch (e) { console.warn(e); }
}

api.interceptors.request.use((cfg) => {
  cfg.headers = cfg.headers || {};
  cfg.headers["X-Lattice-Role"] = getActiveRole();
  try {
    const token = localStorage.getItem("lattice.session.jwt");
    if (token) cfg.headers["Authorization"] = `Bearer ${token}`;
  } catch (e) { /* ignore */ }
  return cfg;
});

export function shortHash(h, head = 10, tail = 8) {
  if (!h) return "";
  if (h.length <= head + tail + 1) return h;
  return `${h.slice(0, head)}…${h.slice(-tail)}`;
}

export function fmtNumber(n) {
  if (typeof n !== "number") return "—";
  return n.toLocaleString("it-IT");
}

export function fmtBytes(n) {
  if (typeof n !== "number") return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(2)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export function fmtTime(iso, lang = "it") {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString(lang === "it" ? "it-IT" : "en-GB", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch {
    return iso;
  }
}

export function fmtClock(iso, lang = "it") {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString(lang === "it" ? "it-IT" : "en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  } catch {
    return "";
  }
}

export function fmtRelative(iso, lang = "it") {
  if (!iso) return "—";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  const s = Math.max(1, Math.floor(diff));
  const it = lang === "it";
  if (s < 60) return it ? `${s}s fa` : `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return it ? `${m}m fa` : `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return it ? `${h}h fa` : `${h}h ago`;
  const d = Math.floor(h / 24);
  return it ? `${d}g fa` : `${d}d ago`;
}
