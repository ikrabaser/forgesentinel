import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";
import type { Telemetry } from "../api/types";
import { AnimatedNumber } from "../components/AnimatedNumber";
import { StatCard } from "../components/StatCard";
import { useLiveData } from "../state/LiveDataContext";

const ASSET_CODE = "PLC-001"; // single-asset lab for now (see README)

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour12: false });
}

export function TelemetryPage() {
  const [history, setHistory] = useState<Telemetry[]>([]);
  const { telemetryByAsset, historyByAsset } = useLiveData();

  useEffect(() => {
    api.listTelemetry(ASSET_CODE, 50).then((rows) => setHistory([...rows].reverse()));
  }, []);

  const liveHistory = historyByAsset[ASSET_CODE] ?? [];
  const current = telemetryByAsset[ASSET_CODE];

  // Merge REST snapshot with anything that arrived live since, oldest
  // first (chart reads left-to-right as time), deduped by id.
  const chartData = useMemo(() => {
    const byId = new Map<number, Telemetry>();
    for (const row of [...history, ...liveHistory]) byId.set(row.id, row);
    return [...byId.values()]
      .sort((a, b) => a.id - b.id)
      .map((row) => ({ ...row, time: formatTime(row.timestamp) }));
  }, [history, liveHistory]);

  const latest = current ?? chartData.at(-1);

  return (
    <div className="flex flex-col gap-6 p-8">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard
          label="Temperature"
          value={<AnimatedNumber value={latest?.temperature ?? 0} decimals={1} suffix="°C" />}
          tone={latest && latest.temperature > 90 ? "high" : "default"}
          index={0}
        />
        <StatCard
          label="Pressure"
          value={<AnimatedNumber value={latest?.pressure ?? 0} decimals={2} suffix=" bar" />}
          tone={latest && latest.pressure > 4 ? "critical" : "default"}
          index={1}
        />
        <StatCard
          label="Tank Level"
          value={
            <AnimatedNumber value={latest?.tank_level_percent ?? 0} decimals={1} suffix="%" />
          }
          index={2}
        />
        <StatCard label="Pump" value={latest?.pump_state ?? "—"} index={3} />
      </div>

      <div className="glass-panel rounded-xl border border-[var(--border)] p-6">
        <div className="mb-4 text-sm font-semibold text-[var(--text-bright)]">
          Temperature &amp; Pressure — {ASSET_CODE}
        </div>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={chartData}>
            <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
            <XAxis dataKey="time" stroke="var(--text-dim)" fontSize={11} tickLine={false} />
            <YAxis
              yAxisId="temp"
              stroke="var(--text-dim)"
              fontSize={11}
              tickLine={false}
              width={36}
            />
            <YAxis
              yAxisId="pressure"
              orientation="right"
              stroke="var(--text-dim)"
              fontSize={11}
              tickLine={false}
              width={36}
            />
            <Tooltip
              contentStyle={{
                background: "var(--bg-panel-raised)",
                border: "1px solid var(--border-strong)",
                borderRadius: 8,
                fontSize: 12,
              }}
              labelStyle={{ color: "var(--text-dim)" }}
            />
            <Line
              yAxisId="temp"
              type="monotone"
              dataKey="temperature"
              stroke="var(--severity-high)"
              strokeWidth={2}
              dot={false}
              isAnimationActive
              animationDuration={400}
            />
            <Line
              yAxisId="pressure"
              type="monotone"
              dataKey="pressure"
              stroke="var(--accent)"
              strokeWidth={2}
              dot={false}
              isAnimationActive
              animationDuration={400}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
