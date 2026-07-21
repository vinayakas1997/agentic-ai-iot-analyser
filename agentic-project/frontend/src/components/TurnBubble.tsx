import { useMemo } from "react";
import { monoClass } from "../lib/styles";
import { IconUser, IconStar, IconGrid } from "../lib/icons";
import { datasetColor } from "../lib/datasetColors";
import { QueryActions, QueryResultState } from "../sections/QueryActions";
import type { Turn, AnalysisAction } from "../types/manager";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function TurnBubble({ turn, queryResult, onRunAnalysis, completedActions, runningAction, onScrollToTurn }: {
  turn: Turn;
  queryResult?: QueryResultState;
  onRunAnalysis?: (action: AnalysisAction, turnCreatedAt: string) => void;
  completedActions?: Record<string, string>;
  runningAction?: string | null;
  onScrollToTurn?: (turnId: string) => void;
}) {
  const hasDetail = turn.description || turn.benefits || (turn.columns && turn.columns.length > 0);
  const hasActions = turn.analysis_actions && turn.analysis_actions.length > 0;

  const actionsBar = useMemo(() => {
    if (!hasActions || !onRunAnalysis) return null;
    return (
      <div className="mt-3 space-y-1">
        {turn.analysis_actions!.map((action, i) => {
          const key = `${turn.created_at}:${action.name}`;
          const isThisLoading = runningAction === action.name;
          const isCompleted = completedActions && completedActions[action.name] !== undefined;

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

          if (isCompleted) {
            return (
              <button
                key={key}
                type="button"
                onClick={() => onScrollToTurn?.(completedActions![action.name])}
                className="text-[11px] px-2.5 py-1 rounded-full border transition-colors flex items-center gap-1.5 bg-emerald-50 text-emerald-600 border-emerald-200 hover:bg-emerald-100 cursor-pointer"
              >
                <span className="text-[10px]">✓</span>
                {action.name}
              </button>
            );
          }

          return (
            <button
              key={key}
              type="button"
              onClick={() => onRunAnalysis(action, turn.created_at!)}
              className="text-[11px] px-2.5 py-1 rounded-full border transition-colors flex items-center gap-1.5 bg-ic-violet-soft/20 text-ic-violet border-ic-violet/20 hover:bg-ic-violet-soft/40 cursor-pointer"
            >
              <span className="text-[10px]">▶</span>
              {action.name}
            </button>
          );
        })}
      </div>
    );
  }, [hasActions, onRunAnalysis, turn.analysis_actions, turn.created_at, runningAction, completedActions, onScrollToTurn]);

  const agentContent = (
    <div className="flex-1 min-w-0">
      <div className="prose-custom text-sm text-text/90">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{turn.agent}</ReactMarkdown>
      </div>
      {turn.description && (
        <div className="rounded-xl border-l-3 border-l-ic-blue bg-ic-blue-soft/10 border border-border/40 p-3 mb-3">
          <div className="flex items-center gap-1.5 text-[10.5px] font-semibold tracking-wider uppercase text-ic-blue mb-1">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="12" height="12" strokeWidth="2.2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
            Description
          </div>
          <p className="text-sm text-text leading-relaxed">{turn.description}</p>
        </div>
      )}
      {turn.benefits && (
        <div className="text-sm text-text/70 mb-3">
          <span className="text-stage-manager font-semibold">Benefits:</span> {turn.benefits}
        </div>
      )}
      {turn.columns && turn.columns.length > 0 && (
        <div className="mt-3">
          <div className="flex items-center gap-1.5 text-[10.5px] font-semibold tracking-wider uppercase text-tertiary mb-1.5">
            <IconGrid size={11} />
            Columns used
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
      <QueryActions queryResult={queryResult} />
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
            <div className="flex-1 rounded-xl border-2 border-stage-manager-line border-l-3 border-l-stage-manager bg-surface-2 p-4">
              {agentContent}
            </div>
          ) : (
            <div className="flex-1 rounded-xl border-2 border-stage-manager-line border-l-3 border-l-stage-manager bg-surface-2 p-3 text-sm">
              {agentContent}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
