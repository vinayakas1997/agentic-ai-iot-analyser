import { useState, useRef, useEffect } from "react";
import { useSessionStore, useSelectedTurn, useIsLive } from "../stores/sessionStore";
import { panelClass, monoClass } from "../lib/styles";
import { IconCheck, IconMenu, IconClock, IconDatabase, IconGrid, IconEye, IconEdit } from "../lib/icons";

function Stepper() {
  const executionEvents = useSessionStore((s) => s.executionEvents);
  const turn = useSelectedTurn();
  const hasTurn = !!turn;
  const ui = turn?.ui;

  const plannerStart = executionEvents.some((e) => e.topic === "planner.start");
  const plannerDone = executionEvents.some((e) => e.topic === "planner.result");
  const execRun = executionEvents.some((e) => e.topic === "executor.run");
  const execDone = executionEvents.some((e) => e.topic === "task.complete");

  const managerBlinking = hasTurn && !ui?.done;
  const managerActive = !!ui?.done;
  const plannerBlinking = (ui?.done || plannerStart) && !plannerDone;
  const plannerActive = plannerDone;
  const execBlinking = (plannerDone || execRun) && !execDone;
  const execActive = execDone;

  const stepActiveClass: Record<string, string> = {
    "stage-manager": "bg-stage-manager text-[#0a0a0a] shadow-[0_0_0_1px_var(--stage-manager-line),0_0_18px_2px_var(--stage-manager-soft)]",
    "stage-planner": "bg-stage-planner text-[#0a0a0a] shadow-[0_0_0_1px_var(--stage-planner-line),0_0_18px_2px_var(--stage-planner-soft)]",
    "stage-execution": "bg-stage-execution text-[#0a0a0a] shadow-[0_0_0_1px_var(--stage-execution-line),0_0_18px_2px_var(--stage-execution-soft)]",
  };

  const stepBlinkingClass: Record<string, string> = {
    "stage-manager": "bg-stage-manager text-[#0a0a0a] shadow-[0_0_0_1px_var(--stage-manager-line),0_0_18px_2px_var(--stage-manager-soft)] animate-pulse-glow-manager",
    "stage-planner": "bg-stage-planner text-[#0a0a0a] shadow-[0_0_0_1px_var(--stage-planner-line),0_0_18px_2px_var(--stage-planner-soft)] animate-pulse-glow-planner",
    "stage-execution": "bg-stage-execution text-[#0a0a0a] shadow-[0_0_0_1px_var(--stage-execution-line),0_0_18px_2px_var(--stage-execution-soft)] animate-pulse-glow-execution",
  };

  const stepInactiveClass: Record<string, string> = {
    "stage-manager": "bg-stage-manager-soft text-stage-manager",
    "stage-planner": "bg-stage-planner-soft text-stage-planner",
    "stage-execution": "bg-stage-execution-soft text-stage-execution",
  };

  const Step = ({
    label,
    active,
    blinking,
    color,
    icon,
  }: {
    label: string;
    active: boolean;
    blinking?: boolean;
    color: "stage-manager" | "stage-planner" | "stage-execution";
    icon?: React.ReactNode;
  }) =>
    blinking ? (
      <div
        className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg ${stepBlinkingClass[color]} font-semibold text-xs`}
      >
        {label}
      </div>
    ) : active ? (
      <div
        className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg ${stepActiveClass[color]} font-semibold text-xs`}
      >
        {icon}
        {label}
      </div>
    ) : (
      <div className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg ${stepInactiveClass[color]} font-semibold text-xs`}>
        <span className="w-1.5 h-1.5 rounded-full bg-current" />
        {label}
      </div>
    );

  return (
    <div className="flex items-center gap-1.5 mb-5 p-3 rounded-xl bg-surface-1 border-2 border-border">
      <Step label="Manager" active={managerActive} blinking={managerBlinking} color="stage-manager" icon={managerActive ? <IconCheck size={11} /> : undefined} />
      <span className="text-tertiary text-[11px]">→</span>
      <Step label="Planner" active={plannerActive} blinking={plannerBlinking} color="stage-planner" />
      <span className="text-tertiary text-[11px]">→</span>
      <Step label="Execution" active={execActive} blinking={execBlinking} color="stage-execution" />
    </div>
  );
}

export default function ContextSection() {
  const sessionMeta = useSessionStore((s) => s.sessionMeta);
  const turns = useSessionStore((s) => s.turns);
  const turn = useSelectedTurn();
  const isLive = useIsLive();
  const sendUserMessage = useSessionStore((s) => s.sendUserMessage);
  const updateSessionTitle = useSessionStore((s) => s.updateSessionTitle);
  const schema = turn?.schema;

  const [selectedDataset, setSelectedDataset] = useState<string | null>(null);
  const [columnsExpanded, setColumnsExpanded] = useState(false);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleInput, setTitleInput] = useState("");
  const titleInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingTitle && titleInputRef.current) {
      titleInputRef.current.focus();
      titleInputRef.current.select();
    }
  }, [editingTitle]);

  const handleTitleSave = () => {
    setEditingTitle(false);
    if (sessionMeta?.session_id && titleInput !== (sessionMeta.title || "")) {
      updateSessionTitle(sessionMeta.session_id, titleInput);
    }
  };

  const filteredColumns = selectedDataset && schema?.columns
    ? schema.columns.filter((c) => c.dataset === selectedDataset)
    : schema?.columns ?? [];
  const displayColumns = columnsExpanded ? filteredColumns : filteredColumns.slice(0, 5);

  return (
    <section className={`${panelClass} order-1 lg:order-none overflow-y-auto text-sm`}>
      <Stepper />

      <div className="flex items-center gap-2 font-display text-xs font-semibold tracking-wider uppercase text-muted mb-3">
        <span className="inline-flex items-center justify-center w-[22px] h-[22px] rounded-[7px] bg-ic-violet-soft text-ic-violet">
          <IconMenu size={13} />
        </span>
        Context
      </div>

      {sessionMeta && (
        <div className="rounded-xl border border-border bg-surface-1 p-4 mb-4 shadow-[0_1px_0_rgba(255,255,255,0.02)_inset,0_8px_24px_-12px_rgba(0,0,0,0.5)]">
          <div className="flex items-center gap-2 text-sm font-semibold text-text mb-3">
            <span className="inline-flex items-center justify-center w-[22px] h-[22px] rounded-[7px] bg-ic-blue-soft text-ic-blue">
              <IconClock size={13} />
            </span>
            Session
          </div>
          <div className="flex items-center gap-1.5 mb-0.5">
            {editingTitle ? (
              <input
                ref={titleInputRef}
                type="text"
                className="flex-1 rounded-lg border border-accent bg-app text-text px-2 py-1 text-sm font-semibold"
                value={titleInput}
                onChange={(e) => setTitleInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleTitleSave();
                  if (e.key === "Escape") setEditingTitle(false);
                }}
                onBlur={handleTitleSave}
                maxLength={30}
              />
            ) : (
              <button
                type="button"
                className="flex items-center gap-1.5 text-sm font-semibold text-text group cursor-pointer"
                onClick={() => {
                  setTitleInput(sessionMeta.title || "");
                  setEditingTitle(true);
                }}
              >
                <span>{sessionMeta.title || sessionMeta.session_id.slice(0, 8)}</span>
                <IconEdit size={11} className="opacity-50 text-muted" />
              </button>
            )}
          </div>
          <div className="text-[11.5px] text-tertiary mb-2">
            <span className={monoClass}>{sessionMeta.session_id}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[13px] text-muted">
              Turns: <b className="text-text font-medium">{turns.length}</b>
            </span>
            <span className="text-muted">·</span>
            <span
              className={`text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded border ${
                sessionMeta.mode === "man"
                  ? "bg-stage-manager-soft text-stage-manager border-stage-manager-line/40"
                  : sessionMeta.mode === "plan"
                    ? "bg-stage-planner-soft text-stage-planner border-stage-planner-line/40"
                    : sessionMeta.mode === "exe"
                      ? "bg-stage-execution-soft text-stage-execution border-stage-execution-line/40"
                      : "bg-ic-blue-soft text-ic-blue border-ic-blue/30"
              }`}
            >
              {sessionMeta.mode || "ask"}
            </span>
          </div>
        </div>
      )}

      {!schema ? (
        <p className="text-muted text-sm">No schema snapshot.</p>
      ) : (
        <>
          {schema.datasets && schema.datasets.length > 0 && (
            <div className="rounded-xl border-2 border-border bg-surface-1 p-4 mb-4 shadow-[0_1px_0_rgba(255,255,255,0.02)_inset,0_8px_24px_-12px_rgba(0,0,0,0.5)]">
              <div className="flex items-center gap-2 text-sm font-semibold text-text mb-3">
                <span className="inline-flex items-center justify-center w-[22px] h-[22px] rounded-[7px] bg-ic-amber-soft text-ic-amber">
                  <IconDatabase size={13} />
                </span>
                Datasets
              </div>
              {schema.datasets.map((ds) => (
                <div
                  key={ds.name}
                  onClick={() => {
                    setSelectedDataset((prev) => (prev === ds.name ? null : ds.name));
                    setColumnsExpanded(false);
                  }}
                  className={`rounded-lg p-3 mb-2 last:mb-0 transition-colors cursor-pointer ${
                    selectedDataset === ds.name
                      ? "bg-ic-amber-soft/70 border-2 border-ic-amber/20"
                      : "border-2 border-transparent hover:bg-white/[0.03]"
                  }`}
                >
                  <b className="font-medium text-text">{ds.name}</b>
                  {ds.table && (
                    <>
                      {" "}
                      <span className="text-tertiary">→</span>{" "}
                      <span className={monoClass}>{ds.table}</span>
                    </>
                  )}
                  {ds.role && (
                    <span className="text-tertiary"> ({ds.role})</span>
                  )}
                  {ds.description && (
                    <div className="text-[12px] text-tertiary mt-0.5">{ds.description}</div>
                  )}
                  {ds.data_earliest_ts && (
                    <div className="text-[11px] text-ic-blue mt-0.5">
                      Data from <span className={monoClass}>{ds.data_earliest_ts.slice(0, 10)}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {schema.columns && schema.columns.length > 0 && (
            <div className="rounded-xl border-2 border-border bg-surface-1 p-4 mb-4 shadow-[0_1px_0_rgba(255,255,255,0.02)_inset,0_8px_24px_-12px_rgba(0,0,0,0.5)]">
              <div className="flex items-center gap-2 text-sm font-semibold text-text mb-3">
                <span className="inline-flex items-center justify-center w-[22px] h-[22px] rounded-[7px] bg-ic-teal-soft text-ic-teal">
                  <IconGrid size={13} />
                </span>
                Columns
                {selectedDataset && (
                  <span className="text-tertiary font-normal">— {selectedDataset}</span>
                )}
              </div>
              <div className="overflow-x-auto rounded-lg border-2 border-border">
                <table className="min-w-full text-[12.5px] border-collapse">
                  <thead>
                    <tr className="bg-white/[0.03] border-b-2 border-border">
                      <th className="font-display text-[10.5px] font-semibold tracking-wider uppercase text-tertiary text-left py-2 px-2.5">Name</th>
                      <th className="font-display text-[10.5px] font-semibold tracking-wider uppercase text-tertiary text-left py-2 px-2.5">Type</th>
                      <th className="font-display text-[10.5px] font-semibold tracking-wider uppercase text-tertiary text-left py-2 px-2.5">Meaning</th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayColumns.map((c, i) => (
                      <tr key={`${c.dataset}-${c.name}-${i}`} className="border-b-2 border-border/30 last:border-b-0">
                        <td className={`${monoClass} font-medium text-text py-2 px-2.5`}>{c.name}</td>
                        <td className={`${monoClass} text-accent text-[11.5px] py-2 px-2.5`}>{c.datatype}</td>
                        <td className="text-muted py-2 px-2.5">{c.meaning || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {filteredColumns.length > 5 && (
                <div
                  className="text-center text-[11px] text-tertiary mt-2 cursor-pointer hover:text-text transition-colors flex items-center justify-center gap-1"
                  onClick={() => setColumnsExpanded(!columnsExpanded)}
                >
                  <IconEye size={12} />
                  {columnsExpanded ? "Show less" : `${filteredColumns.length - 5} more columns`}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}
