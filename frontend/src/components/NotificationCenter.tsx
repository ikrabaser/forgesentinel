import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { api } from "../api/client";
import type { Alert, AlertSeverity } from "../api/types";
import { useLiveData } from "../state/LiveDataContext";
import { SeverityBadge } from "./SeverityBadge";
import { BellIcon, CloseIcon, InboxIcon } from "./icons";
import { timeAgo } from "../lib/time";

const PANEL_ALERTS_SHOWN = 8;
const SEVERITY_RANK: Record<AlertSeverity, number> = { CRITICAL: 3, HIGH: 2, MEDIUM: 1, LOW: 0 };
const SEVERITY_DOT_COLOR: Record<AlertSeverity, string> = {
  CRITICAL: "var(--critical)",
  HIGH: "var(--high)",
  MEDIUM: "var(--medium)",
  LOW: "var(--accent)",
};

/**
 * Header notification affordance: a bell button that opens a small
 * panel over the existing alert data (REST snapshot + whatever has
 * arrived live via LiveDataContext since). This restructures the
 * existing alert stream into a persistent, dismissible surface - it
 * does not invent a new notification backend or alert type.
 */
export function NotificationCenter() {
  const [open, setOpen] = useState(false);
  const [recentAlerts, setRecentAlerts] = useState<Alert[]>([]);
  const { liveAlerts } = useLiveData();
  const containerRef = useRef<HTMLDivElement>(null);
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    api.listAlerts(undefined, PANEL_ALERTS_SHOWN * 3).then(setRecentAlerts);
  }, []);

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(event: PointerEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open]);

  const merged = useMemo(() => {
    const byId = new Map<number, Alert>();
    for (const alert of [...liveAlerts, ...recentAlerts]) byId.set(alert.id, alert);
    return [...byId.values()].sort((a, b) => b.id - a.id);
  }, [liveAlerts, recentAlerts]);

  const openAlerts = useMemo(() => merged.filter((a) => a.status === "OPEN"), [merged]);
  const shown = merged.slice(0, PANEL_ALERTS_SHOWN);

  const indicatorColor = useMemo(() => {
    if (openAlerts.length === 0) return null;
    const highest = openAlerts.reduce((worst, alert) =>
      SEVERITY_RANK[alert.severity] > SEVERITY_RANK[worst.severity] ? alert : worst,
    );
    return SEVERITY_DOT_COLOR[highest.severity];
  }, [openAlerts]);

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="true"
        aria-expanded={open}
        aria-label={
          openAlerts.length > 0
            ? `Notifications, ${openAlerts.length} open alert${openAlerts.length === 1 ? "" : "s"}`
            : "Notifications"
        }
        className="relative flex h-9 w-9 items-center justify-center rounded-md border border-[var(--border)] text-[var(--text-secondary)] transition-colors duration-200 hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]"
      >
        <BellIcon className="h-4 w-4" />
        {indicatorColor && (
          <span
            aria-hidden
            className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full"
            style={{ background: indicatorColor }}
          />
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            role="dialog"
            aria-label="Notifications"
            initial={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.16, ease: [0.16, 1, 0.3, 1] }}
            className="glass-panel absolute right-0 top-11 z-50 w-[340px] overflow-hidden rounded-[var(--radius-md)] border border-[var(--border-strong)]"
          >
            <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
              <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                Notifications
              </span>
              <div className="flex items-center gap-3">
                <span className="font-mono text-[11px] text-[var(--text-tertiary)]">
                  {openAlerts.length} open
                </span>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  aria-label="Close notifications"
                  className="flex h-5 w-5 items-center justify-center rounded text-[var(--text-tertiary)] transition-colors duration-200 hover:text-[var(--text-primary)]"
                >
                  <CloseIcon className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

            <div className="max-h-[360px] overflow-y-auto">
              {shown.length === 0 ? (
                <div className="flex flex-col items-center gap-2 px-4 py-10 text-center">
                  <InboxIcon className="h-5 w-5 text-[var(--text-tertiary)]" />
                  <span className="text-[12px] text-[var(--text-tertiary)]">
                    No alerts recorded yet.
                  </span>
                </div>
              ) : (
                shown.map((alert) => (
                  <div
                    key={alert.id}
                    className="border-b border-[var(--border)] px-4 py-3 last:border-b-0"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <SeverityBadge severity={alert.severity} />
                      <span className="shrink-0 font-mono text-[10px] text-[var(--text-tertiary)]">
                        {timeAgo(alert.created_at)}
                      </span>
                    </div>
                    <div className="mt-1.5 text-[13px] text-[var(--text-primary)]">
                      {alert.title}
                    </div>
                    <div className="mt-0.5 line-clamp-1 text-[12px] text-[var(--text-secondary)]">
                      {alert.description}
                    </div>
                  </div>
                ))
              )}
            </div>

            <Link
              to="/alerts"
              onClick={() => setOpen(false)}
              className="block border-t border-[var(--border)] px-4 py-2.5 text-center text-[12px] font-medium text-[var(--accent)] transition-colors duration-200 hover:bg-white/[0.03]"
            >
              View all alerts
            </Link>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
