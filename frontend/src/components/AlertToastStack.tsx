import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { useLiveData } from "../state/LiveDataContext";
import { SeverityBadge } from "./SeverityBadge";
import type { Alert } from "../api/types";

const VISIBLE_MS = 6000;
const MAX_VISIBLE_TOASTS = 4;

/**
 * Global toast stack: whenever a NEW alert arrives over the
 * WebSocket, it slides in here regardless of which page is open. This
 * is the one place in the UI where "animated" earns its keep on
 * genuine functional grounds, not just decoration - a security
 * dashboard's whole job is making sure a fresh alert is impossible to
 * miss, even if the analyst is looking at the Assets page.
 */
export function AlertToastStack() {
  const { liveAlerts } = useLiveData();
  const [visible, setVisible] = useState<Alert[]>([]);
  // Each toast's dismiss timer is tracked independently by alert id.
  // A naive `useEffect(() => { ...; return () => clearTimeout(t) },
  // [liveAlerts[0]?.id])` looks reasonable but has a real bug: React
  // runs the PREVIOUS effect's cleanup before the NEXT run whenever
  // the dependency changes - so the moment alert #2 arrives, it
  // cancels alert #1's still-pending dismiss timer. If alerts arrive
  // faster than VISIBLE_MS (exactly what happens during a real alert
  // burst), every earlier toast's timer gets cancelled by the next
  // one's arrival and NONE of them ever auto-dismiss. Keeping timers
  // in a ref, keyed by alert id, makes each one independent of
  // whether another alert shows up in the meantime.
  const timers = useRef<Map<number, number>>(new Map());

  useEffect(() => {
    const newest = liveAlerts[0];
    if (!newest || timers.current.has(newest.id)) return;

    setVisible((prev) => [newest, ...prev]);

    const timer = window.setTimeout(() => {
      setVisible((prev) => prev.filter((a) => a.id !== newest.id));
      timers.current.delete(newest.id);
    }, VISIBLE_MS);
    timers.current.set(newest.id, timer);
  }, [liveAlerts]);

  useEffect(() => {
    const timersMap = timers.current;
    return () => {
      timersMap.forEach((timer) => window.clearTimeout(timer));
      timersMap.clear();
    };
  }, []);

  const shown = visible.slice(0, MAX_VISIBLE_TOASTS);
  const overflow = visible.length - shown.length;

  return (
    <div className="pointer-events-none fixed right-4 top-20 z-50 flex w-80 flex-col gap-2">
      <AnimatePresence>
        {shown.map((alert) => (
          <motion.div
            key={alert.id}
            layout
            initial={{ opacity: 0, x: 40, scale: 0.95 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 40, scale: 0.95 }}
            transition={{ type: "spring", stiffness: 300, damping: 28 }}
            className="glass-panel pointer-events-auto rounded-xl border border-[var(--border-strong)] p-3.5 shadow-2xl shadow-black/50"
          >
            <div className="mb-1.5 flex items-center justify-between gap-2">
              <SeverityBadge severity={alert.severity} />
              <span className="font-mono text-[10px] text-[var(--text-dim)]">
                {alert.rule_id}
              </span>
            </div>
            <div className="text-sm font-medium text-[var(--text-bright)]">{alert.title}</div>
            <div className="mt-0.5 line-clamp-2 text-xs text-[var(--text-dim)]">
              {alert.description}
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
      {overflow > 0 && (
        <div className="pointer-events-none text-right font-mono text-[11px] text-[var(--text-dim)]">
          +{overflow} more
        </div>
      )}
    </div>
  );
}
