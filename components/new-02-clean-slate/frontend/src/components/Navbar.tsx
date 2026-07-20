import { useState, useRef, useEffect, useMemo } from "react";
import { btnSecondary } from "../lib/styles";
import { useSessionStore } from "../stores/sessionStore";

const MODE_STYLES: Record<string, string> = {
  ask: "bg-ic-blue-soft text-ic-blue border-ic-blue/30",
  man: "bg-stage-manager-soft text-stage-manager border-stage-manager-line/40",
  plan: "bg-stage-planner-soft text-stage-planner border-stage-planner-line/40",
  exe: "bg-stage-execution-soft text-stage-execution border-stage-execution-line/40",
};

export default function Navbar() {
  const sessions = useSessionStore((s) => s.sessions);
  const sessionId = useSessionStore((s) => s.sessionId);
  const sessionMeta = useSessionStore((s) => s.sessionMeta);
  const loading = useSessionStore((s) => s.loading);
  const switchSession = useSessionStore((s) => s.switchSession);
  const newSession = useSessionStore((s) => s.newSession);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const current = sessions.find((s) => s.session_id === sessionId);

  const counts = useMemo(() => {
    const c = { ask: 0, man: 0, plan: 0, exe: 0 };
    sessions.forEach((s) => {
      const m = s.mode || "ask";
      if (m in c) c[m as keyof typeof c]++;
    });
    return c;
  }, [sessions]);

  const DOTS: { key: string; color: string }[] = [
    { key: "ask", color: "bg-ic-blue" },
    { key: "man", color: "bg-stage-manager" },
    { key: "plan", color: "bg-stage-planner" },
    { key: "exe", color: "bg-stage-execution" },
  ];

  return (
    <header className="flex items-center justify-between px-5 py-3 border-b border-border bg-surface-1 shrink-0">
      <span className="text-lg font-semibold">EDAS</span>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2.5 mr-1">
          {DOTS.map((d) => (
            <div key={d.key} className="flex items-center gap-1">
              <span className={`w-1.5 h-1.5 rounded-full ${d.color}`} />
              <span className="text-[11px] font-semibold tabular-nums text-muted min-w-[12px] text-center">
                {counts[d.key as keyof typeof counts]}
              </span>
            </div>
          ))}
        </div>
        <div className="relative" ref={ref}>
          <button
            type="button"
            className="flex items-center gap-2 rounded-lg border border-border bg-surface-1 text-text text-sm px-3 py-1.5 min-w-[200px] text-left disabled:opacity-50"
            onClick={() => !loading && setOpen(!open)}
            disabled={loading}
            aria-label="Session"
          >
            {current ? (
              <>
                <span className="flex-1 truncate">{current.title || current.line_name || "New"}</span>
                <span
                  className={`text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded border ${MODE_STYLES[current.mode || "ask"] || "bg-surface-2 text-muted border-border"}`}
                >
                  {current.mode || "ask"}
                </span>
              </>
            ) : (
              <span className="text-muted">No session</span>
            )}
          </button>
          {open && (
            <div className="absolute top-full mt-1 left-0 right-0 rounded-lg border border-border bg-surface-1 shadow-xl z-50 max-h-[300px] overflow-y-auto">
              {sessions.length === 0 && (
                <div className="px-3 py-2 text-sm text-muted">No sessions</div>
              )}
              {sessions.map((s) => (
                <button
                  key={s.session_id}
                  type="button"
                  className={`flex items-center gap-2 w-full text-left px-3 py-2 text-sm hover:bg-white/[0.04] transition-colors ${
                    s.session_id === sessionId ? "bg-white/[0.06]" : ""
                  }`}
                  onClick={() => {
                    switchSession(s.session_id);
                    setOpen(false);
                  }}
                >
                  <span className="flex-1 truncate">{s.title || s.line_name || "New"}</span>
                  <span
                    className={`text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded border shrink-0 ${MODE_STYLES[s.mode || "ask"] || "bg-surface-2 text-muted border-border"}`}
                  >
                    {s.mode || "ask"}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
        <button type="button" className={btnSecondary} onClick={newSession} disabled={loading}>
          + New
        </button>
        <span
          className={`w-2 h-2 rounded-full ${loading ? "bg-yellow-400" : "bg-success"}`}
          aria-hidden
        />
        <span className="text-xs text-muted">{loading ? "Thinking\u2026" : "Ready"}</span>
      </div>
    </header>
  );
}
