import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { Alert, AlertStatus } from "../api/types";
import { IncidentAnalysisPanel } from "../components/IncidentAnalysisPanel";
import { SeverityBadge } from "../components/SeverityBadge";
import { TableSkeleton } from "../components/TableSkeleton";
import { ChevronRightIcon } from "../components/icons";
import { useLiveData } from "../state/LiveDataContext";

const FILTERS: (AlertStatus | "ALL")[] = ["ALL", "OPEN", "ACKNOWLEDGED", "RESOLVED"];

export function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<AlertStatus | "ALL">("OPEN");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const { liveAlerts } = useLiveData();

  useEffect(() => {
    api
      .listAlerts(undefined, 200)
      .then(setAlerts)
      .finally(() => setLoading(false));
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
            className={`rounded px-3 py-1.5 font-mono text-xs transition-colors duration-200 ${
              filter === f
                ? "bg-[var(--accent-dim)] text-[var(--accent)]"
                : "text-[var(--text-tertiary)] hover:bg-white/[0.035]"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      <div className="glass-panel rounded-[var(--radius-lg)] border border-[var(--border)]">
        {loading && <TableSkeleton rows={5} columns={4} />}
        <AnimatePresence initial={false}>
          {!loading && visible.length === 0 && (
            <div className="px-5 py-8 text-center text-sm text-[var(--text-tertiary)]">
              No alerts match this filter.
            </div>
          )}
          {!loading &&
            visible.map((alert) => {
            const expanded = expandedId === alert.id;
            return (
              <motion.div
                key={alert.id}
                layout
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="border-b border-[var(--border)] last:border-b-0"
              >
                <div className="flex items-center gap-4 px-5 py-3">
                  <SeverityBadge severity={alert.severity} />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm text-[var(--text-primary)]">{alert.title}</div>
                    <div className="truncate text-xs text-[var(--text-tertiary)]">
                      {alert.description}
                    </div>
                  </div>
                  <span className="shrink-0 font-mono text-[10px] text-[var(--text-tertiary)]">
                    {alert.rule_id}
                  </span>
                  <div className="flex shrink-0 items-center gap-2">
                    {alert.status === "OPEN" && (
                      <button
                        disabled={busyId === alert.id}
                        onClick={() => handleAction(alert, "acknowledge")}
                        className="rounded border border-[var(--border-strong)] px-2.5 py-1 text-xs text-[var(--text-secondary)] transition-colors duration-200 hover:bg-white/[0.035] disabled:opacity-40"
                      >
                        Acknowledge
                      </button>
                    )}
                    {alert.status !== "RESOLVED" && (
                      <button
                        disabled={busyId === alert.id}
                        onClick={() => handleAction(alert, "resolve")}
                        className="rounded border border-[var(--accent)]/40 bg-[var(--accent-dim)] px-2.5 py-1 text-xs text-[var(--accent)] transition-colors duration-200 hover:bg-[var(--accent)]/20 disabled:opacity-40"
                      >
                        Resolve
                      </button>
                    )}
                    {alert.status === "RESOLVED" && (
                      <span className="px-2.5 py-1 font-mono text-[11px] text-[var(--text-tertiary)]">
                        RESOLVED
                      </span>
                    )}
                    <button
                      onClick={() => setExpandedId(expanded ? null : alert.id)}
                      aria-label={expanded ? "Hide AI analysis" : "Show AI analysis"}
                      className="rounded p-1 text-[var(--text-tertiary)] transition-colors duration-200 hover:text-[var(--accent)]"
                    >
                      <ChevronRightIcon
                        className={`h-4 w-4 transition-transform duration-200 ${expanded ? "rotate-90" : ""}`}
                      />
                    </button>
                  </div>
                </div>

                <AnimatePresence>
                  {expanded && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      className="overflow-hidden px-5 pb-4"
                    >
                      <IncidentAnalysisPanel alertId={alert.id} />
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}
