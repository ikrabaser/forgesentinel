import { motion } from "framer-motion";
import type { ReactNode } from "react";

interface StatCardProps {
  label: string;
  value: ReactNode;
  /** Small supporting line under the value - only pass real derived
   *  context (e.g. "6 of 6 assets online"), never an invented trend. */
  hint?: ReactNode;
  icon?: ReactNode;
  tone?: "default" | "critical" | "high";
  index?: number;
}

const TONE_ACCENT: Record<NonNullable<StatCardProps["tone"]>, string> = {
  default: "var(--accent)",
  high: "var(--high)",
  critical: "var(--critical)",
};

export function StatCard({ label, value, hint, icon, tone = "default", index = 0 }: StatCardProps) {
  const accent = TONE_ACCENT[tone];

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.35, delay: index * 0.05, ease: [0.16, 1, 0.3, 1] }}
      className="glass-panel relative overflow-hidden rounded-[var(--radius-md)] border border-[var(--border)] p-6 transition-colors duration-200 hover:border-[var(--border-strong)] hover:shadow-[var(--shadow-lg)]"
    >
      <span aria-hidden className="absolute inset-y-0 left-0 w-[2px]" style={{ background: accent, opacity: 0.55 }} />

      <div className="flex items-start justify-between gap-3">
        <div className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
          {label}
        </div>
        {icon && (
          <span
            aria-hidden
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius-sm)] border"
            style={{
              background: `radial-gradient(circle at 30% 25%, color-mix(in srgb, ${accent} 18%, transparent), transparent 72%)`,
              borderColor: `color-mix(in srgb, ${accent} 20%, transparent)`,
              color: accent,
            }}
          >
            {icon}
          </span>
        )}
      </div>
      <div className="mt-3 font-mono text-[32px] font-semibold leading-none tracking-tight tabular-nums text-[var(--text-primary)]">
        {value}
      </div>
      {hint && <div className="mt-2.5 text-[12px] text-[var(--text-tertiary)]">{hint}</div>}
    </motion.div>
  );
}
