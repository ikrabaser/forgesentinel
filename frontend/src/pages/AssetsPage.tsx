import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api } from "../api/client";
import type { Asset } from "../api/types";
import { StatusDot } from "../components/StatusDot";
import { useLiveData } from "../state/LiveDataContext";

function timeAgo(iso: string): string {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  return `${Math.floor(seconds / 60)}m ago`;
}

export function AssetsPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const { telemetryByAsset } = useLiveData();

  useEffect(() => {
    api.listAssets().then(setAssets);
  }, []);

  return (
    <div className="p-8">
      <div className="glass-panel overflow-hidden rounded-xl border border-[var(--border)]">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-[var(--border)] text-[11px] uppercase tracking-wider text-[var(--text-dim)]">
            <tr>
              <th className="px-5 py-3">Status</th>
              <th className="px-5 py-3">Asset</th>
              <th className="px-5 py-3">Type</th>
              <th className="px-5 py-3">Protocol</th>
              <th className="px-5 py-3">IP</th>
              <th className="px-5 py-3">Last Seen</th>
            </tr>
          </thead>
          <tbody>
            {assets.map((asset, i) => {
              // A live telemetry point arriving is itself proof of
              // life, independent of whatever `status` said at the
              // last REST fetch - reflect that immediately.
              const seenLive = Boolean(telemetryByAsset[asset.asset_code]);
              const online = asset.status === "ONLINE" || seenLive;

              return (
                <motion.tr
                  key={asset.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: i * 0.03 }}
                  className="border-b border-[var(--border)] last:border-b-0"
                >
                  <td className="px-5 py-3">
                    <StatusDot online={online} />
                  </td>
                  <td className="px-5 py-3 font-mono text-[var(--text-bright)]">
                    {asset.asset_code}
                  </td>
                  <td className="px-5 py-3 text-[var(--text-dim)]">{asset.asset_type}</td>
                  <td className="px-5 py-3 text-[var(--text-dim)]">{asset.protocol ?? "—"}</td>
                  <td className="px-5 py-3 font-mono text-[var(--text-dim)]">
                    {asset.ip_address ?? "—"}
                  </td>
                  <td className="px-5 py-3 text-[var(--text-dim)]">{timeAgo(asset.last_seen)}</td>
                </motion.tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
