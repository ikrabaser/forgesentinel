import type { AlertStatus } from "../api/types";

// Labels stay exact Title Case renderings of the backend's real
// AlertStatus values (OPEN/ACKNOWLEDGED/RESOLVED) - not renamed to
// something friendlier, so this reads consistently with the Alerts
// page and the raw status the API actually returns.
const STATUS_STYLE: Record<AlertStatus, { label: string; color: string }> = {
  OPEN: { label: "Open", color: "var(--high)" },
  ACKNOWLEDGED: { label: "Acknowledged", color: "var(--accent-secondary)" },
  RESOLVED: { label: "Resolved", color: "var(--text-tertiary)" },
};

/** Alert workflow status - distinct from severity, so it gets its own
 *  restrained pill rather than reusing severity colors. Text label is
 *  always present alongside the color so status doesn't rely on
 *  color alone. */
export function StatusPill({ status }: { status: AlertStatus }) {
  const { label, color } = STATUS_STYLE[status];
  return (
    <span
      className="inline-flex items-center gap-1.5 whitespace-nowrap text-[11px] font-medium"
      style={{ color }}
    >
      <span aria-hidden className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}
