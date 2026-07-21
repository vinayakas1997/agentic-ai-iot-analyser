import { useCallback, useEffect, useRef, useState } from "react";

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:7009";
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;

export type ConnectionStatus = "connecting" | "connected" | "disconnected";

export function useWebSocket(onMessage?: (data: Record<string, unknown>) => void) {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("connecting");
  const onMessageRef = useRef(onMessage);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryCountRef = useRef(0);

  onMessageRef.current = onMessage;

  const connect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    setConnectionStatus("connecting");
    const url = `${WS_URL}/ws`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnectionStatus("connected");
      retryCountRef.current = 0;
    };

    ws.onclose = () => {
      setConnectionStatus("disconnected");
      wsRef.current = null;
      scheduleReconnect();
    };

    ws.onerror = () => {
      setConnectionStatus("disconnected");
      wsRef.current = null;
      scheduleReconnect();
    };

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data) as Record<string, unknown>;
        onMessageRef.current?.(data);
      } catch {
        /* ignore */
      }
    };
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (reconnectTimerRef.current) return;
    const delay = Math.min(
      RECONNECT_BASE_MS * Math.pow(2, retryCountRef.current),
      RECONNECT_MAX_MS
    );
    retryCountRef.current += 1;
    reconnectTimerRef.current = setTimeout(() => {
      reconnectTimerRef.current = null;
      connect();
    }, delay);
  }, [connect]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return { connectionStatus };
}
