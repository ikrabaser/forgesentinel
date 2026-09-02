import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { Alert, AlertSeverity, Asset } from "../api/types";
import { StatCard } from "../components/StatCard";
import { StatCardSkeleton } from "../components/StatCardSkeleton";
import { StatusDot } from "../components/StatusDot";
import { SecurityPostureCard } from "../components/SecurityPostureCard";
import { ThreatBreakdown } from "../components/ThreatBreakdown";
import { IncidentFeed } from "../components/IncidentFeed";
import { ServerIcon, RadioIcon, AlertTriangleIcon, ShieldAlertIcon } from "../components/icons";
import { useLiveData } from "../state/LiveDataContext";

const LATEST_ALERTS_SHOWN = 10;
// The backend has no dedicated "count of open alerts" endpoint yet, so
// this is a real (documented) simplification: stats reflect up to 200
// open alerts, not a true unbounded count. That's still a world away
// from the bug this replaced - see below.
const OPEN_ALERTS_STAT_LIMIT = 200;

function countBySeverity(alerts: Alert[]): Record<AlertSeverity, number> {
  const counts: Record<AlertSeverity, number> = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
  for (const alert of alerts) counts[alert.severity]++;
  return counts;
}

/** Trims a trailing ".0" (100.0 -> 100) without rounding away real
 *  precision (66.7 stays 66.7). */
function formatPercent(value: number): string {
  return Number(value.toFixed(1)).toString();
}

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

  // Stat cards + posture/breakdown: a SEPARATE, un-truncated merge -
  // counting from the same list the display slices from was the
  // original bug here (`.slice(0, 10)` then `.length` silently caps
  // the stat at 10 the moment there are 10+ open alerts, no matter
  // how many more arrive).
  const openAlertsForStats = useMemo(() => {
    const byId = new Map<number, Alert>();
    for (const alert of openAlertsSnapshot) byId.set(alert.id, alert);
    for (const alert of liveAlerts) {
      if (alert.status === "OPEN") byId.set(alert.id, alert);
      else byId.delete(alert.id); // acknowledged/resolved since the snapshot
    }
    return [...byId.values()];
  }, [openAlertsSnapshot, liveAlerts]);

  const severityCounts = useMemo(() => countBySeverity(openAlertsForStats), [openAlertsForStats]);
  const onlineCount = assets.filter((a) => a.status === "ONLINE").length;
  const onlinePct = assets.length > 0 ? (onlineCount / assets.length) * 100 : null;
  const activeAlertsCount = openAlertsForStats.length;

  if (loading) {
    return (
      <div className="flex flex-col gap-5 p-6 sm:p-8">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <StatCardSkeleton key={i} />
          ))}
        </div>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[13fr_7fr]">
          <div className="glass-panel h-48 rounded-[var(--radius-lg)] border border-[var(--border)]" />
          <div className="glass-panel h-48 rounded-[var(--radius-lg)] border border-[var(--border)]" />
        </div>
        <div className="glass-panel h-64 rounded-[var(--radius-lg)] border border-[var(--border)]" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5 p-6 sm:p-8">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Assets"
          value={assets.length}
          hint="Protected devices"
          icon={<ServerIcon className="h-4 w-4" />}
          index={0}
        />
        <StatCard
          label="Online"
          value={
            <span className="flex items-center gap-2.5">
              <StatusDot online={onlineCount > 0} />
              {onlineCount}
            </span>
          }
          hint={onlinePct !== null ? `${formatPercent(onlinePct)}% operational` : undefined}
          icon={<RadioIcon className="h-4 w-4" />}
          index={1}
        />
        <StatCard
          label="Active Alerts"
          value={activeAlertsCount}
          hint={
            activeAlertsCount === 0
              ? "No alerts require review"
              : `${activeAlertsCount} require${activeAlertsCount === 1 ? "s" : ""} review`
          }
          icon={<AlertTriangleIcon className="h-4 w-4" />}
          tone={activeAlertsCount > 0 ? "high" : "default"}
          index={2}
        />
        <StatCard
          label="Critical"
          value={severityCounts.CRITICAL}
          hint={severityCounts.CRITICAL > 0 ? "Requires immediate attention" : "No critical incidents"}
          icon={<ShieldAlertIcon className="h-4 w-4" />}
          tone={severityCounts.CRITICAL > 0 ? "critical" : "default"}
          index={3}
        />
      </div>

      <div className="grid grid-cols-1 items-stretch gap-4 lg:grid-cols-[13fr_7fr]">
        <SecurityPostureCard
          critical={severityCounts.CRITICAL}
          high={severityCounts.HIGH}
          medium={severityCounts.MEDIUM}
          low={severityCounts.LOW}
        />
        <ThreatBreakdown
          critical={severityCounts.CRITICAL}
          high={severityCounts.HIGH}
          medium={severityCounts.MEDIUM}
          low={severityCounts.LOW}
        />
      </div>

      <IncidentFeed alerts={latestAlerts} assets={assets} />
    </div>
  );
}
