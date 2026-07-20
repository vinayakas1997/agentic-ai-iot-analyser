import { useState, useEffect } from "react";
import { panelClass, btnSecondary, resultCardClass, resultTagClass, resultBadgeClass, miniTableClass, insightNoteClass } from "../lib/styles";
import { useOutputStore } from "../stores/outputStore";
import { QueryActions } from "./QueryActions";
import { IconDatabase, IconTarget, IconClock } from "../lib/icons";

function relativeTime(timestamp: number): string {
  const diff = Math.floor((Date.now() - timestamp) / 1000);
  if (diff < 5) return "just now";
  if (diff < 60) return `${diff} sec ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} hr ago`;
  return `${Math.floor(diff / 86400)} days ago`;
}

export default function OutputPanel() {
  const results = useOutputStore((s) => s.results);
  const removeResult = useOutputStore((s) => s.removeResult);
  const clearResults = useOutputStore((s) => s.clearResults);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [, forceUpdate] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => forceUpdate((n) => n + 1), 30000);
    return () => clearInterval(timer);
  }, []);

  const resultCount = results.length;

  if (resultCount === 0) {
    return (
      <section className={`${panelClass} order-3 lg:order-none text-sm`}>
        <div className="flex flex-col items-center justify-center h-full text-center px-6">
          <span className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-stage-execution-soft text-stage-execution mb-4">
            <IconDatabase size={22} />
          </span>
          <h3 className="text-base font-semibold text-text mb-1">No results yet</h3>
          <p className="text-sm text-muted max-w-xs">
            Run an aim from the chat to collect analysis results here
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className={`${panelClass} order-3 lg:order-none text-sm`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <h2 className="font-display text-xs font-semibold tracking-wider uppercase text-muted">Analysis Results</h2>
          <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-surface-2 text-text border border-border/50">
            {resultCount}
          </span>
        </div>
        <button
          type="button"
          className="text-[11px] font-medium px-2 py-1 rounded-full border border-border/50 text-muted hover:text-ic-red hover:border-ic-red/30 transition-colors"
          onClick={clearResults}
        >
          Clear all
        </button>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0 pr-1 space-y-2.5">
        {results.map((r) => {
          const isExpanded = expandedId === r.id;
          const rowCount = r.result.row_count ?? 0;
          return (
            <div key={r.id} className={resultCardClass}>
              <div className="flex items-start justify-between gap-2 mb-1">
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className={resultBadgeClass}>
                    <IconTarget size={12} />
                  </span>
                  <span className="font-medium text-text text-sm truncate">{r.aim}</span>
                </div>
                <button
                  type="button"
                  className="shrink-0 w-6 h-6 flex items-center justify-center rounded hover:bg-white/[0.06] text-muted hover:text-ic-red transition-colors"
                  onClick={() => removeResult(r.id)}
                  title="Remove result"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="12" height="12" strokeWidth="2.2">
                    <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                  </svg>
                </button>
              </div>

              <div className="flex items-center gap-2 mb-2">
                <span className="text-[11px] text-muted">
                  {rowCount} row{rowCount !== 1 ? "s" : ""}
                </span>
                <span className="text-border">·</span>
                <span className="text-[11px] text-tertiary flex items-center gap-1">
                  <IconClock size={10} />
                  {relativeTime(r.created_at)}
                </span>
              </div>

              <button
                type="button"
                className={`text-[11px] font-medium px-2 py-0.5 rounded-full border transition-colors ${isExpanded ? "bg-accent text-white border-accent" : "text-muted border-border/50 hover:text-text"}`}
                onClick={() => setExpandedId(isExpanded ? null : r.id)}
              >
                {isExpanded ? "▼ Hide Details" : "▶ Show Details"}
              </button>

              {isExpanded && (
                <div className="mt-3 space-y-3">
                  {r.description && (
                    <div className="rounded-xl border-l-3 border-l-ic-blue bg-ic-blue-soft/10 border border-border/40 p-3">
                      <div className="flex items-center gap-1.5 text-[10.5px] font-semibold tracking-wider uppercase text-ic-blue mb-1">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="12" height="12" strokeWidth="2.2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
                        Description
                      </div>
                      <p className="text-sm text-text leading-relaxed">{r.description}</p>
                    </div>
                  )}
                  {r.datasets && r.datasets.length > 0 && (
                    <div>
                      <div className="text-[10.5px] font-semibold tracking-wider uppercase text-tertiary mb-1.5">Datasets</div>
                      <div className="flex flex-wrap gap-1">
                        {r.datasets.map((ds) => (
                          <span key={ds} className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full border bg-ic-amber-soft/20 text-ic-amber border-ic-amber/20">
                            {ds}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  <QueryActions queryResult={r.result} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
