import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ShieldAlertIcon, ShieldCheckIcon, ArrowUpRightIcon } from "./icons";
import { derivePosture, type SecurityPosture, type SeverityCounts } from "../lib/posture";

type SecurityPostureCardProps = SeverityCounts;

const POSTURE_STYLE: Record<
  SecurityPosture,
  { color: string; copy: (counts: SeverityCounts) => string }
> = {
  Critical: {
    color: "var(--critical)",
    copy: (c) =>
      `${c.critical} critical alert${c.critical === 1 ? "" : "s"} require immediate attention across monitored assets.`,
  },
  "Elevated Risk": {
    color: "var(--high)",
    copy: (c) =>
      `${c.high} high-severity alert${c.high === 1 ? "" : "s"} require${c.high === 1 ? "s" : ""} investigation.`,
  },
  Guarded: {
    color: "var(--medium)",
    copy: (c) =>
      `${c.medium} medium-severity alert${c.medium === 1 ? "" : "s"} being monitored, no elevated findings.`,
  },
  Healthy: {
    color: "var(--success)",
    copy: () => "No unresolved alerts across monitored assets. All systems within expected range.",
  },
};

const RAIL_ROWS: { key: keyof SeverityCounts; label: string; color: string }[] = [
  { key: "critical", label: "Critical", color: "var(--critical)" },
  { key: "high", label: "High", color: "var(--high)" },
  { key: "medium", label: "Medium", color: "var(--medium)" },
];

/**
 * The overview's primary focal card: current posture on the left,
 * a compact "risk rail" - a vertical segmented severity indicator
 * plus the three counts it represents - on the right, so the card
 * reads as one intentional composition rather than a headline
 * floating in empty space.
 */
export function SecurityPostureCard({ critical, high, medium, low }: SecurityPostureCardProps) {
  const counts = { critical, high, medium, low };
  const posture = derivePosture(counts);
  const style = POSTURE_STYLE[posture];
  const railTotal = critical + high + medium;
  const Icon = posture === "Healthy" || posture === "Guarded" ? ShieldCheckIcon : ShieldAlertIcon;

  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
      className="glass-panel relative flex h-full flex-col overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border)] p-6 sm:p-7"
      aria-label="Security posture"
    >
      <span
        aria-hidden
        className="absolute inset-y-0 left-0 w-[3px]"
        style={{
          background: style.color,
          boxShadow: `0 0 14px -3px color-mix(in srgb, ${style.color} 60%, transparent)`,
        }}
      />

      <div className="grid flex-1 grid-cols-1 gap-7 lg:grid-cols-[1fr_236px] lg:items-center">
        <div className="flex min-w-0 flex-col justify-center">
          <div className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
            Security Posture
          </div>
          <div className="mt-2.5 flex items-center gap-3">
            <Icon className="h-7 w-7 shrink-0" style={{ color: style.color }} />
            <h2 className="text-[30px] font-semibold leading-none tracking-tight" style={{ color: style.color }}>
              {posture}
            </h2>
          </div>
          <p className="mt-3 max-w-md text-[14px] leading-relaxed text-[var(--text-secondary)]">
            {style.copy(counts)}
          </p>

          <Link
            to="/alerts"
            className="group mt-5 inline-flex w-fit items-center gap-1.5 rounded-[var(--radius-sm)] border border-[var(--border)] bg-white/[0.02] px-3.5 py-2 text-[12.5px] font-medium text-[var(--accent)] transition-colors duration-200 hover:border-[var(--accent)]/30 hover:bg-[var(--accent-dim)] hover:text-[var(--text-primary)]"
          >
            View threat analysis
            <ArrowUpRightIcon className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
          </Link>
        </div>

        <div className="surface-2 flex shrink-0 gap-4 rounded-[var(--radius-md)] border border-[var(--border)] p-4">
          <div className="flex shrink-0 flex-col gap-1.5" aria-hidden>
            {RAIL_ROWS.map(({ key, color }) => {
              const value = counts[key];
              const weight = railTotal > 0 ? value / railTotal : 0;
              // Every active severity gets a visible sliver even at a
              // low share of the total; an inactive one collapses to
              // the bare track so the rail never implies a finding
              // that isn't there.
              const flexGrow = value > 0 ? Math.max(weight, 0.16) : 0.001;
              return (
                <span
                  key={key}
                  className="w-2 rounded-full"
                  style={{
                    flexGrow,
                    background: value > 0 ? color : "rgba(255,255,255,0.06)",
                  }}
                />
              );
            })}
          </div>

          <div className="flex flex-1 flex-col justify-between gap-2.5">
            {RAIL_ROWS.map(({ key, label, color }) => (
              <div key={key} className="flex items-baseline justify-between gap-3">
                <span className="text-[12px] text-[var(--text-secondary)]">{label}</span>
                <span
                  className="font-mono text-[20px] font-semibold leading-none tabular-nums"
                  style={{ color: counts[key] > 0 ? color : "var(--text-tertiary)" }}
                >
                  {counts[key]}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </motion.section>
  );
}
