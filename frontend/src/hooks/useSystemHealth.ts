// Polls the existing GET /health endpoint (defined in api/client.ts,
// previously unused by the UI) so the sidebar's system health panel
// reflects a real backend/database check rather than an invented
// status. A dropped poll is treated as "unknown", not "healthy" - a
// security console should never silently claim health it hasn't
// actually confirmed.

import { useEffect, useState } from "react";
import { api } from "../api/client";

export type SystemHealthState = "checking" | "healthy" | "degraded" | "unknown";

const POLL_INTERVAL_MS = 30_000;

export function useSystemHealth(): SystemHealthState {
  const [state, setState] = useState<SystemHealthState>("checking");

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const result = await api.health();
        if (cancelled) return;
        setState(result.status === "ok" ? "healthy" : "degraded");
      } catch {
        if (!cancelled) setState("unknown");
      }
    }

    poll();
    const interval = window.setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  return state;
}
