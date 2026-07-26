import { useState } from "react";
import { useAuthStore } from "../stores/authStore";
import { login } from "../api/client";
import { useT } from "../lib/i18n";
import { btnPrimary } from "../lib/styles";

export default function LoginPage() {
  const t = useT();
  const doLogin = useAuthStore((s) => s.login);
  const [userId, setUserId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

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
    <div className="flex items-center justify-center h-screen bg-bg-deep text-text">
      <div className="rounded-2xl border-2 border-border bg-surface-1 p-8 w-full max-w-sm">
        <div className="text-lg font-semibold mb-1">EDAS</div>
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
