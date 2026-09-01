import { useMemo } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import type { Alert, Asset } from "../api/types";
import { SeverityBadge } from "./SeverityBadge";
import { StatusPill } from "./StatusPill";
import { ChevronRightIcon, InboxIcon } from "./icons";
import { timeAgo } from "../lib/time";

interface IncidentFeedProps {
  alerts: Alert[];
  assets: Asset[];
}

const GRID_COLS = "grid-cols-[auto_minmax(0,1fr)_130px_96px_128px_20px]";

/**
 * Premium incident feed for the overview - a table on desktop that
 * collapses into readable cards below md, built from the same
 * REST + live-merged alert list the old "Latest Alerts" panel used.
 * No alert data is invented here; asset names are resolved from the
 * real asset list already fetched by the overview page.
 */
export function IncidentFeed({ alerts, assets }: IncidentFeedProps) {
  const assetByCode = useMemo(() => {
    const map = new Map<number, Asset>();
    for (const asset of assets) map.set(asset.id, asset);
    return map;
  }, [assets]);

  return (
    <section className="glass-panel overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border)]">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
        <h3 className="text-[14px] font-semibold text-[var(--text-primary)]">Latest Alerts</h3>
        <Link
          to="/alerts"
          className="text-[12px] font-medium text-[var(--accent)] transition-colors duration-200 hover:text-[var(--text-primary)]"
        >
          View all
        </Link>
      </div>

      {alerts.length === 0 ? (
        <div className="flex flex-col items-center gap-2 px-6 py-14 text-center">
          <InboxIcon className="h-5 w-5 text-[var(--text-tertiary)]" />
          <span className="text-[13px] text-[var(--text-tertiary)]">No alerts recorded yet.</span>
        </div>
      ) : (
        <>
          <div
            className={`surface-2 hidden ${GRID_COLS} gap-5 border-b border-[var(--border)] px-6 py-2.5 text-[10px] font-medium uppercase tracking-wider text-[var(--text-tertiary)] md:grid`}
          >
            <span>Severity</span>
            <span>Alert</span>
            <span>Asset</span>
            <span>Time</span>
            <span>Status</span>
            <span />
          </div>

          <div className="divide-y divide-[var(--border)]">
            {alerts.map((alert, i) => {
              const asset = assetByCode.get(alert.asset_id);
              return (
                <motion.div
                  key={alert.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: Math.min(i, 8) * 0.02 }}
                  className={`group relative flex flex-col gap-2.5 px-6 py-4 transition-colors duration-200 hover:bg-white/[0.035] md:grid md:items-center md:gap-5 ${GRID_COLS}`}
                >
                  <span
                    aria-hidden
                    className="absolute inset-y-0 left-0 w-[2px] scale-y-0 bg-[var(--accent)] opacity-70 transition-transform duration-200 group-hover:scale-y-100"
                  />

                  <div className="flex items-center justify-between md:block">
                    <SeverityBadge severity={alert.severity} />
                    <span className="font-mono text-[10px] text-[var(--text-tertiary)] md:hidden">
                      {timeAgo(alert.created_at)}
                    </span>
                  </div>

                  <div className="min-w-0">
                    <div className="truncate text-[14px] font-medium text-[var(--text-primary)]">
                      {alert.title}
                    </div>
                    <div className="mt-0.5 truncate text-[12.5px] text-[var(--text-secondary)]">
                      {alert.description}
                    </div>
                  </div>

                  <div className="font-mono text-[12px] text-[var(--text-secondary)]">
                    {asset?.asset_code ?? `#${alert.asset_id}`}
                  </div>

                  <div className="hidden font-mono text-[12px] text-[var(--text-tertiary)] md:block">
                    {timeAgo(alert.created_at)}
                  </div>

                  <div className="flex items-center justify-between md:block">
                    <StatusPill status={alert.status} />
                  </div>

                  <ChevronRightIcon
                    aria-hidden
                    className="hidden h-3.5 w-3.5 shrink-0 text-[var(--text-tertiary)] opacity-0 transition-opacity duration-200 group-hover:opacity-100 md:block"
                  />
                </motion.div>
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}
