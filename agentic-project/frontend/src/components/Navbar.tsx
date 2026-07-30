import { useState, useRef, useEffect } from "react";
import { btnSecondary } from "../lib/styles";
import { useSessionStore } from "../stores/sessionStore";
import { useUiStore } from "../stores/uiStore";
import { useAuthStore } from "../stores/authStore";
import { useT, tCount } from "../lib/i18n";
import { IconTrash, IconHelpAnimated } from "../lib/icons";

export default function Navbar({ onBackToManage, onHelp }: { onBackToManage?: () => void; onHelp?: () => void }) {
  const sessions = useSessionStore((s) => s.sessions);
  const sessionId = useSessionStore((s) => s.sessionId);
  const sessionMeta = useSessionStore((s) => s.sessionMeta);
  const loading = useSessionStore((s) => s.loading);
  const error = useSessionStore((s) => s.error);
  const switchSession = useSessionStore((s) => s.switchSession);
  const newSession = useSessionStore((s) => s.newSession);
  const deleteSession = useSessionStore((s) => s.deleteSession);
  const language = useUiStore((s) => s.language);
  const setLanguage = useUiStore((s) => s.setLanguage);
  const logout = useAuthStore((s) => s.logout);
  const t = useT();
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
    <header className="flex items-center justify-between px-5 py-3 border-b border-border bg-surface-1 shrink-0 relative">
      <div className="flex items-center gap-2">
        <span className="text-lg font-semibold">{t("brand.name")}</span>
        <div className="hlp-label-wrap">
          <button
            type="button"
            onClick={onHelp}
            className="w-[34px] h-[34px] rounded-lg flex items-center justify-center hover:bg-white/[0.06] transition-colors"
            title={t("tour.help")}
          >
            <IconHelpAnimated size={34} />
          </button>
          <span className="hlp-label" aria-hidden>
            {t("tour.help")}
          </span>
        </div>
      </div>

      <div className="absolute left-1/2 -translate-x-1/2 text-sm font-bold text-muted">
        {t("brand.note")} {t("nav.noDatasetsInfo")}
      </div>

      {error && (
        <div className="absolute left-1/2 -translate-x-1/2 top-full mt-1 text-xs text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-1.5 max-w-md truncate">
          {error}
        </div>
      )}

      <div className="flex items-center gap-3">
        <span className="text-[11px] font-semibold tabular-nums text-muted mr-1">
          {tCount(t, "nav.sessionCount", sessions.length)}
        </span>
        <div className="flex rounded-full border border-border bg-surface-1 overflow-hidden">
          <button
            type="button"
            className={`text-[11px] font-semibold px-2.5 py-1 transition-colors ${
              language === "en"
                ? "bg-ic-amber text-black"
                : "text-text hover:bg-white/[0.06]"
            }`}
            onClick={() => setLanguage("en")}
          >
            EN
          </button>
          <div className="w-px bg-border self-stretch" />
          <button
            type="button"
            className={`text-[11px] font-semibold px-2.5 py-1 transition-colors ${
              language === "ja"
                ? "bg-ic-amber text-black"
                : "text-text hover:bg-white/[0.06]"
            }`}
            onClick={() => setLanguage("ja")}
          >
            日本語
          </button>
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
              <span className="flex-1 truncate">{current.title || current.line_name || "New"}</span>
            ) : (
              <span className="text-muted">{t("nav.noSession")}</span>
            )}
          </button>
          {open && (
            <div className="absolute top-full mt-1 left-0 right-0 rounded-lg border border-border bg-surface-1 shadow-xl z-50 max-h-[300px] overflow-y-auto">
              {sessions.length === 0 && (
                <div className="px-3 py-2 text-sm text-muted">{t("nav.noSessions")}</div>
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
                      <span className="flex-1 text-[12px] text-ic-amber">{t("nav.deleteConfirm")}</span>
                      <button
                        type="button"
                        className="text-[11px] font-semibold text-ic-amber hover:text-text transition-colors shrink-0 disabled:opacity-50"
                        onClick={() => handleConfirmDelete(s.session_id)}
                        disabled={deleting}
                      >
                        {deleting ? t("nav.deleting") : t("nav.delete")}
                      </button>
                      <button
                        type="button"
                        className="text-[11px] font-medium text-muted hover:text-text transition-colors shrink-0 disabled:opacity-50"
                        onClick={() => setConfirmDeleteId(null)}
                        disabled={deleting}
                      >
                        {t("common.cancel")}
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
                        title={t("nav.deleteSessionTitle")}
                        aria-label={t("nav.deleteSessionTitle")}
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
          {t("nav.new")}
        </button>
        {onBackToManage && (
          <button type="button" className={btnSecondary} onClick={onBackToManage}>
            {t("registryAdmin.backToManage")}
          </button>
        )}
        <button type="button" className={btnSecondary} onClick={logout}>
          {t("registryAdmin.logout")}
        </button>
        <span
          className={`w-2 h-2 rounded-full ${loading ? "bg-yellow-400" : "bg-success"}`}
          aria-hidden
        />
        <span className="text-xs text-muted">{loading ? t("common.thinking") : t("nav.ready")}</span>
      </div>
    </header>
  );
}
