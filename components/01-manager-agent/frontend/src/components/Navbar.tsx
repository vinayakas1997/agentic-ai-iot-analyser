import { btnSecondary } from "../lib/styles";
import { useSessionStore } from "../stores/sessionStore";
import { useUiStore } from "../stores/uiStore";

export default function Navbar() {
  const sessions = useSessionStore((s) => s.sessions);
  const sessionId = useSessionStore((s) => s.sessionId);
  const loading = useSessionStore((s) => s.loading);
  const switchSession = useSessionStore((s) => s.switchSession);
  const newSession = useSessionStore((s) => s.newSession);
  const view = useUiStore((s) => s.view);
  const setView = useUiStore((s) => s.setView);

  return (
    <header className="flex items-center justify-between px-5 py-3 border-b border-border bg-panel shrink-0">
      <button
        type="button"
        className="text-lg font-semibold hover:text-accent transition-colors"
        onClick={() => setView("workspace")}
      >
        EDAS
      </button>

      <div className="absolute left-1/2 -translate-x-1/2">
        <button
          type="button"
          className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            view === "dashboard"
              ? "bg-accent text-white"
              : "bg-[#2f3336] text-text hover:bg-[#3f4346]"
          }`}
          onClick={() => setView("dashboard")}
        >
          Dashboard
        </button>
      </div>

      <div className="flex items-center gap-3">
        <select
          className="rounded-lg border border-border bg-app text-text text-sm px-2 py-1.5 min-w-[200px]"
          value={sessionId || ""}
          onChange={(e) => switchSession(e.target.value)}
          disabled={loading}
          aria-label="Session"
        >
          {!sessionId && <option value="">No session</option>}
          {sessions.map((s) => (
            <option key={s.session_id} value={s.session_id}>
              {s.line_name || "New"} · {s.phase} · {s.session_id.slice(0, 8)}
            </option>
          ))}
        </select>
        <button type="button" className={btnSecondary} onClick={newSession} disabled={loading}>
          + New
        </button>
        <span
          className={`w-2 h-2 rounded-full ${loading ? "bg-yellow-400" : "bg-success"}`}
          aria-hidden
        />
        <span className="text-xs text-muted">{loading ? "Thinking…" : "Ready"}</span>
      </div>
    </header>
  );
}
