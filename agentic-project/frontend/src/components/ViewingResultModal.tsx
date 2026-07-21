import { QueryActions, QueryResultState } from "../sections/QueryActions";

interface ViewingResultState {
  aim: string;
  description?: string;
  datasets?: string[];
  result: QueryResultState;
}

export function ViewingResultModal({
  state,
  onClose,
}: {
  state: ViewingResultState;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-surface-1 rounded-2xl border-2 border-border shadow-2xl w-full max-w-2xl mx-4 max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-border/50">
          <h3 className="text-base font-semibold text-text leading-tight pr-2">{state.aim}</h3>
          <button
            type="button"
            className="shrink-0 w-7 h-7 flex items-center justify-center rounded-lg hover:bg-white/[0.06] text-muted hover:text-text transition-colors"
            onClick={onClose}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="16" height="16" strokeWidth="2.5"><path d="M18 6L6 18M6 6l12 12" /></svg>
          </button>
        </div>
        <div className="px-5 py-4 space-y-3">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-ic-teal-soft/40 text-ic-teal border border-ic-teal/30">
              {state.result.row_count} row{state.result.row_count !== 1 ? "s" : ""}
            </span>
          </div>
          {state.description && (
            <div className="rounded-xl border-l-3 border-l-ic-blue bg-ic-blue-soft/10 border border-border/40 p-3">
              <div className="flex items-center gap-1.5 text-[10.5px] font-semibold tracking-wider uppercase text-ic-blue mb-1">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="12" height="12" strokeWidth="2.2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
                Description
              </div>
              <p className="text-sm text-text leading-relaxed">{state.description}</p>
            </div>
          )}
          {state.datasets && state.datasets.length > 0 && (
            <div>
              <div className="text-[10.5px] font-semibold tracking-wider uppercase text-tertiary mb-1.5">Datasets</div>
              <div className="flex flex-wrap gap-1">
                {state.datasets.map((ds) => (
                  <span key={ds} className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full border bg-ic-amber-soft/20 text-ic-amber border-ic-amber/20">
                    {ds}
                  </span>
                ))}
              </div>
            </div>
          )}
          <QueryActions queryResult={state.result} />
        </div>
        <div className="flex items-center justify-end gap-2 px-5 pb-5 pt-2 border-t border-border/50">
          <button
            type="button"
            className="bg-ic-red-soft/40 backdrop-blur-sm border border-ic-red/30 text-ic-red hover:bg-ic-red-soft/60 transition-all rounded-lg px-3 py-1.5 text-sm"
            onClick={onClose}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
