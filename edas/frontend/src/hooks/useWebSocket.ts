import { useEffect, useRef, useState } from "react";

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:7009";

export function useWebSocket(onMessage?: (data: Record<string, unknown>) => void) {
  const [connected, setConnected] = useState(false);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    const url = `${WS_URL}/ws`;
    const ws = new WebSocket(url);

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data) as Record<string, unknown>;
        onMessageRef.current?.(data);
      } catch {
        /* ignore */
      }
    };

    return () => ws.close();
  }, []);

  return { connected };
}
