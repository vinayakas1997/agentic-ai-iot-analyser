import { useMemo } from "react";
import { cardClass } from "../lib/styles";
import {
  useSessionStore,
  useIsDone,
  useSelectedTurn,
} from "../stores/sessionStore";
import { useUiStore } from "../stores/uiStore";
import {
  waitingCardClass, waitingMetaClass, lockedRowClass,
  resultCardClass, resultTagClass, resultBadgeClass,
} from "../lib/styles";
import { IconLock, IconCheckCircle, IconGrid } from "../lib/icons";

const outputPanelClass =
  "flex flex-col min-h-0 h-full overflow-hidden border-r border-border p-4";

/* ── Waiting on Planner ── */
function WaitingOnPlanner() {
  return (
    <div className={waitingCardClass}>
      <div className="w-11 h-11 rounded-xl bg-stage-planner-soft text-stage-planner flex items-center justify-center mx-auto mb-3.5">
        <IconCheckCircle size={22} />
      </div>
      <h3 className="font-display text-[14.5px] font-semibold text-text mb-1.5">
        Waiting on Planner
      </h3>
      <p className="text-[12.5px] text-muted leading-relaxed max-w-[280px] mx-auto mb-4">
        Manager has scoped the aim. Once Planner builds a query plan, it'll
        appear here — followed by Execution's results.
      </p>
      <div className={waitingMetaClass}>
        <span className="w-1.5 h-1.5 rounded-full bg-stage-planner animate-[pulse_1.6s_ease-in-out_infinite]" />
        Planner not yet started
      </div>
      <div className={lockedRowClass}>
        <IconLock size={14} />
        <span>Execution results will appear once Planner completes</span>
      </div>
    </div>
  );
}

/* ── Execution progress & results ── */
function ExecutionProgress({ isDone }: { isDone: boolean }) {
  const executionEvents = useSessionStore((s) => s.executionEvents);
  const lastEvent = useMemo(() => {
    if (!executionEvents.length) return null;
    return executionEvents[executionEvents.length - 1];
  }, [executionEvents]);

  const plannerStarted = executionEvents.some((e) => e.topic === "planner.start");

  // Waiting on Planner
  if (isDone && !plannerStarted) {
    return <WaitingOnPlanner />;
  }

  if (!executionEvents.length) return null;

  const statusFromEvent = (topic: string) => {
    switch (topic) {
      case "planner.start":
        return { label: "Planning queries\u2026", color: "text-stage-planner" };
      case "executor.run":
        return { label: "Running query\u2026", color: "text-stage-execution" };
      case "planner.result":
        return { label: "Planner complete", color: "text-stage-planner" };
      case "planner.retry":
        return { label: "Retrying query\u2026", color: "text-stage-planner" };
      case "task.complete":
        return { label: "Task complete", color: "text-stage-execution" };
      case "task.failed":
        return { label: "Task failed", color: "text-red-400" };
      default:
        return { label: topic, color: "text-muted" };
    }
  };

  const status = statusFromEvent(lastEvent?.topic || "");

  // Complete → show structured results
  if (lastEvent?.topic === "task.complete") {
    const payload = lastEvent.payload as Record<string, unknown>;
    const data = payload?.data as Record<string, unknown> | undefined;
    const results = data?.results as Record<string, unknown>[] | undefined;

    return (
      <>
        {results && results.length > 0 ? (
          results.map((r, i) => (
            <div key={i} className={resultCardClass}>
              <div className={resultTagClass}>
                <span className={resultBadgeClass}>
                  <IconGrid size={12} />
                </span>
                Execution &middot; {r.title ? String(r.title) : `Query ${i + 1}`}
              </div>
              <pre className="bg-black/30 p-2.5 rounded-lg overflow-x-auto whitespace-pre-wrap text-[12px] text-muted leading-relaxed">
                {JSON.stringify(r, null, 2)}
              </pre>
            </div>
          ))
        ) : (
          <div className={resultCardClass}>
            <div className={resultTagClass}>
              <span className={resultBadgeClass}>
                <IconCheckCircle size={12} />
              </span>
              Execution &middot; Complete
            </div>
            <p className="text-sm text-stage-execution">{status.label}</p>
          </div>
        )}
      </>
    );
  }

  // Running / intermediate state
  return (
    <div className={cardClass}>
      <div className="flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-stage-planner animate-pulse" />
        <p className={`text-sm ${status.color}`}>{status.label}</p>
      </div>
    </div>
  );
}

export default function OutputSection() {
  const turns = useSessionStore((s) => s.turns);
  const selectedTurnIndex = useUiStore((s) => s.selectedTurnIndex);
  const turn = useSelectedTurn();
  const isDone = useIsDone();
  const ui = turn?.ui;

  return (
    <section className={`${outputPanelClass} order-3 lg:order-none border-r-0`}>
      <div className="flex items-center justify-between mb-3 shrink-0">
        <h2 className="text-base font-semibold font-display">Outputs</h2>
        <p className="text-xs text-muted">
          Step {turns.length > 0 ? selectedTurnIndex + 1 : 0} of {turns.length}
        </p>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0">
        {!turn ? (
          <p className="text-muted text-sm">Send a message to start planning.</p>
        ) : !ui ? (
          <p className="text-muted text-sm">No snapshot for this step.</p>
        ) : (
          <ExecutionProgress isDone={isDone} />
        )}
      </div>
    </section>
  );
}
