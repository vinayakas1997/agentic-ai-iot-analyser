import { useEffect, useRef } from "react";
import { useSessionStore } from "../stores/sessionStore";

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:7009";
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;

export function useWorkspaceSocket() {
  const sessionId = useSessionStore((s) => s.sessionId);
  const pushEvent = useSessionStore((s) => s.pushExecutionEvent);
  const setWsStatus = useSessionStore((s) => s.setWsStatus);
  const updatePendingSchema = useSessionStore((s) => s.updatePendingSchema);
  const updatePendingUi = useSessionStore((s) => s.updatePendingUi);
  const wsRef = useRef<WebSocket | null>(null);
  const retryCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const everConnectedRef = useRef(false);

  const connect = () => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    setWsStatus("connecting");
    const url = `${WS_URL}/ws`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      everConnectedRef.current = true;
      setWsStatus("connected");
      retryCountRef.current = 0;
    };

    ws.onclose = () => {
      if (everConnectedRef.current) {
        setWsStatus("disconnected");
      }
      wsRef.current = null;
      scheduleReconnect();
    };

    ws.onerror = () => {
      if (everConnectedRef.current) {
        setWsStatus("disconnected");
      }
      wsRef.current = null;
      scheduleReconnect();
    };

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data) as Record<string, unknown>;
        const topic = (data.topic || "") as string;
        const eventSessionId = (data.session_id || "") as string;
        const payload = data.payload as Record<string, unknown>;

        if (eventSessionId && eventSessionId !== sessionId) return;

        // Handle real-time resolution updates for pending turn
        if (topic === "manager.line_resolved") {
          updatePendingSchema({
            line: payload.line as string,
            line_match: { mention: payload.mention as string, canonical: payload.line as string, source: payload.source as string },
          });
          return;
        }

        if (topic === "manager.time_resolved") {
          updatePendingSchema({
            time: {
              start: payload.start as string,
              end: payload.end as string,
            },
          });
          return;
        }

        if (topic === "manager.context_synced") {
          updatePendingSchema({
            datasets_in_scope: payload.datasets as string[],
            suggested_aims: payload.suggested_aims as string[],
          });
          return;
        }

        if (topic === "manager.plan_built") {
          updatePendingUi({
            plan: { aims: payload.aims as string[] },
          });
          return;
        }

        const relevantTopics = [
          "planner.start",
          "planner.result",
          "planner.retry",
          "executor.run",
          "task.complete",
          "task.failed",
          "manager.result",
        ];
        if (!relevantTopics.includes(topic)) return;

        pushEvent({
          topic,
          payload: data.payload as Record<string, unknown>,
          timestamp: Date.now(),
        });
      } catch {
        // ignore malformed messages
      }
    };
  };

  const scheduleReconnect = () => {
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
  };

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
  }, [sessionId, pushEvent, setWsStatus]);
}
