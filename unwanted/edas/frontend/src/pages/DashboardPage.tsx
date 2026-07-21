import { useCallback, useEffect, useState } from "react";
import { fetchResults } from "../api/client";
import EventFeed, { type WsEvent } from "../components/dashboard/EventFeed";
import ResultCard, { type TaskResult } from "../components/dashboard/ResultCard";
import TaskInput from "../components/dashboard/TaskInput";
import { useWebSocket } from "../hooks/useWebSocket";

const USER_ID = import.meta.env.VITE_DEFAULT_USER_ID || "98765";

export default function DashboardPage() {
  const [events, setEvents] = useState<WsEvent[]>([]);
  const [latestResult, setLatestResult] = useState<TaskResult | null>(null);

  const onWsMessage = useCallback((msg: Record<string, unknown>) => {
    const event = msg as WsEvent;
    setEvents((prev) => [event, ...prev].slice(0, 50));
    if (event.topic === "task.complete" || event.topic === "task.failed") {
      const payload = event.payload as { data?: Record<string, unknown> } | undefined;
      const data = payload?.data || {};
      setLatestResult({
        task: data.task as string | undefined,
        status:
          (data.status as string) || (event.topic === "task.failed" ? "failed" : "complete"),
        result: data,
      });
    }
  }, []);

  const { connected } = useWebSocket(onWsMessage);

  useEffect(() => {
    fetchResults().then((rows: TaskResult[]) => {
      if (rows.length > 0) setLatestResult(rows[0]);
    });
  }, []);

  return (
    <main className="flex-1 overflow-y-auto p-5 space-y-4 max-w-3xl mx-auto w-full">
      <div>
        <h1 className="text-xl font-semibold">Dashboard</h1>
        <p className="text-muted text-sm mt-1">
          User {USER_ID} · WS {connected ? "connected" : "disconnected"}
        </p>
      </div>
      <TaskInput onSubmitted={() => setEvents([])} />
      <EventFeed events={events} />
      <ResultCard result={latestResult} />
    </main>
  );
}
