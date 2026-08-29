// LiveDataContext: the single WebSocket connection for the whole app,
// fanned out to any component that needs it via useLiveData(). Having
// exactly one socket (not one per page/component) matches how the
// backend's ConnectionManager expects to be used - it broadcasts once
// per connected client, so the fewer redundant connections, the
// fewer duplicate messages to reconcile.

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useLiveSocket, type ConnectionState } from "../hooks/useLiveSocket";
import type { Alert, LiveMessage, Telemetry } from "../api/types";

const MAX_HISTORY_POINTS = 60;
const MAX_ALERTS_KEPT = 200;

interface LiveDataValue {
  connectionState: ConnectionState;
  telemetryByAsset: Record<string, Telemetry>;
  historyByAsset: Record<string, Telemetry[]>;
  liveAlerts: Alert[];
}

const LiveDataContext = createContext<LiveDataValue | null>(null);

export function LiveDataProvider({ children }: { children: ReactNode }) {
  const [telemetryByAsset, setTelemetryByAsset] = useState<Record<string, Telemetry>>({});
  const [historyByAsset, setHistoryByAsset] = useState<Record<string, Telemetry[]>>({});
  const [liveAlerts, setLiveAlerts] = useState<Alert[]>([]);

  const handleMessage = useCallback((message: LiveMessage) => {
    if (message.type === "telemetry") {
      const { asset_code, ...rest } = message;
      // asset_id isn't in the broadcast payload (see api/types.ts) -
      // nothing in the UI keys telemetry by numeric id, only by
      // asset_code, so 0 is a harmless placeholder here.
      const record: Telemetry = { ...rest, asset_id: 0 };

      setTelemetryByAsset((prev) => ({ ...prev, [asset_code]: record }));
      setHistoryByAsset((prev) => {
        const existing = prev[asset_code] ?? [];
        const next = [...existing, record].slice(-MAX_HISTORY_POINTS);
        return { ...prev, [asset_code]: next };
      });
    } else if (message.type === "alert") {
      const { type: _type, ...alert } = message;
      setLiveAlerts((prev) => [alert, ...prev].slice(0, MAX_ALERTS_KEPT));
    }
  }, []);

  const connectionState = useLiveSocket(handleMessage);

  const value = useMemo(
    () => ({ connectionState, telemetryByAsset, historyByAsset, liveAlerts }),
    [connectionState, telemetryByAsset, historyByAsset, liveAlerts],
  );

  return <LiveDataContext.Provider value={value}>{children}</LiveDataContext.Provider>;
}

export function useLiveData(): LiveDataValue {
  const ctx = useContext(LiveDataContext);
  if (!ctx) throw new Error("useLiveData must be used within a LiveDataProvider");
  return ctx;
}
