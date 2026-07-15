import { FormEvent, KeyboardEvent, Fragment, useState, useEffect, useMemo, useRef, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  panelClass, monoClass, btnPrimary, btnSecondary,
  userBubbleClass, managerCardClass,
  qrPrimaryClass, qrSecondaryClass, qrPressedClass,
  composerBannerClass,
} from "../lib/styles";
import { useSessionStore, useIsDone, useIsLive } from "../stores/sessionStore";
import { useUiStore } from "../stores/uiStore";
import type { TurnUi } from "../types/manager";
import {
  IconUser, IconCheck, IconCheckCircle,
  IconMapPin, IconDatabase, IconClock, IconTarget,
  IconMenu, IconEdit,
} from "../lib/icons";
import OnboardingView from "./OnboardingView";

/* ── Selectable proposal card ── */
function OptionCard({
  index,
  proposal,
  onSelect,
}: {
  index: number;
  proposal: Record<string, unknown>;
  onSelect: (msg: string) => void;
}) {
  const p = proposal as {
    title?: string;
    aims?: string[];
    datasets_used?: string[];
    join_description?: string;
    what_you_might_see?: string;
    feasible?: boolean;
    feasibility_reason?: string;
    alternative?: string;
  };
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect(`confirm ${index + 1}`);
    }
  };
  return (
    <div
      className="bg-white/[0.02] border-2 border-border rounded-lg p-3.5 mb-2.5 last:mb-0 cursor-pointer transition-all hover:border-stage-manager-line hover:bg-stage-manager-soft/20 hover:-translate-y-px relative group"
      onClick={() => onSelect(`confirm ${index + 1}`)}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      role="button"
      aria-label={`Select option ${index + 1}: ${p.title || `Option ${index + 1}`}`}
    >
      <span className="hidden group-hover:block absolute top-3 right-3 text-[10.5px] font-semibold text-stage-manager">
        select →
      </span>
      <div className="flex items-center gap-2 mb-1.5">
        <span className="w-5 h-5 rounded-md bg-stage-manager-soft text-stage-manager font-mono text-[11px] flex items-center justify-center font-semibold shrink-0">
          {index + 1}
        </span>
        <span className="text-sm font-semibold text-text">{p.title || `Option ${index + 1}`}</span>
        {p.feasible !== undefined && (
          <span className={`ml-auto text-[10px] font-semibold tracking-wider uppercase px-1.5 py-0.5 rounded-full ${
            p.feasible
              ? "bg-green-900/40 text-green-300 border border-green-500/30"
              : "bg-red-900/40 text-red-300 border border-red-500/30"
          }`}>
            {p.feasible ? "Doable" : "Not doable"}
          </span>
        )}
      </div>
      <div className="ml-7 text-xs text-muted leading-relaxed">
        {p.aims?.join(", ")}
        {(p.datasets_used || p.join_description) && (
          <div className="mt-1.5">
            {p.datasets_used && (
              <span className={`${monoClass} text-tertiary mr-3`}>
                Datasets <b className="text-text font-sans font-semibold">{p.datasets_used.join(", ")}</b>
              </span>
            )}
            {p.join_description && (
              <span className={`${monoClass} text-tertiary`}>
                Join <b className="text-text font-sans font-semibold">{p.join_description}</b>
              </span>
            )}
          </div>
        )}
        {p.what_you_might_see && (
          <div className="italic text-tertiary mt-1 text-[11.5px]">
            You might see: {p.what_you_might_see}
          </div>
        )}
        {p.feasibility_reason && (
          <div className="text-[11px] text-muted mt-1.5 leading-snug">
            {p.feasibility_reason}
          </div>
        )}
        {p.feasible === false && p.alternative && (
          <button
            type="button"
            className="mt-1.5 text-[11px] font-semibold text-ic-blue hover:text-blue-300 underline underline-offset-2"
            onClick={(e) => {
              e.stopPropagation();
              onSelect(p.alternative!);
            }}
          >
            Try instead: {p.alternative}
          </button>
        )}
      </div>
    </div>
  );
}

/* ── Chip styling helper ── */
function chipClass(accent?: "blue" | "amber" | "coral") {
  const base = "inline-flex items-center gap-1 font-mono text-[11.5px] px-2 py-0.5 rounded-[7px] border";
  if (accent === "blue") return `${base} text-ic-blue bg-ic-blue-soft border-ic-blue/30`;
  if (accent === "amber") return `${base} text-ic-amber bg-ic-amber-soft border-ic-amber/30`;
  if (accent === "coral") return `${base} text-ic-coral bg-ic-coral-soft border-ic-coral/30`;
  return `${base} text-text bg-white/[0.04] border-border`;
}

