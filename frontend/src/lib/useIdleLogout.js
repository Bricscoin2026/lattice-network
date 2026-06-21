/**
 * Idle session guard
 * ===================
 *
 * Forces a `clearSession()` after N minutes of no user activity
 * (mouse/keyboard/touch). Default 15 minutes; configurable via env var
 * `REACT_APP_IDLE_LOGOUT_MIN`.
 *
 * Hooked once at AppShell mount via `useIdleLogout()`. Activity events
 * are throttled to one update / 30s to avoid noise.
 *
 * On expiry: clears the session (sessionStorage), informs the server
 * via /api/auth/logout, then forces a redirect to `/login`.
 */
import { useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { clearSession, loadSession } from "@/lib/pqcAuth";
import { toast } from "sonner";

const IDLE_MIN = Number(process.env.REACT_APP_IDLE_LOGOUT_MIN || 15);
const IDLE_MS = IDLE_MIN * 60 * 1000;
const THROTTLE_MS = 30 * 1000;

export function useIdleLogout() {
  const lastSeen = useRef(Date.now());
  const timer = useRef(null);

  useEffect(() => {
    const session = loadSession();
    if (!session) return; // not logged in → nothing to guard
    if (IDLE_MS <= 0) return; // disabled

    const bump = () => {
      const now = Date.now();
      if (now - lastSeen.current > THROTTLE_MS) {
        lastSeen.current = now;
      }
    };

    const onExpire = async () => {
      try { await api.post("/auth/logout"); } catch (_e) { /* ignore */ }
      clearSession();
      toast.error(`Sessione scaduta per inattività (${IDLE_MIN} min) — accedi di nuovo`);
      setTimeout(() => { window.location.href = "/login"; }, 1500);
    };

    const tick = () => {
      if (Date.now() - lastSeen.current >= IDLE_MS) {
        onExpire();
        return;
      }
      timer.current = setTimeout(tick, 30 * 1000);
    };

    const events = ["mousemove", "mousedown", "keydown", "touchstart", "scroll", "visibilitychange"];
    events.forEach((ev) => window.addEventListener(ev, bump, { passive: true }));
    timer.current = setTimeout(tick, 30 * 1000);

    return () => {
      events.forEach((ev) => window.removeEventListener(ev, bump));
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);
}
