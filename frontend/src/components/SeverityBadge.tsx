import type { AlertSeverity } from "../api/types";

const SEVERITY_STYLES: Record<AlertSeverity, string> = {
  LOW: "text-[var(--severity-low)] bg-[var(--severity-low)]/10 border-[var(--severity-low)]/30",
  MEDIUM:
    "text-[var(--severity-medium)] bg-[var(--severity-medium)]/10 border-[var(--severity-medium)]/30",
  HIGH: "text-[var(--severity-high)] bg-[var(--severity-high)]/10 border-[var(--severity-high)]/30",
  CRITICAL:
    "text-[var(--severity-critical)] bg-[var(--severity-critical)]/10 border-[var(--severity-critical)]/40",
};

export function SeverityBadge({ severity }: { severity: AlertSeverity }) {
  return (
    <span
      className={`inline-flex items-center rounded border px-2 py-0.5 text-[11px] font-mono font-semibold tracking-wide ${SEVERITY_STYLES[severity]}`}
    >
      {severity}
    </span>
  );
}