/* ── Internal protocol messages that shouldn't render as a raw chat turn ── */
function isControlMessage(text: string): boolean {
  return text === "__confirm__" || /^confirm\s+\d+$/i.test(text);
}

/* ── Resolve chip accent from dataset role ── */
function datasetAccent(
  dsName: string,
  datasets?: { name: string; role?: string }[]
): "blue" | "amber" | "coral" {
  const entry = datasets?.find((d) => d.name === dsName);
  if (entry?.role === "primary") return "blue";
  if (entry?.role === "secondary") return "amber";
  if (entry?.role === "tertiary") return "coral";
  return "amber";
}

/* ── Main chat section ── */
export default function ChatSection() {
  const turns = useSessionStore((s) => s.turns);
  const loading = useSessionStore((s) => s.loading);
  const statusMessage = useSessionStore((s) => s.statusMessage);
  const sendUserMessage = useSessionStore((s) => s.sendUserMessage);
  const reopenSession = useSessionStore((s) => s.reopenSession);
  const forkSession = useSessionStore((s) => s.forkSession);
  const newSession = useSessionStore((s) => s.newSession);
  const executionEvents = useSessionStore((s) => s.executionEvents);
  const selectedTurnIndex = useUiStore((s) => s.selectedTurnIndex);
  const selectTurn = useUiStore((s) => s.selectTurn);
  const isLive = useIsLive();
  const isDone = useIsDone();
  const plannerStarted = executionEvents.some((e) => e.topic === "planner.start");
  const error = useSessionStore((s) => s.error);
  const setError = useSessionStore((s) => s.setError);
  const wsStatus = useSessionStore((s) => s.wsStatus);
  const pendingTurn = useSessionStore((s) => s.pendingTurn);
  const [input, setInput] = useState("");
  const [shake, setShake] = useState(false);
  const [activeProposal, setActiveProposal] = useState<{ index: number; title: string } | null>(null);
  const [showChangeInput, setShowChangeInput] = useState(false);
  const [changeInput, setChangeInput] = useState("");
  const [pressedButtons, setPressedButtons] = useState<Set<string>>(new Set());

  /* ── Track which suggested aims have already been asked, and where ── */
  const turnRefs = useRef<Record<number, HTMLDivElement | null>>({});
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);

  /* ── Auto-scroll to the newest turn whenever one arrives ── */
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [turns.length]);
  const pickedAimTurnIndex = useMemo(() => {
    const map: Record<string, number> = {};
    turns.forEach((t, i) => {
      const text = (t.user || "").trim();
      if (text && !(text in map)) map[text] = i;
    });
    return map;
  }, [turns]);
  const scrollToTurn = (idx: number) => {
    selectTurn(idx);
    turnRefs.current[idx]?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  /* ── Typewriter placeholder ── */
  const typeExamples = [
    "Tell me about this machine",
    "What is the average cost by fruit?",
    "Show me sales by region",
  ];
  const [placeholder, setPlaceholder] = useState("Ask anything\u2026");
  const typeIdxRef = useRef(0);
  const charIdxRef = useRef(0);
  const deletingRef = useRef(false);
  const typeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const typewriterActiveRef = useRef(true);

  const typeLoop = useCallback(() => {
    if (!typewriterActiveRef.current) return;
    const full = typeExamples[typeIdxRef.current];

    if (!deletingRef.current) {
      charIdxRef.current++;
      setPlaceholder(full.slice(0, charIdxRef.current) + "\u258c");
      if (charIdxRef.current === full.length) {
        deletingRef.current = true;
        typeTimerRef.current = setTimeout(typeLoop, 1400);
        return;
      }
      typeTimerRef.current = setTimeout(typeLoop, 45);
    } else {
      charIdxRef.current--;
      setPlaceholder(full.slice(0, charIdxRef.current) + (charIdxRef.current > 0 ? "\u258c" : ""));
      if (charIdxRef.current === 0) {
        deletingRef.current = false;
        typeIdxRef.current = (typeIdxRef.current + 1) % typeExamples.length;
        typeTimerRef.current = setTimeout(typeLoop, 300);
        return;
      }
      typeTimerRef.current = setTimeout(typeLoop, 25);
    }
  }, []);

  useEffect(() => {
    if (turns.length === 0) {
      typewriterActiveRef.current = true;
      typeIdxRef.current = 0;
      charIdxRef.current = 0;
      deletingRef.current = false;
      typeLoop();
    }
    return () => {
      if (typeTimerRef.current) clearTimeout(typeTimerRef.current);
    };
  }, [turns.length, typeLoop]);

  const stopTypewriter = () => {
    typewriterActiveRef.current = false;
    if (typeTimerRef.current) clearTimeout(typeTimerRef.current);
    setPlaceholder("Ask anything\u2026");
  };

  useEffect(() => {
    if (!pendingTurn) {
      setActiveProposal(null);
      setShowChangeInput(false);
      setChangeInput("");
    }
  }, [pendingTurn]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim()) {
      setShake(true);
      setTimeout(() => setShake(false), 300);
      return;
    }
    if (loading || isDone) return;
    const text = input;
    setInput("");
    await sendUserMessage(text);
  };

  /* ── Render action buttons from backend-provided actions ── */
  const renderActions = (ui: TurnUi, onSend: (msg: string) => void, turnIndex: number) => {
    const actions = ui.actions || [];
    const showChange = ui.show_change;
    if (!actions.length && !showChange) return null;

    const changePressed = pressedButtons.has(`${turnIndex}:change`);

    return (
      <div className="flex flex-wrap gap-2 mt-4 pt-3.5 border-t-2 border-border/30">
        {actions.map((b) => {
          const icon = b.msg === "more options"
            ? <IconMenu size={11} />
            : null;
          const isPressed = b.msg === "more options" && pressedButtons.has(`${turnIndex}:more options`);
          return (
            <button
              key={b.label}
              type="button"
              className={isPressed ? qrPressedClass : (b.primary ? qrPrimaryClass : qrSecondaryClass)}
              onClick={() => {
                if (b.msg === "more options") {
                  setPressedButtons(prev => new Set(prev).add(`${turnIndex}:more options`));
                }
                onSend(b.msg);
              }}
            >
              {icon}
              {b.label}
            </button>
          );
        })}
        {showChange && (showChangeInput ? (
          <div className="flex gap-2 items-start" key="change-input">
            <input
              type="text"
              className="flex-1 rounded-lg border-2 border-border bg-bg-deep text-text px-3 py-1.5 text-sm min-w-[200px]"
              placeholder="Describe your changes..."
              value={changeInput}
              onChange={(e) => setChangeInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && changeInput.trim()) {
                  setPressedButtons(prev => new Set(prev).add(`${turnIndex}:change`));
                  onSend(changeInput);
                  setChangeInput("");
                  setShowChangeInput(false);
                }
                if (e.key === "Escape") {
                  setShowChangeInput(false);
                  setChangeInput("");
                }
              }}
              autoFocus
            />
            <button
              type="button"
              className="text-xs px-3 py-1.5 rounded-lg bg-stage-execution text-[#0a1a12] font-semibold whitespace-nowrap"
              onClick={() => {
                if (changeInput.trim()) {
                  setPressedButtons(prev => new Set(prev).add(`${turnIndex}:change`));
                  onSend(changeInput);
                  setChangeInput("");
                  setShowChangeInput(false);
                }
              }}
            >
              Apply
            </button>
            <button
              type="button"
              className="text-xs px-2.5 py-1.5 rounded-lg bg-surface-2 text-muted hover:text-text whitespace-nowrap"
              onClick={() => {
                setShowChangeInput(false);
                setChangeInput("");
              }}
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            key="change"
            type="button"
            className={changePressed ? qrPressedClass : qrSecondaryClass}
            onClick={() => setShowChangeInput(true)}
          >
            <IconEdit size={11} />
            Change something...
          </button>
        ))}
      </div>
    );
  };

  return (
    <section className={`${panelClass} order-2 lg:order-none`}>
      {/* ── Header ── */}
      <div className="flex items-center justify-between mb-3 shrink-0">
        <h2 className="text-base font-semibold font-display">Chat</h2>
        {isDone && (
          <span className="text-[11px] font-semibold tracking-wider uppercase px-2.5 py-1 rounded-full bg-stage-execution-soft text-stage-execution border border-stage-execution-line/40">
            Completed
          </span>
        )}
      </div>

      {/* ── Turns ── */}
      <div className="flex-1 overflow-y-auto min-h-0 pr-1 mb-3">
        {turns.length === 0 && <OnboardingView />}
        {turns.map((turn, i) => {
          if (isControlMessage((turn.user || "").trim())) return null;
          const prevTurn = turns[i - 1];
          const nextTurn = turns[i + 1];
          const ui = turn.ui;
          const schema = turn.schema;
          const isSelected = i === selectedTurnIndex;
          // The backend explicitly signals execution via ui.executed set when
          // phase transitions to "man" (tool_confirm_plan ran).  Previously
          // the frontend inferred this from the next turn's message text, but
          // that heuristic was fragile — it couldn't distinguish the "Go —
          // proceed" button (__confirm__) from a proposal selection (confirm N).
          const confirmedByNextTurn = !!ui?.executed;

          return (
            <Fragment key={turn.turn_index ?? i}>
              {i > 0 && <hr className="border-t-2 border-border/30 my-3" />}
              <div
                ref={(el) => { turnRefs.current[i] = el; }}
                className={`p-2.5 rounded-lg cursor-pointer border-l-2 transition-colors ${
                  isSelected
                    ? "ring-1 ring-accent bg-blue-500/10 border-l-accent"
                    : i % 2 === 1
                      ? "bg-stripe-odd border-l-rail/30"
                      : "border-l-transparent"
                } ${!isSelected ? "hover:bg-white/[0.02]" : ""}`}
                onClick={() => selectTurn(i)}
                onKeyDown={(e: KeyboardEvent) => e.key === "Enter" && selectTurn(i)}
                role="button"
                tabIndex={0}
              >
                {/* ── User bubble ── */}
                {turn.user && (
                  <div className={userBubbleClass}>
                    <div className="flex items-center gap-1.5 text-[11.5px] font-semibold text-user-blue uppercase tracking-wider mb-1.5">
                      <IconUser size={13} />
                      You
                    </div>
                    <p className="text-sm text-text leading-relaxed m-0">{turn.user}</p>

                    {(schema?.line ||
                      schema?.datasets_in_scope?.length ||
                      schema?.time ||
                      schema?.no_time_filter ||
                      ui?.plan?.aims?.length) && (
                      <div className="mt-3 pt-2.5 border-t-2 border-border/30">
                        <span className="text-[10.5px] font-semibold tracking-wider text-tertiary uppercase block mb-1.5">
                          Resolved
                        </span>
                        <div className="flex flex-wrap gap-1.5">
                          {schema?.line && (
                            <span className={chipClass("blue")}>
                              <IconMapPin size={11} />
                              {schema.line}
                            </span>
                          )}
                          {schema?.datasets_in_scope?.map((ds) => (
                            <span
                              key={ds}
                              className={chipClass(datasetAccent(ds, schema.datasets))}
                            >
                              <IconDatabase size={11} />
                              {ds}
                            </span>
                          ))}
                          {schema?.datasets_in_scope?.length > 1 && (
                            <span className={`${monoClass} text-[10.5px] text-ic-violet bg-ic-violet-soft border border-ic-violet/30 px-1.5 py-0.5 rounded-[5px]`}>
                              Cross-table
                            </span>
                          )}
                          {(schema?.time || schema?.no_time_filter || schema?.time_pending) && (
                            <span className={chipClass()}>
                              <IconClock size={11} />
                              {schema?.time
                                ? `${schema.time.start} → ${schema.time.end}`
                                : schema?.time_pending
                                  ? `⏳ ${schema.time_pending}`
                                  : "No time filter"}
                            </span>
                          )}
                          {ui?.plan?.aims?.map((aim) => (
                            <span key={aim} className={chipClass("coral")}>
                              <IconTarget size={11} />
                              {aim}
                            </span>
                          ))}
                          {schema?.joins?.length > 0 && (
                            <div className="w-full flex flex-col gap-1 mt-0.5">
                              {schema.joins.map((join, ji) => (
                                <span
                                  key={ji}
                                  className={`${monoClass} text-[11px] text-ic-blue bg-ic-blue-soft/50 border border-ic-blue/20 px-2 py-0.5 rounded-[6px] w-fit`}
                                >
                                  {join.from_dataset} → {join.to_dataset}
                                  {join.on?.length ? ` on ${join.on.join(", ")}` : ""}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* ── Manager card ── */}
                {turn.agent && (
                  <div className={managerCardClass}>
                    <div className="flex items-center gap-1.5 mb-3">
                      <span className="w-5 h-5 rounded-[6px] bg-stage-manager-soft text-stage-manager flex items-center justify-center">
                        <IconCheckCircle size={12} />
                      </span>
                      <span className="text-[11.5px] font-semibold text-stage-manager uppercase tracking-wider">
                        Manager
                      </span>
                    </div>

                    {/* Explanation text */}
                    {ui?.explanation && (
                      <div className="text-sm text-muted leading-relaxed mb-3 [&>p]:m-0">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {ui.explanation}
                        </ReactMarkdown>
                      </div>
                    )}

                    {/* Plan mode */}
                    {(ui?.plan?.aims?.length ?? 0) > 0 && (ui?.proposals?.length ?? 0) === 0 && (
                      <div>
                        <div className="text-[13.5px] text-muted leading-relaxed space-y-1.5 mb-3">
                          {schema?.line && (
                            <p>
                              <b className="text-text font-medium">Line</b>{" "}
                              <span className={`${monoClass} text-text`}>{schema.line}</span>
                            </p>
                          )}
                          {(schema?.time || schema?.no_time_filter) && (
                            <p>
                              <b className="text-text font-medium">Time</b>{" "}
                              <span className="text-text">
                                {schema?.time
                                  ? `${schema.time.start} → ${schema.time.end}`
                                  : "all data (no date filter)"}
                              </span>
                            </p>
                          )}
                          {schema?.datasets_in_scope?.length > 0 && (
                            <div>
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <b className="text-text font-medium">Datasets</b>
                                {schema.datasets_in_scope.length > 1 && (
                                  <span className={`${monoClass} text-[10.5px] text-ic-violet bg-ic-violet-soft border border-ic-violet/30 px-1.5 py-0.5 rounded-[5px]`}>
                                    ×{schema.datasets_in_scope.length}
                                  </span>
                                )}
                              </div>
                              <div className="flex flex-wrap gap-1.5 mt-1">
                                {schema.datasets_in_scope.map((ds) => (
                                  <span key={ds} className={chipClass(datasetAccent(ds, schema.datasets))}>
                                    <IconDatabase size={11} />
                                    {ds}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                          {schema?.joins?.length > 0 && (
                            <div>
                              <b className="text-text font-medium">Joins</b>
                              <div className="flex flex-col gap-1 mt-1">
                                {schema.joins.map((join, ji) => (
                                  <span
                                    key={ji}
                                    className={`${monoClass} text-[12px] text-ic-blue bg-ic-blue-soft/50 border border-ic-blue/20 px-2 py-0.5 rounded-[6px] w-fit`}
                                  >
                                    {join.from_dataset} → {join.to_dataset}
                                    {join.on?.length ? ` on ${join.on.join(", ")}` : ""}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                          <p>
                            <b className="text-text font-medium">Aims</b>{" "}
                            <span className="text-text">{ui.plan.aims.join(", ")}</span>
                          </p>
                        </div>
                        {ui?.time_default_notice && (
                          <div className="mt-2 p-2 rounded-lg bg-ic-blue-soft/30 border border-ic-blue/20 text-[12px] text-ic-blue">
                            {ui.time_default_notice}
                          </div>
                        )}
                        {ui.plan.benefits && (
                          <>
                            <p className="text-[11px] font-semibold uppercase tracking-wider text-tertiary mb-1.5">
                              Benefits
                            </p>
                            <ul className="m-0 p-0 list-none">
                              {ui.plan.benefits.split("\n").filter(Boolean).map((b, bi) => (
                                <li
                                  key={bi}
                                  className="text-[13px] text-muted leading-relaxed pl-3.5 relative mb-1 before:content-[''] before:absolute before:left-0 before:top-[7px] before:w-1 before:h-1 before:rounded-full before:bg-stage-manager"
                                >
                                  {b}
                                </li>
                              ))}
                            </ul>
                          </>
                        )}
                      </div>
                    )}

                    {/* Single-proposal mode (already-decided, plain prose) */}
                    {ui?.proposals?.length === 1 && (() => {
                      const p = ui.proposals[0] as {
                        title?: string;
                        feasible?: boolean;
                        feasibility_reason?: string;
                        what_you_might_see?: string;
                        alternative?: string;
                      };
                      const bullets = [p.what_you_might_see, p.feasibility_reason].filter(Boolean) as string[];
                      return (
                        <div className="text-[13.5px] text-muted leading-relaxed">
                          <p className="mb-2">
                            Here's the analysis plan for{" "}
                            <b className="text-text">{schema?.line || "this line"}</b>:{" "}
                            <b className="text-text font-medium">{p.title}</b>
                            {p.feasible !== undefined && (
                              <span className={`ml-1.5 text-[11px] font-semibold ${p.feasible ? "text-green-300" : "text-red-300"}`}>
                                ({p.feasible ? "Doable" : "Not doable"})
                              </span>
                            )}
                          </p>
                          {bullets.length > 0 && (
                            <ul className="m-0 p-0 list-none">
                              {bullets.map((b, bi) => (
                                <li
                                  key={bi}
                                  className="text-[13px] text-muted leading-relaxed pl-3.5 relative mb-1 before:content-[''] before:absolute before:left-0 before:top-[7px] before:w-1 before:h-1 before:rounded-full before:bg-stage-manager"
                                >
                                  {b}
                                </li>
                              ))}
                            </ul>
                          )}
                          {p.feasible === false && p.alternative && (
                            <button
                              type="button"
                              className="mt-1.5 text-[11px] font-semibold text-ic-blue hover:text-blue-300 underline underline-offset-2"
                              onClick={() => sendUserMessage(p.alternative!)}
                            >
                              Try instead: {p.alternative}
                            </button>
                          )}
                        </div>
                      );
                    })()}

                    {/* Waiting for planner */}
                    {ui?.phase === "man" && (
                      <div className="flex items-center gap-2 py-3 text-sm text-muted">
                        <span className="w-2.5 h-2.5 rounded-full bg-ic-amber animate-pulse" />
                        Plan confirmed — waiting for the planner to build queries...
                      </div>
                    )}

                    {/* Proposals mode */}
                    {(ui?.proposals?.length ?? 0) > 1 && (
                      <div>
                        <p className="text-[13.5px] text-muted mb-3">
                          Here are {ui.proposals.length} analysis option
                          {ui.proposals.length > 1 ? "s" : ""} for{" "}
                          <b className="text-text">{schema?.line || "this line"}</b>. Select one to
                          proceed:
                        </p>
                        {ui.proposals.map((prop, pi) => (
                          <OptionCard
                            key={pi}
                            index={pi}
                            proposal={prop}
                            onSelect={(msg) => {
                              setActiveProposal({ index: pi, title: (prop.title as string) || `Option ${pi + 1}` });
                              sendUserMessage(msg);
                            }}
                          />
                        ))}
                      </div>
                    )}

                    {/* Fallback markdown */}
                    {(ui?.plan?.aims?.length ?? 0) === 0 && (ui?.proposals?.length ?? 0) === 0 && (
                      <div className="text-sm leading-relaxed space-y-1 [&>p]:m-0 [&>ul]:pl-4 [&>ol]:pl-4 [&>li>p]:m-0 [&>pre]:bg-black/40 [&>pre]:p-2 [&>pre]:rounded [&>pre]:overflow-x-auto [&>code]:bg-black/30 [&>code]:px-1 [&>code]:rounded [&>blockquote]:border-l-2 [&>blockquote]:border-blue-500 [&>blockquote]:pl-3 [&>blockquote]:italic [&>blockquote]:text-muted">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            a: ({ href, children }) => (
                              <a
                                href={href}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="underline text-blue-400"
                              >
                                {children}
                              </a>
                            ),
                            code: ({ className, children, ...props }) => {
                              const isInline = !className;
                              return isInline ? (
                                <code className={`${monoClass} bg-black/30 px-1 rounded`} {...props}>
                                  {children}
                                </code>
                              ) : (
                                <code className={`${monoClass} ${className || ""}`} {...props}>
                                  {children}
                                </code>
                              );
                            },
                          }}
                        >
                          {turn.agent}
                        </ReactMarkdown>
                      </div>
                    )}

                    {/* Quick-reply buttons / next_step fallback */}
                    {ui && (confirmedByNextTurn ? (
                      <div className="flex items-center gap-1.5 mt-4 pt-3.5 border-t-2 border-border/30 text-sm text-stage-execution font-medium">
                        <IconCheck size={14} />
                        Confirmed — sent to execution
                      </div>
                    ) : (
                      renderActions(ui, sendUserMessage, i)
                    ))}
                    {!ui?.plan?.aims?.length && !ui?.proposals?.length && ui?.next_step && (
                      <div className="mt-3 pt-3 border-t-2 border-border/30 text-sm text-foreground">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {ui.next_step}
                        </ReactMarkdown>
                      </div>
                    )}
                    {!ui?.plan?.aims?.length && !ui?.proposals?.length && ui?.suggested_aims?.length > 0 && (
                      <div className="mt-3 flex flex-col gap-3">
                        {(() => {
                          const groups: Record<string, typeof ui.suggested_aims> = {};
                          for (const a of ui.suggested_aims) {
                            const ds = a.dataset || "Other";
                            if (!groups[ds]) groups[ds] = [];
                            groups[ds].push(a);
                          }
                          return Object.entries(groups).map(([dsName, aims]) => {
                            const accent = datasetAccent(dsName, schema?.datasets);
                            return (
                              <div key={dsName}>
                                <div className={`text-[11px] font-semibold tracking-wider uppercase mb-1.5 ${chipClass(accent)} w-fit`}>
                                  <IconDatabase size={11} />
                                  {dsName}
                                  {schema?.datasets?.find(d => d.name === dsName)?.role && (
                                    <span className="ml-1 opacity-70">({schema.datasets.find(d => d.name === dsName)!.role})</span>
                                  )}
                                </div>
                                <div className="flex flex-col gap-1.5">
                                  {aims.map((a) => {
                                    const pickedIdx = pickedAimTurnIndex[a.aim.trim()];
                                    const isPicked = pickedIdx !== undefined;
                                    return (
                                    <button
                                      key={a.aim}
                                      type="button"
                                      onClick={() => (isPicked ? scrollToTurn(pickedIdx) : sendUserMessage(a.aim))}
                                      className={`w-full text-left px-4 py-2.5 text-sm rounded-lg border-2 transition-all duration-150 cursor-pointer ${
                                        isPicked
                                          ? "bg-ic-violet-soft/15 border-ic-violet/40 hover:bg-ic-violet-soft/25"
                                          : accent === "blue"
                                            ? "bg-ic-blue-soft/10 border-ic-blue/20 hover:bg-ic-blue-soft/25 hover:border-ic-blue/40"
                                            : accent === "amber"
                                              ? "bg-ic-amber-soft/10 border-ic-amber/20 hover:bg-ic-amber-soft/25 hover:border-ic-amber/40"
                                              : "bg-ic-coral-soft/10 border-ic-coral/20 hover:bg-ic-coral-soft/25 hover:border-ic-coral/40"
                                      }`}
                                    >
                                      <span className="text-text">{a.aim}</span>
                                      {isPicked && (
                                        <span className="ml-2 text-[10px] font-semibold uppercase tracking-wider text-ic-violet">
                                          ✓ asked
                                        </span>
                                      )}
                                      {a.kpi_value && (
                                        <p className="text-[11px] text-muted mt-0.5 leading-snug">{a.kpi_value}</p>
                                      )}
                                    </button>
                                    );
                                  })}
                                </div>
                              </div>
                            );
                          });
                        })()}
                        {schema?.joins && schema.joins.length > 0 && (
                          <div className="text-[11px] text-ic-blue mt-1 mb-1">
                            Cross-table analysis available:{" "}
                            {schema.joins.map(j => `${j.from_dataset} ↔ ${j.to_dataset}`).join(", ")}
                          </div>
                        )}
                        <div className="text-[11px] text-tertiary italic border-t-2 border-border/20 pt-2 mt-1">
                          These are per-dataset suggestions. For complex or cross-relational analysis, share your thoughts and I'll create a custom plan.
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </Fragment>
          );
        })}
        {pendingTurn && (
          <Fragment>
            <hr className="border-t-2 border-border/30 my-3" />
            <div className="p-2.5 rounded-lg border-l-2 border-l-rail/30 bg-stripe-odd">
              <div className={userBubbleClass}>
                <div className="flex items-center gap-1.5 text-[11.5px] font-semibold text-user-blue uppercase tracking-wider mb-1.5">
                  <IconUser size={13} />
                  You
                </div>
                <p className="text-sm text-text leading-relaxed m-0">
                  {activeProposal
                    ? `Selected Plan ${activeProposal.index + 1}: ${activeProposal.title}`
                    : isControlMessage((pendingTurn.user || "").trim())
                      ? "Confirming…"
                      : pendingTurn.user}
                </p>
                {(pendingTurn.schema?.line ||
                  pendingTurn.schema?.datasets_in_scope?.length ||
                  pendingTurn.schema?.time ||
                  pendingTurn.ui?.plan?.aims?.length) && (
                  <div className="mt-3 pt-2.5 border-t-2 border-border/30">
                    <span className="text-[10.5px] font-semibold tracking-wider text-tertiary uppercase block mb-1.5">
                      Resolved
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {pendingTurn.schema?.line && (
                        <span className={chipClass("blue")}>
                          <IconMapPin size={11} />
                          {pendingTurn.schema.line}
                        </span>
                      )}
                      {pendingTurn.schema?.datasets_in_scope?.map((ds) => (
                        <span key={ds} className={chipClass(datasetAccent(ds, pendingTurn.schema?.datasets))}>
                          <IconDatabase size={11} />
                          {ds}
                        </span>
                      ))}
                      {pendingTurn.schema?.datasets_in_scope?.length > 1 && (
                        <span className={`${monoClass} text-[10.5px] text-ic-violet bg-ic-violet-soft border border-ic-violet/30 px-1.5 py-0.5 rounded-[5px]`}>
                          Cross-table
                        </span>
                      )}
                      {(pendingTurn.schema?.time || pendingTurn.schema?.no_time_filter) && (
                        <span className={chipClass()}>
                          <IconClock size={11} />
                          {pendingTurn.schema?.time
                            ? `${pendingTurn.schema.time.start} → ${pendingTurn.schema.time.end}`
                            : "No time filter"}
                        </span>
                      )}
                      {pendingTurn.ui?.plan?.aims?.map((aim) => (
                        <span key={aim} className={chipClass("coral")}>
                          <IconTarget size={11} />
                          {aim}
                        </span>
                      ))}
                      {pendingTurn.schema?.joins?.length > 0 && (
                        <div className="w-full flex flex-col gap-1 mt-0.5">
                          {pendingTurn.schema.joins.map((join, ji) => (
                            <span
                              key={ji}
                              className={`${monoClass} text-[11px] text-ic-blue bg-ic-blue-soft/50 border border-ic-blue/20 px-2 py-0.5 rounded-[6px] w-fit`}
                            >
                              {join.from_dataset} → {join.to_dataset}
                              {join.on?.length ? ` on ${join.on.join(", ")}` : ""}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
              {pendingTurn.loading && (
                <div className="flex items-center gap-2 py-2 text-muted text-sm">
                  <span className="w-2 h-2 rounded-full bg-stage-manager animate-pulse" />
                  {statusMessage || (activeProposal
                    ? `Building Plan ${activeProposal.index + 1}: ${activeProposal.title}\u2026`
                    : "Thinking\u2026")}
                </div>
              )}
            </div>
          </Fragment>
        )}
        {error && (
          <div className="mb-3 p-3 rounded-lg bg-red-900/30 border-2 border-red-500/30 text-red-300 text-sm flex items-start gap-2">
            <span className="flex-1">{error}</span>
            <button
              type="button"
              className="text-red-400 hover:text-red-300 text-xs font-semibold shrink-0"
              onClick={() => setError(null)}
            >
              Dismiss
            </button>
          </div>
        )}

        {wsStatus === "disconnected" && (
          <div className="mb-3 p-3 rounded-lg bg-amber-900/30 border-2 border-amber-500/30 text-amber-300 text-sm">
            {"Connection lost. Reconnecting\u2026"}
          </div>
        )}

        {isDone && (
          <div className="rounded-xl border-2 border-border/60 bg-surface-2 p-4 mb-3 mt-3">
            <h3 className="flex items-center gap-1.5 font-display text-xs font-semibold tracking-wider uppercase text-muted mb-2">
              Session complete
            </h3>
            <p className="text-muted text-xs mb-3">
              Analysis plan has been sent to the execution pipeline.
            </p>
            <div className="space-y-2">
              {!plannerStarted ? (
                <button
                  type="button"
                  className={btnSecondary + " w-full justify-start"}
                  disabled={loading}
                  onClick={reopenSession}
                >
                  ✏️ Edit — Revise plan
                </button>
              ) : (
                <p className="text-xs text-yellow-400 flex items-center gap-1">
                  ⚠️ Planner has already begun — cannot edit this session.
                </p>
              )}
              <button
                type="button"
                className={btnSecondary + " w-full justify-start"}
                disabled={loading}
                onClick={forkSession}
              >
                🔀 Fork — Continue with new planning
              </button>
              <button
                type="button"
                className={btnSecondary + " w-full justify-start"}
                disabled={loading}
                onClick={newSession}
              >
                ➕ +New — Start fresh
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── Composer ── */}
      {isDone ? (
        <div className="rounded-xl overflow-hidden shrink-0">
          <div className={composerBannerClass}>
            <IconCheck size={13} />
            Session complete — start a new analysis from the top bar
          </div>
          <div className="flex gap-2 bg-surface-1 border-2 border-border border-t-0 rounded-b-xl p-3">
            <input
              type="text"
              className="flex-1 rounded-lg border-2 border-border/60 bg-white/[0.03] text-tertiary italic px-3 py-2 text-sm"
              placeholder="Session complete"
              disabled
            />
            <button
              type="button"
              className="bg-white/[0.06] text-tertiary border-2 border-border rounded-lg px-4 py-2 text-sm font-semibold cursor-not-allowed"
              disabled
            >
              Send
            </button>
          </div>
        </div>
      ) : (
        <form className="flex gap-2 shrink-0" onSubmit={handleSubmit}>
          <input
            type="text"
            className={`flex-1 rounded-lg border-2 border-border bg-app text-text px-3 py-2 text-sm ${shake ? "animate-shake" : ""}`}
            placeholder={placeholder}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onFocus={stopTypewriter}
            disabled={loading || !isLive}
          />
          <button
            type="submit"
            className={btnPrimary}
            disabled={loading || !input.trim()}
          >
            Send
          </button>
        </form>
      )}
      {!isLive && turns.length > 0 && (
        <p className="text-muted text-xs mt-2 shrink-0">
          Viewing step {selectedTurnIndex + 1}. Select latest turn to send messages.
        </p>
      )}
    </section>
  );
}
