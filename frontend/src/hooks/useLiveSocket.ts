// useLiveSocket: connects to WS /ws/live (Milestone 8) and calls
// onMessage for every parsed message. Handles reconnection with a
// fixed backoff - a dashboard that just stops updating silently after
// one dropped connection would be a worse failure mode than a brief
// "Reconnecting..." indicator, especially for a security tool.

import { useEffect, useRef, useState } from "react";
import type { LiveMessage } from "../api/types";

export type ConnectionState = "connecting" | "connected" | "disconnected";

const RECONNECT_DELAY_MS = 2000;

export function useLiveSocket(onMessage: (message: LiveMessage) => void) {
  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    let socket: WebSocket | null = null;
    let reconnectTimer: number | undefined;
    let cancelled = false;

    function connect() {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      socket = new WebSocket(`${protocol}//${window.location.host}/ws/live`);

      socket.onopen = () => setConnectionState("connected");
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as LiveMessage;
          onMessageRef.current(message);
        } catch {
          // Malformed message - ignore rather than crash the socket handler.
        }
      };
      socket.onclose = () => {
        if (cancelled) return;
        setConnectionState("disconnected");
        reconnectTimer = window.setTimeout(connect, RECONNECT_DELAY_MS);
      };
      socket.onerror = () => socket?.close();
    }

    connect();

    return () => {
      cancelled = true;
      window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, []);

  return connectionState;
}
