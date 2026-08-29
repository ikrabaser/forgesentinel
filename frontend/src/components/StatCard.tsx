import { motion } from "framer-motion";
import type { ReactNode } from "react";

interface StatCardProps {
  label: string;
  value: ReactNode;
  tone?: "default" | "critical" | "high";
  index?: number;
}

const TONE_ACCENT: Record<NonNullable<StatCardProps["tone"]>, string> = {
  default: "var(--accent)",
  high: "var(--severity-high)",
  critical: "var(--severity-critical)",
};

export function StatCard({ label, value, tone = "default", index = 0 }: StatCardProps) {
  const accent = TONE_ACCENT[tone];

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.4, delay: index * 0.06, ease: [0.16, 1, 0.3, 1] }}
      className="glass-panel relative overflow-hidden rounded-xl border border-[var(--border)] px-5 py-4 transition-shadow"
      style={{ boxShadow: tone !== "default" ? `0 0 0 1px ${accent}22, 0 8px 24px -12px ${accent}55` : undefined }}
    >
      <span
        className="absolute inset-x-0 top-0 h-[2px]"
        style={{ background: `linear-gradient(90deg, transparent, ${accent}, transparent)` }}
      />
      <div className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-dim)]">
        {label}
      </div>
      <div className="mt-1.5 text-[28px] font-bold leading-none text-[var(--text-bright)]">
        {value}
      </div>
    </motion.div>
  );
}
