import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import type { AlertSeverity } from "../api/types";
import type { SeverityCounts } from "../lib/posture";

const SEVERITY_ORDER: { key: keyof SeverityCounts; label: AlertSeverity; color: string }[] = [
  { key: "critical", label: "CRITICAL", color: "var(--critical)" },
  { key: "high", label: "HIGH", color: "var(--high)" },
  { key: "medium", label: "MEDIUM", color: "var(--medium)" },
  { key: "low", label: "LOW", color: "var(--severity-low)" },
];

/**
 * Open-alert severity distribution - the honest visualization used
 * in place of a fabricated historical trend line, reusing recharts
 * (already a project dependency for the telemetry chart) rather than
 * adding a new charting library. Deliberately compact: this sits
 * beside the (wider) posture card, not stretched across the page.
 */
export function ThreatBreakdown({ critical, high, medium, low }: SeverityCounts) {
  const counts = { critical, high, medium, low };
  const total = critical + high + medium + low;
  const segments = SEVERITY_ORDER.filter((s) => counts[s.key] > 0);

  return (
    <section className="glass-panel flex h-full flex-col gap-4 rounded-[var(--radius-lg)] border border-[var(--border)] p-5 sm:p-6">
      <div>
        <h3 className="text-[14px] font-semibold text-[var(--text-primary)]">Threat Breakdown</h3>
        <p className="mt-0.5 text-[12px] text-[var(--text-tertiary)]">Open alerts by severity</p>
      </div>

      <div className="flex flex-1 items-center gap-5">
        <div className="relative h-[92px] w-[92px] shrink-0">
          {total > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={segments.map((s) => ({ name: s.label, value: counts[s.key] }))}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={30}
                  outerRadius={45}
                  paddingAngle={segments.length > 1 ? 3 : 0}
                  stroke="none"
                  isAnimationActive
                  animationDuration={400}
                >
                  {segments.map((s) => (
                    <Cell key={s.key} fill={s.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-full w-full items-center justify-center rounded-full border border-dashed border-[var(--border-strong)]">
              <span className="text-[10px] text-[var(--text-tertiary)]">No data</span>
            </div>
          )}
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span className="font-mono text-[17px] font-semibold leading-none text-[var(--text-primary)]">
              {total}
            </span>
            <span className="mt-0.5 text-[8.5px] uppercase tracking-wider text-[var(--text-tertiary)]">
              Open
            </span>
          </div>
        </div>

        <ul className="flex min-w-0 flex-1 flex-col gap-2.5">
          {SEVERITY_ORDER.map((s) => {
            const value = counts[s.key];
            const pct = total > 0 ? Math.round((value / total) * 100) : 0;
            return (
              <li key={s.key} className="flex items-center gap-2.5 text-[12px]">
                <span
                  aria-hidden
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ background: s.color }}
                />
                <span className="w-[52px] shrink-0 text-[var(--text-secondary)]">{s.label}</span>
                <span className="h-1 flex-1 overflow-hidden rounded-full bg-white/[0.05]">
                  <span
                    className="block h-full rounded-full"
                    style={{ width: `${pct}%`, background: s.color }}
                  />
                </span>
                <span className="w-6 shrink-0 text-right font-mono text-[var(--text-tertiary)]">
                  {value}
                </span>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
