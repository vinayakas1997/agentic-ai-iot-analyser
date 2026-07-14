import { useCallback, useEffect, useRef } from "react";
import { useSessionStore } from "../stores/sessionStore";

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:7009";
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;

export function useWorkspaceSocket() {
  const setWsStatus = useSessionStore((s) => s.setWsStatus);

  const wsRef = useRef<WebSocket | null>(null);
  const retryCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const everConnectedRef = useRef(false);
  const wsIdRef = useRef(0);

  const callbacksRef = useRef({
    sessionId: useSessionStore.getState().sessionId,
    pushEvent: useSessionStore.getState().pushExecutionEvent,
    updatePendingSchema: useSessionStore.getState().updatePendingSchema,
    updatePendingUi: useSessionStore.getState().updatePendingUi,
  });

  useEffect(() => {
    const unsub = useSessionStore.subscribe((s) => {
      callbacksRef.current.sessionId = s.sessionId;
      callbacksRef.current.pushEvent = s.pushExecutionEvent;
      callbacksRef.current.updatePendingSchema = s.updatePendingSchema;
      callbacksRef.current.updatePendingUi = s.updatePendingUi;
    });
    return unsub;
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
      connectRef.current();
    }, delay);
  }, []);

  const connect = useCallback(() => {
    const cbs = callbacksRef.current;

    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    const currentId = ++wsIdRef.current;

    setWsStatus("connecting");
    const url = `${WS_URL}/ws`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (currentId !== wsIdRef.current) return;
      everConnectedRef.current = true;
      setWsStatus("connected");
      retryCountRef.current = 0;
    };

    ws.onclose = () => {
      if (currentId !== wsIdRef.current) return;
      if (everConnectedRef.current) {
        setWsStatus("disconnected");
      }
      wsRef.current = null;
      scheduleReconnect();
    };

    ws.onerror = () => {
      if (currentId !== wsIdRef.current) return;
      if (everConnectedRef.current) {
        setWsStatus("disconnected");
      }
      wsRef.current = null;
      scheduleReconnect();
    };

    ws.onmessage = (evt) => {
      if (currentId !== wsIdRef.current) return;
      try {
        const data = JSON.parse(evt.data) as Record<string, unknown>;
        const topic = (data.topic || "") as string;
        const eventSessionId = (data.session_id || "") as string;
        const payload = data.payload as Record<string, unknown>;

        if (eventSessionId && eventSessionId !== cbs.sessionId) return;

        if (topic === "manager.line_resolved") {
          cbs.updatePendingSchema({
            line: payload.line as string,
            line_match: { mention: payload.mention as string, canonical: payload.line as string, source: payload.source as string },
          });
          return;
        }

        if (topic === "manager.time_resolved") {
          cbs.updatePendingSchema({
            time: {
              start: payload.start as string,
              end: payload.end as string,
            },
          });
          return;
        }

        if (topic === "manager.context_synced") {
          cbs.updatePendingSchema({
            datasets_in_scope: payload.datasets as string[],
            suggested_aims: payload.suggested_aims as string[],
          });
          return;
        }

        if (topic === "manager.plan_built") {
          cbs.updatePendingUi({
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

        cbs.pushEvent({
          topic,
          payload: data.payload as Record<string, unknown>,
          timestamp: Date.now(),
        });
      } catch {
        // ignore malformed messages
      }
    };
  }, [setWsStatus, scheduleReconnect]);

  const connectRef = useRef(connect);
  connectRef.current = connect;

  useEffect(() => {
    connect();
    return () => {
      wsIdRef.current++;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);
}
