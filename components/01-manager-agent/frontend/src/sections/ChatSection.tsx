import { FormEvent, KeyboardEvent, Fragment, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  panelClass, monoClass, btnPrimary, btnSecondary,
  userBubbleClass, managerCardClass,
  qrPrimaryClass, qrSecondaryClass,
  composerBannerClass,
} from "../lib/styles";
import { useSessionStore, useIsDone, useIsLive } from "../stores/sessionStore";
import { useUiStore } from "../stores/uiStore";
import type { TurnUi } from "../types/manager";
import {
  IconUser, IconCheck, IconCheckCircle,
  IconMapPin, IconDatabase, IconClock, IconTarget,
} from "../lib/icons";

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
  };
  return (
    <div
      className="bg-white/[0.02] border border-border rounded-lg p-3.5 mb-2.5 last:mb-0 cursor-pointer transition-all hover:border-stage-manager-line hover:bg-stage-manager-soft/20 hover:-translate-y-px relative group"
      onClick={() => onSelect(`confirm ${index + 1}`)}
    >
      <span className="hidden group-hover:block absolute top-3 right-3 text-[10.5px] font-semibold text-stage-manager">
        select →
      </span>
      <div className="flex items-center gap-2 mb-1.5">
        <span className="w-5 h-5 rounded-md bg-stage-manager-soft text-stage-manager font-mono text-[11px] flex items-center justify-center font-semibold shrink-0">
          {index + 1}
        </span>
        <span className="text-sm font-semibold text-text">{p.title || `Option ${index + 1}`}</span>
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

/* ── Main chat section ── */
export default function ChatSection() {
  const turns = useSessionStore((s) => s.turns);
  const loading = useSessionStore((s) => s.loading);
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
  const [input, setInput] = useState("");

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading || isDone) return;
    const text = input;
    setInput("");
    await sendUserMessage(text);
  };

  /* ── Build action buttons for quick replies ── */
  const buildQuickReplies = (ui: TurnUi, onSend: (msg: string) => void) => {
    const btns: { label: string; msg: string; primary?: boolean }[] = [];

    if (ui.proposals?.length) {
      btns.push({ label: "See more options", msg: "more options" });
      btns.push({ label: "Change something\u2026", msg: "change something" });
    } else if (ui.plan?.aims?.length && !ui.done) {
      btns.push({ label: "Go — proceed", msg: "go", primary: true });
      btns.push({ label: "More options", msg: "more options" });
      btns.push({ label: "Change something\u2026", msg: "change something" });
    }

    if (!btns.length) return null;

    return (
      <div className="flex flex-wrap gap-2 mt-4 pt-3.5 border-t border-border/30">
        {btns.map((b) => (
          <button
            key={b.label}
            type="button"
            className={b.primary ? qrPrimaryClass : qrSecondaryClass}
            onClick={() => onSend(b.msg)}
          >
            {b.primary && <IconCheck size={11} />}
            {b.label}
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
        {turns.length === 0 && (
          <p className="text-muted text-sm">
            What would you like to analyze? Try a line name like Vinayaka or fruits test.
          </p>
        )}
        {turns.map((turn, i) => {
          const prevTurn = turns[i - 1];
          const ui = turn.ui;
          const schema = turn.schema;
          const isSelected = i === selectedTurnIndex;

          return (
            <Fragment key={turn.turn_index ?? i}>
              {i > 0 && <hr className="border-t border-border/30 my-3" />}
              <div
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
                      <div className="mt-3 pt-2.5 border-t border-border/30">
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
                              className={chipClass("amber")}
                            >
                              <IconDatabase size={11} />
                              {ds}
                            </span>
                          ))}
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

                    {/* Plan mode */}
                    {ui?.plan?.aims?.length && !ui?.proposals?.length && (
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
                          <p>
                            <b className="text-text font-medium">Aims</b>{" "}
                            <span className="text-text">{ui.plan.aims.join(", ")}</span>
                          </p>
                        </div>
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

                    {/* Proposals mode */}
                    {ui?.proposals?.length > 0 && (
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
                            onSelect={sendUserMessage}
                          />
                        ))}
                      </div>
                    )}

                    {/* Fallback markdown */}
                    {!ui?.plan?.aims?.length && !ui?.proposals?.length && (
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
                    {ui && buildQuickReplies(ui, sendUserMessage)}
                    {!ui?.plan?.aims?.length && !ui?.proposals?.length && ui?.next_step && (
                      <div className="mt-3 pt-3 border-t border-border/30 text-sm text-foreground">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {ui.next_step}
                        </ReactMarkdown>
                      </div>
                    )}
                    {!ui?.plan?.aims?.length && !ui?.proposals?.length && ui?.suggested_aims?.length > 0 && (
                      <div className="mt-3 flex flex-col gap-2">
                        {ui.suggested_aims.map((aim, i) => (
                          <button
                            key={aim}
                            type="button"
                            onClick={() => sendUserMessage(aim)}
                            className="w-full text-left px-4 py-2.5 text-sm rounded-lg bg-bg-deep border border-border shadow-sm hover:shadow-lg hover:-translate-y-0.5 hover:bg-surface-1 active:translate-y-0.5 active:shadow-inner transition-all duration-150 cursor-pointer"
                          >
                            <span className="text-xs font-semibold text-stage-manager uppercase tracking-wider mr-2">
                              Suggestion {i + 1}:
                            </span>
                            <span className="text-text">{aim}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </Fragment>
          );
        })}
        {loading && <p className="text-muted text-sm">Thinking\u2026</p>}

        {isDone && (
          <div className="rounded-xl border border-border/60 bg-surface-2 p-4 mb-3 mt-3">
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
          <div className="flex gap-2 bg-surface-1 border border-border border-t-0 rounded-b-xl p-3">
            <input
              type="text"
              className="flex-1 rounded-lg border border-border/60 bg-white/[0.03] text-tertiary italic px-3 py-2 text-sm"
              placeholder="Session complete"
              disabled
            />
            <button
              type="button"
              className="bg-white/[0.06] text-tertiary border border-border rounded-lg px-4 py-2 text-sm font-semibold cursor-not-allowed"
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
            className="flex-1 rounded-lg border border-border bg-app text-text px-3 py-2 text-sm"
            placeholder="Ask anything\u2026"
            value={input}
            onChange={(e) => setInput(e.target.value)}
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
