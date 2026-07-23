import { useToastStore } from "../stores/toastStore";
import { useSessionStore } from "../stores/sessionStore";
import { IconUser } from "../lib/icons";

export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);
  const dismissToast = useToastStore((s) => s.dismissToast);
  const switchSession = useSessionStore((s) => s.switchSession);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 max-w-sm">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className="flex items-start gap-3 bg-surface-2 border-2 border-stage-manager-line/40 rounded-xl p-3 shadow-lg cursor-pointer hover:bg-surface-1 transition-colors animate-in slide-in-from-right"
          onClick={() => {
            dismissToast(toast.id);
            switchSession(toast.sessionId);
          }}
        >
          <span className="inline-flex items-center justify-center w-7 h-7 rounded-lg bg-stage-manager-soft text-stage-manager shrink-0 mt-0.5">
            <IconUser size={12} />
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-[13px] font-medium text-text leading-snug">{toast.message}</p>
            <p className="text-[11px] text-muted mt-0.5 truncate">{toast.sessionTitle}</p>
          </div>
          <button
            type="button"
            className="shrink-0 w-5 h-5 flex items-center justify-center rounded-full text-muted hover:text-text hover:bg-white/10 transition-colors"
            onClick={(e) => {
              e.stopPropagation();
              dismissToast(toast.id);
            }}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
