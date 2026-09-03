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
import type { Asset, Telemetry } from "../api/types";
import { AnimatedNumber } from "../components/AnimatedNumber";
import { StatCard } from "../components/StatCard";
import { StatCardSkeleton } from "../components/StatCardSkeleton";
import { useLiveData } from "../state/LiveDataContext";
import { formatClockTime } from "../lib/time";

const FALLBACK_ASSET_CODE = "PLC-001"; // used only until the real asset list loads

export function TelemetryPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [selectedAssetCode, setSelectedAssetCode] = useState<string>(FALLBACK_ASSET_CODE);
  const [history, setHistory] = useState<Telemetry[]>([]);
  const [loading, setLoading] = useState(true);
  const { telemetryByAsset, historyByAsset } = useLiveData();

  // Milestone 16 (multi-asset): fetch the asset list once, then let
  // the user switch which one's telemetry this page shows. Defaults
  // to whichever asset comes back first - not hard-coded to PLC-001 -
  // so a lab with a different first asset still opens on something
  // real instead of an empty chart.
  useEffect(() => {
    api.listAssets().then((list) => {
      setAssets(list);
      if (list.length > 0) {
        setSelectedAssetCode((current) =>
          list.some((a) => a.asset_code === current) ? current : list[0].asset_code,
        );
      }
    });
  }, []);

  useEffect(() => {
    setLoading(true);
    api
      .listTelemetry(selectedAssetCode, 50)
      .then((rows) => setHistory([...rows].reverse()))
      .finally(() => setLoading(false));
  }, [selectedAssetCode]);

  const liveHistory = historyByAsset[selectedAssetCode] ?? [];
  const current = telemetryByAsset[selectedAssetCode];

  // Merge REST snapshot with anything that arrived live since, oldest
  // first (chart reads left-to-right as time), deduped by id.
  const chartData = useMemo(() => {
    const byId = new Map<number, Telemetry>();
    for (const row of [...history, ...liveHistory]) byId.set(row.id, row);
    return [...byId.values()]
      .sort((a, b) => a.id - b.id)
      .map((row) => ({ ...row, time: formatClockTime(row.timestamp) }));
  }, [history, liveHistory]);

  const latest = current ?? chartData.at(-1);

  const assetPicker = assets.length > 1 && (
    <div className="flex flex-wrap items-center gap-2">
      {assets.map((asset) => (
        <button
          key={asset.asset_code}
          type="button"
          onClick={() => setSelectedAssetCode(asset.asset_code)}
          className={`rounded px-3 py-1.5 font-mono text-xs transition-colors duration-200 ${
            asset.asset_code === selectedAssetCode
              ? "bg-[var(--accent-dim)] text-[var(--accent)]"
              : "text-[var(--text-tertiary)] hover:bg-white/[0.035]"
          }`}
        >
          {asset.asset_code}
        </button>
      ))}
    </div>
  );

  if (loading) {
    return (
      <div className="flex flex-col gap-6 p-8">
        {assetPicker}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <StatCardSkeleton key={i} />
          ))}
        </div>
        <div className="glass-panel h-[344px] rounded-xl border border-[var(--border)]" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 p-8">
      {assetPicker}
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
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm font-semibold text-[var(--text-bright)]">
            Temperature &amp; Pressure — {selectedAssetCode}
          </div>
          <div className="flex items-center gap-4 text-[11px] text-[var(--text-tertiary)]">
            <ChartLegendEntry color="var(--severity-high)" label="Temperature (°C)" />
            <ChartLegendEntry color="var(--accent)" label="Pressure (bar)" />
          </div>
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

function ChartLegendEntry({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span aria-hidden className="h-[2px] w-3.5 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}
