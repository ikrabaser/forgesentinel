import type { AuditAction } from "../api/types";

// Same visual language as SeverityBadge, but the color mapping
// encodes something different: not "how dangerous" but "how
// sensitive an action category is" - MODBUS_WRITE gets the critical
// treatment because (per detection/rules/suspicious_configuration_
// change.py) there is currently no legitimate writer at all, so
// *every* occurrence is worth an operator's attention, not just some.
const ACTION_STYLES: Record<string, string> = {
  ALERT_ACKNOWLEDGED:
    "text-[var(--accent-secondary)] bg-[var(--accent-secondary)]/10 border-[var(--accent-secondary)]/30",
  ALERT_RESOLVED: "text-[var(--success)] bg-[var(--success)]/10 border-[var(--success)]/30",
  INCIDENT_ANALYSIS_REQUESTED: "text-[var(--accent)] bg-[var(--accent)]/10 border-[var(--accent)]/30",
  MODBUS_WRITE: "text-[var(--critical)] bg-[var(--critical)]/10 border-[var(--critical)]/40",
};

const FALLBACK_STYLE = "text-[var(--text-tertiary)] bg-white/5 border-[var(--border-strong)]";

export function ActionBadge({ action }: { action: AuditAction | string }) {
  return (
    <span
      className={`inline-flex items-center rounded border px-2 py-0.5 text-[11px] font-mono font-semibold tracking-wide ${
        ACTION_STYLES[action] ?? FALLBACK_STYLE
      }`}
    >
      {action}
    </span>
  );
}
