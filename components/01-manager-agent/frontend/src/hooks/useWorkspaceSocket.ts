import { useEffect, useRef } from "react";
import { useSessionStore } from "../stores/sessionStore";

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:7009";

export function useWorkspaceSocket() {
  const sessionId = useSessionStore((s) => s.sessionId);
  const pushEvent = useSessionStore((s) => s.pushExecutionEvent);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const url = `${WS_URL}/ws`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data) as Record<string, unknown>;
        const topic = (data.topic || "") as string;
        const eventSessionId = (data.session_id || "") as string;

        if (eventSessionId && eventSessionId !== sessionId) return;

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

    ws.onerror = () => {};
    ws.onclose = () => {};

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [sessionId, pushEvent]);
}
