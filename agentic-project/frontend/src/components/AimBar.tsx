import { IconTarget, IconChart } from "../lib/icons";
import { QueryResultState } from "../sections/QueryActions";

interface Aim {
  aim: string;
  description?: string;
  benefits?: string;
  datasets?: string[];
  columns?: { dataset: string; names: string[] }[];
}

interface ViewingResultState {
  aim: string;
  description?: string;
  datasets?: string[];
  result: QueryResultState;
}

export function AimBar({
  selectedAims,
  aimResults,
  completedActions,
  runningAim,
  loading,
  onRunSql,
  onRerun,
  onViewResult,
  onRemove,
  onPreview,
}: {
  selectedAims: Aim[];
  aimResults: Record<string, QueryResultState>;
  completedActions: Record<string, string>;
  runningAim: string | null;
  loading: boolean;
  onRunSql: (aim: Aim) => void;
  onRerun: (aim: Aim) => void;
  onViewResult: (state: ViewingResultState) => void;
  onRemove: (aimText: string) => void;
  onPreview: (aim: Aim) => void;
}) {
  if (selectedAims.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5 mb-2">
      {selectedAims.map((a) => {
        const isCompleted = a.aim in completedActions;
        const isRunning = runningAim === a.aim;
        const result = aimResults[a.aim];
        return (
          <div key={a.aim} className="flex flex-wrap items-center gap-1">
            <span
              className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-1 rounded-full bg-stage-planner-soft/40 text-stage-planner border border-stage-planner-line/30 cursor-pointer"
              onClick={() => onPreview(a)}
            >
              {isCompleted && <span className="text-[10px] text-emerald-500">✓</span>}
              <IconTarget size={11} className="shrink-0" />
              <span className="hover:brightness-125 transition-all">{a.aim}</span>
              <button
                type="button"
                className={`ml-1 -mr-1 w-5 h-5 flex items-center justify-center rounded-full transition-colors ${loading ? "cursor-not-allowed text-muted/30" : "hover:bg-ic-red/10 hover:text-ic-red text-muted"}`}
                onClick={(e) => { e.stopPropagation(); if (!loading) onRemove(a.aim); }}
                title={loading ? "Processing... please wait" : "Remove"}
                disabled={loading}
              >
                ×
              </button>
            </span>
            {isRunning ? (
              <button
                type="button"
                className="text-[11px] font-medium px-1.5 py-0.5 rounded-full bg-ic-amber-soft/40 text-ic-amber border border-ic-amber/30 shrink-0 cursor-wait"
                disabled
                title="Generating query..."
              >
                <span className="inline-block animate-spin">
                  <IconChart size={12} className="inline-block animate-hue-cycle" />
                </span>
              </button>
            ) : isCompleted && result?.error ? (
              <button
                type="button"
                className="text-[11px] font-medium px-1.5 py-0.5 rounded-full bg-ic-red-soft/40 text-ic-red border border-ic-red/30 hover:bg-ic-red-soft/60 transition-colors shrink-0"
                onClick={() => onRerun(a)}
                title="Retry failed query"
              >
                ↻ Retry
              </button>
            ) : isCompleted ? (
              <>
                <button
                  type="button"
                  className="text-[11px] font-medium px-1.5 py-0.5 rounded-full bg-accent text-white hover:bg-accent/80 transition-colors shrink-0"
                  onClick={() => onRerun(a)}
                  title="Re-run"
                >
                  ↻
                </button>
                {result && (
                  <button
                    type="button"
                    className="text-[11px] font-medium px-1.5 py-0.5 rounded-full bg-ic-teal-soft/40 text-ic-teal border border-ic-teal/30 hover:bg-ic-teal-soft/60 transition-colors shrink-0"
                    title={`View results: ${result.row_count} rows`}
                    onClick={() => onViewResult({ aim: a.aim, description: a.description, datasets: a.datasets, result })}
                  >
                    <IconChart size={12} className="inline-block" />
                  </button>
                )}
              </>
            ) : (
              <button
                type="button"
                className={`text-[11px] font-medium px-1.5 py-0.5 rounded-full transition-colors shrink-0 ${loading ? "bg-accent/50 text-white/50 cursor-not-allowed" : "bg-accent text-white hover:bg-accent/80"}`}
                onClick={() => !loading && onRunSql(a)}
                title={loading ? "Processing... please wait" : "Run SQL for this aim"}
                disabled={loading}
              >
                ▶ Run
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
