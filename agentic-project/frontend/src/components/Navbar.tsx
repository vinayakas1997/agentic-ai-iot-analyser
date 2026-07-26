import { useState, useRef, useEffect } from "react";
import { btnSecondary } from "../lib/styles";
import { useSessionStore } from "../stores/sessionStore";
import { IconTrash } from "../lib/icons";

export default function Navbar() {
  const sessions = useSessionStore((s) => s.sessions);
  const sessionId = useSessionStore((s) => s.sessionId);
  const sessionMeta = useSessionStore((s) => s.sessionMeta);
  const loading = useSessionStore((s) => s.loading);
  const switchSession = useSessionStore((s) => s.switchSession);
  const newSession = useSessionStore((s) => s.newSession);
  const deleteSession = useSessionStore((s) => s.deleteSession);
  const [open, setOpen] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
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

  useEffect(() => {
    if (!open) setConfirmDeleteId(null);
  }, [open]);

  const handleConfirmDelete = async (id: string) => {
    setDeleting(true);
    try {
      await deleteSession(id);
    } catch (e) {
      console.error("Failed to delete session:", e);
    } finally {
      setDeleting(false);
      setConfirmDeleteId(null);
    }
  };

  const current = sessions.find((s) => s.session_id === sessionId);

  return (
    <header className="flex items-center justify-between px-5 py-3 border-b border-border bg-surface-1 shrink-0">
      <span className="text-lg font-semibold">EDAS</span>

      <div className="flex items-center gap-3">
        <span className="text-[11px] font-semibold tabular-nums text-muted mr-1">
          {sessions.length} session{sessions.length === 1 ? "" : "s"}
        </span>
        <div className="relative" ref={ref}>
          <button
            type="button"
            className="flex items-center gap-2 rounded-lg border border-border bg-surface-1 text-text text-sm px-3 py-1.5 min-w-[200px] text-left disabled:opacity-50"
            onClick={() => !loading && setOpen(!open)}
            disabled={loading}
            aria-label="Session"
          >
            {current ? (
              <span className="flex-1 truncate">{current.title || current.line_name || "New"}</span>
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
                <div
                  key={s.session_id}
                  className={`flex items-center gap-2 w-full px-3 py-2 text-sm transition-colors ${
                    s.session_id === sessionId ? "bg-white/[0.06]" : "hover:bg-white/[0.04]"
                  }`}
                >
                  {confirmDeleteId === s.session_id ? (
                    <>
                      <span className="flex-1 text-[12px] text-ic-amber">Delete this session?</span>
                      <button
                        type="button"
                        className="text-[11px] font-semibold text-ic-amber hover:text-text transition-colors shrink-0 disabled:opacity-50"
                        onClick={() => handleConfirmDelete(s.session_id)}
                        disabled={deleting}
                      >
                        {deleting ? "Deleting..." : "Delete"}
                      </button>
                      <button
                        type="button"
                        className="text-[11px] font-medium text-muted hover:text-text transition-colors shrink-0 disabled:opacity-50"
                        onClick={() => setConfirmDeleteId(null)}
                        disabled={deleting}
                      >
                        Cancel
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        type="button"
                        className="flex-1 text-left truncate"
                        onClick={() => {
                          switchSession(s.session_id);
                          setOpen(false);
                        }}
                      >
                        {s.title || s.line_name || "New"}
                      </button>
                      <button
                        type="button"
                        className="text-muted hover:text-ic-amber transition-colors shrink-0"
                        onClick={() => setConfirmDeleteId(s.session_id)}
                        title="Delete session"
                        aria-label="Delete session"
                      >
                        <IconTrash size={13} />
                      </button>
                    </>
                  )}
                </div>
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
