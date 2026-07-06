import type { TurnUi } from "../types/manager";
import { btnSecondary, cardClass, panelClass, sectionHeaderClass } from "../lib/styles";
import {
  useSessionStore,
  useIsDone,
  useIsLive,
  useSelectedTurn,
} from "../stores/sessionStore";
import { useUiStore } from "../stores/uiStore";

function PhaseBadge({ phase, isLive }: { phase?: string; isLive: boolean }) {
  return (
    <span
      className={`text-xs px-2 py-0.5 rounded-full ${
        isLive ? "bg-green-950 text-success" : "bg-yellow-950 text-yellow-400"
      }`}
    >
      {isLive ? "Live" : "Historical"} · {phase || "extract"}
    </span>
  );
}

function ActionButtons({
  ui,
  isLive,
  isDone,
  onSendMessage,
  loading,
}: {
  ui: TurnUi;
  isLive: boolean;
  isDone: boolean;
  onSendMessage: (msg: string) => void;
  loading: boolean;
}) {
  if (!isLive || isDone) return null;

  const buttons: { label: string; message: string }[] = [];

  if (ui.proposals?.length) {
    ui.proposals.forEach((_, i) => {
      buttons.push({ label: `Confirm ${i + 1}`, message: `confirm ${i + 1}` });
    });
  }

  if (ui.plan && !ui.done) {
    buttons.push({ label: "Go", message: "go" });
  }

  if (ui.scope_pending) {
    buttons.push({ label: "1 — All machines", message: "1" });
  }

  if (!ui.proposals?.length && !ui.plan) {
    buttons.push({ label: "Show suggested aims", message: "show suggested aims" });
    buttons.push({ label: "More options", message: "more options" });
  }

  if (ui.saved_plans?.length) {
    buttons.push({ label: "List saved plans", message: "list saved plans" });
    ui.saved_plans.forEach((p) => {
      const label = p.label || p.id;
      if (label) buttons.push({ label: `Activate ${label}`, message: `activate ${label}` });
    });
  }

  if (!buttons.length) return null;

  return (
    <div className={cardClass}>
      <h3 className={sectionHeaderClass}>Actions</h3>
      <div className="flex flex-wrap gap-2">
        {buttons.map((b) => (
          <button
            key={b.label}
            type="button"
            className={btnSecondary}
            disabled={loading}
            onClick={() => onSendMessage(b.message)}
          >
            {b.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function OutputSection() {
  const turns = useSessionStore((s) => s.turns);
  const loading = useSessionStore((s) => s.loading);
  const sendUserMessage = useSessionStore((s) => s.sendUserMessage);
  const selectedTurnIndex = useUiStore((s) => s.selectedTurnIndex);
  const turn = useSelectedTurn();
  const isLive = useIsLive();
  const isDone = useIsDone();
  const ui = turn?.ui;

  return (
    <section className={`${panelClass} order-3 lg:order-none border-r-0 overflow-y-auto`}>
      <div className="flex items-center justify-between mb-2 shrink-0">
        <h2 className="text-base font-semibold">Outputs</h2>
        {ui && <PhaseBadge phase={ui.phase} isLive={isLive} />}
      </div>

      {!turn ? (
        <p className="text-muted text-sm">Send a message to start planning.</p>
      ) : !ui ? (
        <p className="text-muted text-sm">No snapshot for this step.</p>
      ) : (
        <>
          <p className="text-xs text-muted mb-3">
            Step {selectedTurnIndex + 1} of {turns.length}
          </p>

          {ui.missing && ui.missing.length > 0 && (
            <div className={cardClass}>
              <h3 className={sectionHeaderClass}>Still needed</h3>
              <ul className="list-disc pl-4 text-sm">
                {ui.missing.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            </div>
          )}

          {ui.suggested_aims &&
            ui.suggested_aims.length > 0 &&
            !ui.proposals?.length &&
            !ui.plan && (
              <div className={cardClass}>
                <h3 className={sectionHeaderClass}>Suggested aims</h3>
                <div className="flex flex-wrap gap-2">
                  {ui.suggested_aims.map((aim) => (
                    <button
                      key={aim}
                      type="button"
                      className={btnSecondary}
                      disabled={loading}
                      onClick={() => sendUserMessage(aim)}
                    >
                      {aim}
                    </button>
                  ))}
                </div>
              </div>
            )}

          {ui.proposals && ui.proposals.length > 0 && (
            <div className={cardClass}>
              <h3 className={sectionHeaderClass}>Proposals</h3>
              {ui.proposals.map((p, i) => (
                <p key={i} className="text-sm mt-1">
                  <strong>{i + 1}.</strong>{" "}
                  {String(
                    (p as { aims?: string[] }).aims?.join?.(", ") ||
                      (p as { title?: string }).title ||
                      JSON.stringify(p)
                  )}
                </p>
              ))}
            </div>
          )}

          {ui.saved_plans && ui.saved_plans.length > 0 && (
            <div className={cardClass}>
              <h3 className={sectionHeaderClass}>Saved plans</h3>
              {ui.saved_plans.map((p) => (
                <p key={p.id || p.label} className="text-sm mt-1">
                  <strong>{p.label || p.id}</strong>: {(p.aims || []).join(", ")}
                </p>
              ))}
            </div>
          )}

          {ui.plan && (
            <div className={cardClass}>
              <h3 className={sectionHeaderClass}>Active plan</h3>
              {(ui.plan.aims || []).map((a) => (
                <p key={a} className="text-sm mt-1">
                  {a}
                </p>
              ))}
              {ui.plan.benefits && <p className="text-sm text-muted mt-2">{ui.plan.benefits}</p>}
            </div>
          )}

          {ui.done && (
            <div className={cardClass}>
              <h3 className={sectionHeaderClass}>Ready for planner</h3>
              <p className="text-sm">Line: {ui.line || "—"}</p>
              <p className="text-sm">
                Aims:{" "}
                {(ui.planner_payload?.task_definition?.aims || ui.plan?.aims || []).join(", ") ||
                  "—"}
              </p>
              <p className="text-muted text-xs mt-2">
                Session complete. Start a new analysis from the top bar.
              </p>
            </div>
          )}

          <ActionButtons
            ui={ui}
            isLive={isLive}
            isDone={isDone}
            onSendMessage={sendUserMessage}
            loading={loading}
          />
        </>
      )}
    </section>
  );
}
