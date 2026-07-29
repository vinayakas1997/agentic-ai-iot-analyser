import { useEffect, useState } from "react";
import { useAuthStore } from "../stores/authStore";
import { login } from "../api/client";
import { useT } from "../lib/i18n";
import { btnPrimary } from "../lib/styles";

export default function LoginPage({ onClose }: { onClose?: () => void }) {
  const t = useT();
  const doLogin = useAuthStore((s) => s.login);
  const [userId, setUserId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!onClose) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const handleSubmit = async () => {
    if (!userId.trim()) return;
    setSubmitting(true);
    setError("");
    try {
      const res = await login(userId.trim());
      doLogin(res.user_id, res.role);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("login.error"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-bg-deep/40 backdrop-blur-sm text-text"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose?.();
      }}
    >
      <div className="rounded-2xl border-2 border-border bg-surface-1 p-8 w-full max-w-sm shadow-2xl">
        <div className="text-lg font-semibold mb-1">Agentic IoT Data Analyser</div>
        <div className="text-base font-semibold text-text mb-1">{t("login.title")}</div>
        <div className="text-sm text-muted mb-4">{t("login.subtitle")}</div>
        <input
          type="text"
          className="w-full rounded-xl border-2 border-border bg-app text-text text-sm px-3 py-2.5 mb-3 focus:outline-none focus:border-accent transition-colors"
          placeholder={t("login.placeholder")}
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSubmit();
          }}
          autoFocus
        />
        {error && <div className="text-[12px] text-ic-amber mb-3">{error}</div>}
        <button
          type="button"
          className={`${btnPrimary} w-full`}
          onClick={handleSubmit}
          disabled={submitting || !userId.trim()}
        >
          {submitting ? "..." : t("login.submit")}
        </button>
      </div>
    </div>
  );
}
