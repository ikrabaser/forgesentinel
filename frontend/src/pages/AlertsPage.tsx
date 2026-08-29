import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { Alert, AlertStatus } from "../api/types";
import { SeverityBadge } from "../components/SeverityBadge";
import { useLiveData } from "../state/LiveDataContext";

const FILTERS: (AlertStatus | "ALL")[] = ["ALL", "OPEN", "ACKNOWLEDGED", "RESOLVED"];

export function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [filter, setFilter] = useState<AlertStatus | "ALL">("OPEN");
  const [busyId, setBusyId] = useState<number | null>(null);
  const { liveAlerts } = useLiveData();

  useEffect(() => {
    api.listAlerts(undefined, 200).then(setAlerts);
  }, []);

  const combined = useMemo(() => {
    const byId = new Map<number, Alert>();
    for (const alert of [...liveAlerts, ...alerts]) byId.set(alert.id, alert);
    return [...byId.values()].sort((a, b) => b.id - a.id);
  }, [alerts, liveAlerts]);

  const visible = filter === "ALL" ? combined : combined.filter((a) => a.status === filter);

  async function handleAction(alert: Alert, action: "acknowledge" | "resolve") {
    setBusyId(alert.id);
    try {
      const updated =
        action === "acknowledge"
          ? await api.acknowledgeAlert(alert.id)
          : await api.resolveAlert(alert.id);
      setAlerts((prev) => {
        const withoutOld = prev.filter((a) => a.id !== updated.id);
        return [updated, ...withoutOld];
      });
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="flex flex-col gap-4 p-8">
      <div className="flex gap-2">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded px-3 py-1.5 font-mono text-xs transition-colors ${
              filter === f
                ? "bg-[var(--accent-dim)] text-[var(--accent)]"
                : "text-[var(--text-dim)] hover:bg-[var(--bg-panel-raised)]"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      <div className="glass-panel rounded-xl border border-[var(--border)]">
        <AnimatePresence initial={false}>
          {visible.length === 0 && (
            <div className="px-5 py-8 text-center text-sm text-[var(--text-dim)]">
              No alerts match this filter.
            </div>
          )}
          {visible.map((alert) => (
            <motion.div
              key={alert.id}
              layout
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="flex items-center gap-4 border-b border-[var(--border)] px-5 py-3 last:border-b-0"
            >
              <SeverityBadge severity={alert.severity} />
              <div className="min-w-0 flex-1">
                <div className="text-sm text-[var(--text-bright)]">{alert.title}</div>
                <div className="truncate text-xs text-[var(--text-dim)]">
                  {alert.description}
                </div>
              </div>
              <span className="shrink-0 font-mono text-[10px] text-[var(--text-dim)]">
                {alert.rule_id}
              </span>
              <div className="flex shrink-0 gap-2">
                {alert.status === "OPEN" && (
                  <button
                    disabled={busyId === alert.id}
                    onClick={() => handleAction(alert, "acknowledge")}
                    className="rounded border border-[var(--border-strong)] px-2.5 py-1 text-xs text-[var(--text)] transition-colors hover:bg-[var(--bg-panel-raised)] disabled:opacity-40"
                  >
                    Acknowledge
                  </button>
                )}
                {alert.status !== "RESOLVED" && (
                  <button
                    disabled={busyId === alert.id}
                    onClick={() => handleAction(alert, "resolve")}
                    className="rounded border border-[var(--accent)]/40 bg-[var(--accent-dim)] px-2.5 py-1 text-xs text-[var(--accent)] transition-colors hover:bg-[var(--accent)]/20 disabled:opacity-40"
                  >
                    Resolve
                  </button>
                )}
                {alert.status === "RESOLVED" && (
                  <span className="px-2.5 py-1 font-mono text-[11px] text-[var(--text-dim)]">
                    RESOLVED
                  </span>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
