import StatusBadge from "./StatusBadge";

export interface WsEvent {
  event_id?: string;
  topic?: string;
  session_id?: string;
  payload?: Record<string, unknown>;
}

export default function EventFeed({ events }: { events: WsEvent[] }) {
  return (
    <div className="rounded-xl border border-border bg-panel p-4">
      <h2 className="text-base font-semibold mb-3">Live activity</h2>
      {events.length === 0 && <p className="text-muted text-sm">Waiting for events…</p>}
      {events.map((ev, i) => (
        <div key={`${ev.event_id}-${i}`} className="flex items-center gap-2 py-1.5 text-sm">
          <StatusBadge status={ev.topic} />
          <span className="text-muted">{ev.session_id?.slice(0, 8)}</span>
        </div>
      ))}
    </div>
  );
}
