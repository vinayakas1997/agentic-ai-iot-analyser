import ContextSection from "../sections/ContextSection";
import ChatSection from "../sections/ChatSection";
import OutputSection from "../sections/OutputSection";
import { useSessionStore } from "../stores/sessionStore";
import { btnSecondary } from "../lib/styles";

export default function WorkspacePage() {
  const error = useSessionStore((s) => s.error);
  const setError = useSessionStore((s) => s.setError);

  return (
    <>
      {error && (
        <div
          className="flex items-center justify-between gap-3 px-5 py-2 bg-red-950/50 text-red-400 text-sm shrink-0"
          role="alert"
        >
          <span>{error}</span>
          <button type="button" className={btnSecondary} onClick={() => setError(null)}>
            Dismiss
          </button>
        </div>
      )}
      <main className="grid flex-1 min-h-0 grid-cols-1 lg:grid-cols-[minmax(240px,25fr)_minmax(320px,40fr)_minmax(280px,35fr)]">
        <ContextSection />
        <ChatSection />
        <OutputSection />
      </main>
    </>
  );
}
