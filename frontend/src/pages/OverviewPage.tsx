import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { api } from "../api/client";
import type { Alert, Asset } from "../api/types";
import { StatCard } from "../components/StatCard";
import { SeverityBadge } from "../components/SeverityBadge";
import { StatusDot } from "../components/StatusDot";
import { useLiveData } from "../state/LiveDataContext";

const LATEST_ALERTS_SHOWN = 10;
// The backend has no dedicated "count of open alerts" endpoint yet, so
// this is a real (documented) simplification: stats reflect up to 200
// open alerts, not a true unbounded count. That's still a world away
// from the bug this replaced - see below.
const OPEN_ALERTS_STAT_LIMIT = 200;

export function OverviewPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [recentAlerts, setRecentAlerts] = useState<Alert[]>([]);
  const [openAlertsSnapshot, setOpenAlertsSnapshot] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const { liveAlerts } = useLiveData();

  useEffect(() => {
    Promise.all([
      api.listAssets(),
      api.listAlerts(undefined, LATEST_ALERTS_SHOWN * 2),
      api.listAlerts("OPEN", OPEN_ALERTS_STAT_LIMIT),
    ])
      .then(([assetList, recent, open]) => {
        setAssets(assetList);
        setRecentAlerts(recent);
        setOpenAlertsSnapshot(open);
      })
      .finally(() => setLoading(false));
  }, []);

  // "Latest Alerts" panel: REST snapshot merged with anything that's
  // arrived live since, newest first, deduped by id, capped for
  // DISPLAY only.
  const latestAlerts = useMemo(() => {
    const byId = new Map<number, Alert>();
    for (const alert of [...liveAlerts, ...recentAlerts]) byId.set(alert.id, alert);
    return [...byId.values()].sort((a, b) => b.id - a.id).slice(0, LATEST_ALERTS_SHOWN);
  }, [recentAlerts, liveAlerts]);

  // Stat cards: a SEPARATE, un-truncated merge - counting from the
  // same list the display slices from was the original bug here
  // (`.slice(0, 10)` then `.length` silently caps the stat at 10 the
  // moment there are 10+ open alerts, no matter how many more arrive).
  const openAlertsForStats = useMemo(() => {
    const byId = new Map<number, Alert>();
    for (const alert of openAlertsSnapshot) byId.set(alert.id, alert);
    for (const alert of liveAlerts) {
      if (alert.status === "OPEN") byId.set(alert.id, alert);
      else byId.delete(alert.id); // acknowledged/resolved since the snapshot
    }
    return [...byId.values()];
  }, [openAlertsSnapshot, liveAlerts]);

  const onlineCount = assets.filter((a) => a.status === "ONLINE").length;
  const criticalCount = openAlertsForStats.filter((a) => a.severity === "CRITICAL").length;

  if (loading) {
    return <div className="p-8 text-sm text-[var(--text-dim)]">Loading…</div>;
  }

  return (
    <div className="flex flex-col gap-6 p-8">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Assets" value={assets.length} index={0} />
        <StatCard
          label="Online"
          value={
            <span className="flex items-center gap-2">
              <StatusDot online={onlineCount > 0} />
              {onlineCount}
            </span>
          }
          index={1}
        />
        <StatCard
          label="Active Alerts"
          value={openAlertsForStats.length}
          tone={openAlertsForStats.length > 0 ? "high" : "default"}
          index={2}
        />
        <StatCard
          label="Critical"
          value={criticalCount}
          tone={criticalCount > 0 ? "critical" : "default"}
          index={3}
        />
      </div>

      <div className="glass-panel rounded-xl border border-[var(--border)]">
        <div className="border-b border-[var(--border)] px-6 py-4 text-sm font-semibold text-[var(--text-bright)]">
          Latest Alerts
        </div>
        <div className="divide-y divide-[var(--border)]">
          {latestAlerts.length === 0 && (
            <div className="px-5 py-6 text-sm text-[var(--text-dim)]">No alerts recorded yet.</div>
          )}
          {latestAlerts.map((alert, i) => (
            <motion.div
              key={alert.id}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: i * 0.02 }}
              className="flex items-center gap-4 px-5 py-3"
            >
              <SeverityBadge severity={alert.severity} />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm text-[var(--text-bright)]">{alert.title}</div>
                <div className="truncate text-xs text-[var(--text-dim)]">
                  {alert.description}
                </div>
              </div>
              <span className="shrink-0 font-mono text-[11px] text-[var(--text-dim)]">
                {alert.status}
              </span>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}
