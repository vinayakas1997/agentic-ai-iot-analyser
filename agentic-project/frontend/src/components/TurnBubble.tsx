import { useMemo } from "react";
import { monoClass, fieldLabelClass, insightNoteClass } from "../lib/styles";
import { IconUser, IconStar, IconGrid, IconDatabase, IconTarget } from "../lib/icons";
import { datasetColor } from "../lib/datasetColors";
import { QueryActions, QueryResultState } from "../sections/QueryActions";
import type { Turn, AnalysisAction } from "../types/manager";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import { parseSuggestions } from "../lib/parseSuggestions";
import { SuggestionCard } from "./SuggestionCard";
import type { DatasetInfo } from "../types";
import { useT } from "../lib/i18n";
import { useSessionStore } from "../stores/sessionStore";

function escapeAsterisks(text: string): string {
  return text.replace(/\*\*/g, "\x00BOLD\x00")
    .replace(/\*/g, "\\*")
    .replace(/\x00BOLD\x00/g, "**");
}

export function TurnBubble({ turn, queryResult, selectedAims, runningAim, loading, onToggleAction, onScrollToTurn, onRerunAim, datasets }: {
  turn: Turn;
  queryResult?: QueryResultState;
  selectedAims?: { aim: string }[];
  runningAim?: string | null;
  loading?: boolean;
  onToggleAction?: (action: AnalysisAction) => void;
  onScrollToTurn?: (turnId: string) => void;
  onRerunAim?: (aim: { aim: string; description: string; datasets?: string[] }) => void;
  datasets?: DatasetInfo[];
}) {
  const t = useT();
  const completedActions = useSessionStore((s) => s.completedActions);
  const hasDetail = turn.description || turn.benefits || (turn.columns && turn.columns.length > 0);
  const hasActions = turn.analysis_actions && turn.analysis_actions.length > 0;

  const actionsBar = useMemo(() => {
    if (!hasActions || !onToggleAction) return null;
    return (
      <div className="mt-3 space-y-1">
        {turn.analysis_actions!.map((action, i) => {
          const key = `${turn.created_at}:${action.name}`;
          const isThisLoading = runningAim === action.name;
          const isCompleted = completedActions[action.name] !== undefined;
          const isAttached = selectedAims?.some(a => a.aim === action.name);

          if (isThisLoading) {
            return (
              <button
                key={key}
                type="button"
                disabled
                className="text-[11px] px-2.5 py-1 rounded-full border transition-colors flex items-center gap-1.5 bg-black/[0.08] text-muted/40 border-border/20 cursor-not-allowed"
              >
                <span className="w-2.5 h-2.5 rounded-full bg-yellow-400 animate-pulse" />
                {action.name}
              </button>
            );
          }

          if (isCompleted && isAttached) {
            return (
              <div key={key} className="flex items-center gap-1">
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => !loading && onToggleAction(action)}
                  className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors flex items-center gap-1.5 bg-emerald-50 text-emerald-600 border-emerald-200 hover:bg-emerald-100 cursor-pointer ${loading ? "opacity-50 cursor-not-allowed" : ""}`}
                  title={loading ? t("common.processingWait") : t("turn.clickToDetach")}
                >
                  <span className="text-[10px]">✓</span>
                  {action.name}
                </button>
                {onRerunAim && (
                  <button
                    type="button"
                    disabled={loading}
                    onClick={() => !loading && onRerunAim({ aim: action.name, description: action.description, datasets: action.datasets })}
                    className={`text-[11px] px-1.5 py-1 rounded-full border transition-colors ${loading ? "text-muted/30 cursor-not-allowed border-border/10" : "text-muted hover:text-text hover:border-border border-border/30"}`}
                    title={loading ? t("common.processingWait") : t("turn.rerunAnalysis")}
                  >
                    ↻
                  </button>
                )}
              </div>
            );
          }

          if (isCompleted) {
            return (
              <div key={key} className="flex items-center gap-1">
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => !loading && onScrollToTurn?.(completedActions![action.name])}
                  className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors flex items-center gap-1.5 bg-emerald-50 text-emerald-600 border-emerald-200 hover:bg-emerald-100 cursor-pointer ${loading ? "opacity-50 cursor-not-allowed" : ""}`}
                >
                  <span className="text-[10px]">✓</span>
                  {action.name}
                </button>
                <span
                  className="text-[11px] px-1.5 py-1 rounded-full text-muted/60 cursor-default border border-transparent"
                >
                  {t("common.view")}
                </span>
              </div>
            );
          }

          if (isAttached) {
            return (
              <button
                key={key}
                type="button"
                disabled={loading}
                onClick={() => !loading && onToggleAction(action)}
                className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors flex items-center gap-1.5 ${loading ? "bg-ic-teal-soft/20 text-ic-teal/50 border-ic-teal/10 cursor-not-allowed" : "bg-ic-teal-soft/40 text-ic-teal border-ic-teal/30 hover:bg-ic-teal-soft/60 cursor-pointer"}`}
              >
                <span className="text-[10px]">+</span>
                {action.name}
              </button>
            );
          }

          return (
            <button
              key={key}
              type="button"
              disabled={loading}
              onClick={() => !loading && onToggleAction(action)}
              className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors flex items-center gap-1.5 ${loading ? "bg-ic-violet-soft/10 text-ic-violet/50 border-ic-violet/10 cursor-not-allowed" : "bg-ic-violet-soft/20 text-ic-violet border-ic-violet/20 hover:bg-ic-violet-soft/40 cursor-pointer"}`}
            >
              <span className="text-[10px]">+</span>
              {action.name}
            </button>
          );
        })}
      </div>
    );
  }, [hasActions, onToggleAction, turn.analysis_actions, turn.created_at, runningAim, completedActions, selectedAims, onScrollToTurn, onRerunAim, loading]);

  const deepIterationBlocks = useMemo(() => {
    if (!turn.deep_iterations?.length) return null;
    return (
      <div className="mt-4 space-y-4">
        <div className="text-[11px] font-semibold tracking-wider uppercase text-stage-manager/70 mb-1">
          {t("turn.researchSteps", { count: turn.deep_iterations.length })}
        </div>
        {turn.deep_iterations.map((iter, idx) => {
          const iterResult: QueryResultState = {
            loading: false,
            sql: iter.sql,
            columns: iter.columns,
            column_types: iter.column_types,
            rows: iter.rows,
            row_count: iter.row_count,
            chart_suggestions: iter.chart_suggestions ?? null,
          };
          return (
            <div key={idx} className="pt-3 border-t border-border/10">
              <div className="text-[10.5px] font-semibold text-stage-manager mb-2 flex items-center gap-1.5">
                <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-stage-manager/10 text-stage-manager text-[10px] font-bold">
                  {idx + 1}
                </span>
                {t("turn.iteration", { count: idx + 1 })}
              </div>
              <div className="prose-custom text-sm text-text/90 mb-3">
                <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>{escapeAsterisks(iter.explanation)}</ReactMarkdown>
              </div>
              <QueryActions queryResult={iterResult} />
            </div>
          );
        })}
      </div>
    );
  }, [turn.deep_iterations]);

  const parsedSuggestions = useMemo(() => parseSuggestions(turn.agent), [turn.agent]);

  const actionCards = useMemo(() => {
    if (parsedSuggestions || !turn.analysis_actions?.length) return null;
    return (
      <div className="mt-3 space-y-2">
        {turn.analysis_actions.map((action, i) => (
          <div key={i} className="rounded-xl border border-border/40 bg-surface-1/60 p-3">
            <div className="flex items-center gap-2 mb-1.5">
              <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-stage-manager/10 text-stage-manager text-[10px] font-bold shrink-0">
                {i + 1}
              </span>
              <h4 className="font-semibold text-sm text-text leading-snug">{action.name}</h4>
            </div>
            {action.goal && (
              <div className="flex items-start gap-1.5 text-[13px] text-text/80 mb-2 pl-0.5">
                <IconTarget size={12} className="mt-0.5 text-ic-amber shrink-0" />
                <span>{action.goal}</span>
              </div>
            )}
            {action.datasets && action.datasets.length > 0 && (
              <div className="mb-2">
                <div className={fieldLabelClass}>
                  <IconDatabase size={11} />
                  {t("common.datasets")}
                </div>
                <div className="flex flex-wrap gap-1">
                  {action.datasets.map((d, j) => (
                    <span key={j} className={`${monoClass} text-[11px] px-2 py-0.5 rounded-full border ${datasetColor(d)}`}>
                      {d}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {action.columns && action.columns.length > 0 && (
              <div className="mb-2">
                <div className={fieldLabelClass}>
                  <IconGrid size={11} />
                  {t("common.columns")}
                </div>
                <div className="flex flex-wrap gap-1">
                  {action.columns.map((c, j) => (
                    <span key={j} className={`${monoClass} text-[11px] px-2 py-0.5 rounded-full border border-border/50 text-muted bg-black/[0.03]`}>
                      {c}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {action.description && (
              <p className="text-[13px] text-text/70 leading-relaxed mb-1.5">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ p: ({ children }) => <>{children}</> }}>
                  {escapeAsterisks(action.description)}
                </ReactMarkdown>
              </p>
            )}
            {action.insight && (
              <p className={insightNoteClass}>
                <strong>{t("suggestion.expectedInsight")}</strong> {action.insight}
              </p>
            )}
          </div>
        ))}
      </div>
    );
  }, [parsedSuggestions, turn.analysis_actions, datasets, t]);

  const agentContent = (
    <div className="flex-1 min-w-0">
      <div className="prose-custom text-sm text-text/90">
        {parsedSuggestions ? (
          <>
            {parsedSuggestions.intro && (
              <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>{escapeAsterisks(parsedSuggestions.intro)}</ReactMarkdown>
            )}
            <div className="mt-2">
              {parsedSuggestions.suggestions.map((s, i) => (
                <SuggestionCard key={i} suggestion={s} index={i} datasets={datasets} />
              ))}
            </div>
          </>
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>{escapeAsterisks(turn.agent)}</ReactMarkdown>
        )}
      </div>
      {turn.truncated && (
        <div className="rounded-lg border border-ic-amber/40 bg-ic-amber-soft/30 px-3 py-2 mt-3 text-[12px] text-ic-amber leading-snug">
          {turn.stopped_reason === "error" ? t("turn.truncatedErrorWarning") : t("turn.truncatedWarning")}
        </div>
      )}
      {actionCards}
      {deepIterationBlocks}
      {turn.description && (
        <div className="rounded-xl border-l-3 border-l-ic-blue bg-ic-blue-soft/10 border border-border/40 p-3 mb-3">
          <div className="flex items-center gap-1.5 text-[10.5px] font-semibold tracking-wider uppercase text-ic-blue mb-1">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="12" height="12" strokeWidth="2.2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
            {t("common.description")}
          </div>
          <div className="prose-custom text-sm text-text leading-relaxed">
            <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>{escapeAsterisks(turn.description)}</ReactMarkdown>
          </div>
        </div>
      )}
      {turn.benefits && (
        <div className="text-sm text-text/70 mb-3">
          <span className="text-stage-manager font-semibold">{t("turn.benefitsLabel")}</span> {turn.benefits}
        </div>
      )}
      {turn.columns && turn.columns.length > 0 && (
        <div className="mt-3">
          <div className="flex items-center gap-1.5 text-[10.5px] font-semibold tracking-wider uppercase text-tertiary mb-1.5">
            <IconGrid size={11} />
            {t("common.columnsUsed")}
          </div>
          <div className="flex flex-wrap gap-1">
            {turn.columns.map((c, i) => (
              <span key={i} className={`${monoClass} text-[11px] px-2 py-0.5 rounded-full border ${datasetColor(c.dataset)}`}>
                {c.name}
              </span>
            ))}
          </div>
        </div>
      )}
      {hasActions && actionsBar}
      {!turn.deep_iterations?.length &&
        (turn.query_results && turn.query_results.length > 0 ? (
          <div className="space-y-3">
            {turn.query_results.map((qr, qi) => (
              <QueryActions key={qi} queryResult={qr as QueryResultState} />
            ))}
          </div>
        ) : (
          <QueryActions queryResult={queryResult} />
        ))}
    </div>
  );

  return (
    <div className="mb-4" data-turn-id={turn.created_at}>
      <div className="flex items-start gap-2 mb-2">
        <span className="inline-flex items-center justify-center w-[26px] h-[26px] rounded-lg bg-ic-blue-soft text-ic-blue shrink-0 mt-0.5">
          <IconUser size={13} />
        </span>
        <div className="rounded-xl border-2 border-user-blue-line border-l-3 border-l-user-blue bg-surface-1 p-3 flex-1 text-sm">
          {turn.user}
        </div>
      </div>
      {turn.agent && (
        <div className="flex items-start gap-2">
          <span className="inline-flex items-center justify-center w-[26px] h-[26px] rounded-lg bg-stage-manager-soft text-stage-manager shrink-0 mt-0.5">
            <IconStar size={11} />
          </span>
          {hasDetail ? (
            <div className="flex-1 min-w-0 rounded-xl border-2 border-stage-manager-line border-l-3 border-l-stage-manager bg-surface-2 p-4">
              {agentContent}
            </div>
          ) : (
            <div className="flex-1 min-w-0 rounded-xl border-2 border-stage-manager-line border-l-3 border-l-stage-manager bg-surface-2 p-3 text-sm">
              {agentContent}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
