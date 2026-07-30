import { useState, useEffect, useCallback, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import { panelClass, resultCardClass, resultTagClass, resultBadgeClass, miniTableClass, insightNoteClass } from "../lib/styles";
import { useOutputStore } from "../stores/outputStore";
import { useSessionStore } from "../stores/sessionStore";
import { useDatasetStore } from "../stores/datasetStore";
import { listDatasets } from "../api/client";
import { QueryActions, type QueryResultState } from "./QueryActions";
import { IconDatabase, IconTarget, IconClock, IconChart } from "../lib/icons";
import { t, useT, tCount } from "../lib/i18n";
import type { DatasetInfo } from "../types";

function relativeTime(timestamp: number): string {
  const diff = Math.floor((Date.now() - timestamp) / 1000);
  if (diff < 5) return t("output.justNow");
  if (diff < 60) return t("output.secAgo", { count: diff });
  if (diff < 3600) return t("output.minAgo", { count: Math.floor(diff / 60) });
  if (diff < 86400) return t("output.hrAgo", { count: Math.floor(diff / 3600) });
  return t("output.daysAgo", { count: Math.floor(diff / 86400) });
}

export default function OutputPanel() {
  const t = useT();
  const results = useOutputStore((s) => s.results);
  const removeResult = useOutputStore((s) => s.removeResult);
  const clearResults = useOutputStore((s) => s.clearResults);
  const selectedAims = useSessionStore((s) => s.selectedAims);
  const turns = useSessionStore((s) => s.turns);
  const contextSummaries = useSessionStore((s) => s.contextSummaries);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [contextExpandedId, setContextExpandedId] = useState<string | null>(null);
  const [, forceUpdate] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => forceUpdate((n) => n + 1), 30000);
    return () => clearInterval(timer);
  }, []);

  const sessionId = useSessionStore((s) => s.sessionId);
  const sendUserMessage = useSessionStore((s) => s.sendUserMessage);
  const loading = useSessionStore((s) => s.loading);
  const storeAttached = useDatasetStore((s) => s.attached);
  const [summarizing, setSummarizing] = useState(false);
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);

  const datasetLookup = useMemo(() => {
    const map = new Map<string, DatasetInfo>();
    for (const ds of datasets) {
      map.set(ds.dataset_name, ds);
    }
    return map;
  }, [datasets]);

  function filterAvailable(names: string[]): { available: string[]; missing: string[] } {
    const available: string[] = [];
    const missing: string[] = [];
    for (const name of names) {
      (datasetLookup.has(name) ? available : missing).push(name);
    }
    return { available, missing };
  }

  useEffect(() => {
    listDatasets().then(setDatasets).catch(console.error);
  }, []);

  const handleSummarize = useCallback(async () => {
    if (!sessionId || summarizing) return;
    setSummarizing(true);
    try {
      const { available, missing } = filterAvailable(storeAttached);
      if (missing.length > 0) console.warn("Datasets not available for summary:", missing);
      const lineName = available.join(",");
      const msg = "Provide a comprehensive summary of all analysis findings so far: what was analyzed, what were the key findings, patterns discovered, and any recommendations. Cover all datasets and aims that have been explored.";
      await sendUserMessage(msg, lineName, [], "summary");
    } finally {
      setSummarizing(false);
    }
  }, [sessionId, summarizing, storeAttached, sendUserMessage]);

  const aimProposals = useSessionStore((s) => s.aimProposals);
  const resultCount = results.length;

  const runProposal = async (p: { aim: string; description: string; datasets?: string[] }) => {
    const { available, missing } = filterAvailable(p.datasets || []);
    if (missing.length > 0) {
      console.warn("Datasets not available, skipping aim:", missing);
      return;
    }
    useSessionStore.setState((s) => ({
      selectedAims: s.selectedAims.some((a) => a.aim === p.aim)
        ? s.selectedAims
        : [...s.selectedAims, { aim: p.aim, description: p.description, datasets: available }],
      aimProposals: s.aimProposals.filter((a) => a.aim.toLowerCase() !== p.aim.toLowerCase()),
    }));
    if (available.length > 0) {
      const store = useDatasetStore.getState();
      store.addMultiple(available);
      store.attachMultiple(available);
    }
    const lineName = useDatasetStore.getState().attached.join(",");
    const msg = `Run analysis: ${p.description || p.aim}`;
    const res = await sendUserMessage(msg, lineName, [p.aim], "research", "focus", { [p.aim]: p.description });
    if (res?.result_uuid && res?.query_result) {
      useOutputStore.getState().addResult({
        aim: p.aim,
        description: p.description,
        datasets: p.datasets,
        result: { loading: false, ...res.query_result } as QueryResultState,
      });
      useSessionStore.setState((s) => ({
        completedActions: { ...s.completedActions, [p.aim]: res.result_uuid! },
      }));
    }
  };

  return (
    <section className={`${panelClass} order-3 lg:order-none text-sm flex flex-col`} data-tour="output-panel">
      <div className="flex items-center justify-between mb-3 shrink-0">
        <div className="flex items-center gap-2">
          <h2 className="font-display text-xs font-semibold tracking-wider uppercase text-muted">{t("output.title")}</h2>
          {resultCount > 0 && (
            <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-surface-2 text-text border border-border/50">
              {resultCount}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            className={`text-[11px] font-bold px-2.5 py-1 rounded-full border transition-colors ${summarizing ? "opacity-50 cursor-not-allowed" : "bg-amber-500/80 text-black border-amber-500/60 hover:bg-amber-500"} border-border/50`}
            onClick={handleSummarize}
            disabled={summarizing}
          >
            <span className="flex items-center gap-1">
              {summarizing ? (
                <IconChart size={12} className="animate-spin" />
              ) : (
                <svg viewBox="0 0 24 24" fill="currentColor" width="12" height="12"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
              )}
              {summarizing ? t("output.summarizing") : t("output.summarize")}
            </span>
          </button>
          <button
            type="button"
            className="text-[11px] font-medium px-2 py-1 rounded-full border border-border/50 text-muted hover:text-ic-red hover:border-ic-red/30 transition-colors"
            onClick={clearResults}
          >
            {t("output.clearAll")}
          </button>
        </div>
      </div>

      {resultCount === 0 ? (
        <div className="flex flex-col items-center justify-center flex-1 text-center px-6">
          <p className="text-sm text-muted max-w-xs">
            {t("output.nothingToShow")}
          </p>
        </div>
      ) : (
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
                  <div className="flex items-center gap-1">
                    <span className="flex items-center">
                      <button
                        type="button"
                        className={`shrink-0 text-[11px] font-medium px-1.5 py-0.5 rounded-full border transition-colors ${
                          selectedAims.some((a) => a.aim === r.aim)
                            ? "bg-ic-teal-soft/40 text-ic-teal border-ic-teal/30 hover:bg-ic-teal-soft/60"
                            : "text-muted border-border/50 hover:text-ic-teal hover:border-ic-teal/30"
                        }`}
                        onClick={() => {
                          if (selectedAims.some((a) => a.aim === r.aim)) {
                            useSessionStore.setState((s) => ({
                              selectedAims: s.selectedAims.filter((a) => a.aim !== r.aim),
                            }));
                          } else {
                            useSessionStore.setState((s) => ({
                              selectedAims: s.selectedAims.some((a) => a.aim === r.aim)
                                ? s.selectedAims
                                : [...s.selectedAims, { aim: r.aim, description: r.description, datasets: r.datasets }],
                            }));
                          }
                        }}
                        title={selectedAims.some((a) => a.aim === r.aim) ? t("output.addedTooltip") : t("output.addTooltip")}
                      >
                        {selectedAims.some((a) => a.aim === r.aim) ? t("output.added") : t("output.addLabel")}
                      </button>
                    </span>
                    <button
                      type="button"
                      className="shrink-0 w-6 h-6 flex items-center justify-center rounded hover:bg-white/[0.06] text-muted hover:text-ic-red transition-colors"
                      onClick={() => removeResult(r.id)}
                      title={t("output.removeResult")}
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="12" height="12" strokeWidth="2.2">
                        <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                      </svg>
                    </button>
                  </div>
                </div>

              <div className="flex items-center gap-2 mb-2">
                <span className="text-[11px] text-muted">
                  {tCount(t, "common.rowCount", rowCount)}
                </span>
                <span className="text-border">·</span>
                <span className="text-[11px] text-tertiary flex items-center gap-1">
                  <IconClock size={10} />
                  {relativeTime(r.created_at)}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className={`text-[11px] font-medium px-2 py-0.5 rounded-full border transition-colors ${isExpanded ? "bg-accent text-white border-accent" : "text-muted border-border/50 hover:text-text"}`}
                  onClick={() => setExpandedId(isExpanded ? null : r.id)}
                >
                  {isExpanded ? t("output.hideDetails") : t("output.showDetails")}
                </button>
                <button
                  type="button"
                  className={`text-[11px] font-medium px-2 py-0.5 rounded-full border transition-colors ${contextExpandedId === r.id ? "bg-ic-violet text-white border-ic-violet" : "text-muted border-border/50 hover:text-ic-violet hover:border-ic-violet/30"}`}
                  onClick={() => setContextExpandedId(contextExpandedId === r.id ? null : r.id)}
                >
                  {contextExpandedId === r.id ? t("output.hideContext") : t("output.showContext")}
                </button>
              </div>

              {isExpanded && (
                <div className="mt-3 space-y-3">
                  {r.description && (
                    <div className="rounded-xl border-l-3 border-l-ic-blue bg-ic-blue-soft/10 border border-border/40 p-3">
                      <div className="flex items-center gap-1.5 text-[10.5px] font-semibold tracking-wider uppercase text-ic-blue mb-1">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="12" height="12" strokeWidth="2.2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
                        {t("common.description")}
                      </div>
                      <div className="prose-custom text-sm text-text leading-relaxed">
                        <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>{r.description}</ReactMarkdown>
                      </div>
                    </div>
                  )}
                  {r.datasets && r.datasets.length > 0 && (
                    <div>
                      <div className="text-[10.5px] font-semibold tracking-wider uppercase text-tertiary mb-1.5">{t("common.datasets")}</div>
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

              {contextExpandedId === r.id && (
                <div className="mt-3 rounded-xl border border-border/40 bg-surface-2 p-3 space-y-2">
                  <div className="text-[10.5px] font-semibold tracking-wider uppercase text-tertiary">{t("output.enrichmentContextFor", { aim: r.aim })}</div>
                  {(() => {
                    const aimTag = `aim:${r.aim}`;
                    const dsTags = (r.datasets || []).map((d) => `dataset:${d}`);
                    const allTags = [aimTag, ...dsTags];
                    const relevantSummaries: { tag: string; summary: string }[] = [];
                    for (const tag of allTags) {
                      const entries = contextSummaries[tag] || [];
                      for (const e of entries) {
                        relevantSummaries.push({ tag, summary: e.summary });
                      }
                    }
                    const relevantTurns = turns.filter((t) =>
                      t.aims?.includes(r.aim) || t.datasets?.some((d) => r.datasets?.includes(d))
                    ).slice(-3);
                    return (
                      <>
                        {relevantSummaries.length === 0 && relevantTurns.length === 0 && (
                          <p className="text-[11px] text-muted">{t("output.noPriorContext")}</p>
                        )}
                        {relevantSummaries.map((s, i) => (
                          <div key={i} className="text-[11px] text-text/80 border-l-2 border-ic-teal pl-2">
                            <span className="text-[10px] text-muted">[{s.tag}]</span> {s.summary}
                          </div>
                        ))}
                        {relevantTurns.map((t, i) => (
                          <div key={i} className="text-[11px] text-text/60 border-l-2 border-border pl-2">
                            <span className="text-[10px] text-muted">[Turn]</span> {(t.user || "").slice(0, 60)}
                          </div>
                        ))}
                      </>
                    );
                  })()}
                </div>
              )}
            </div>
          );
        })}
      </div>
      )}

      {aimProposals.length > 0 && (
        <div className="flex-[0_0_20%] border-t border-border pt-2 mt-2 overflow-y-auto min-h-0">
          <div className="flex items-center gap-1.5 text-[10.5px] font-semibold tracking-wider uppercase text-muted mb-2">
            <IconTarget size={12} />
            {t("output.proposals")}
            <span className="text-[11px] font-medium px-1.5 py-0.5 rounded-full bg-surface-2 text-text border border-border/50">
              {aimProposals.length}
            </span>
          </div>
          <div className="flex flex-col gap-1">
            {aimProposals
              .filter((p) => !selectedAims.some((a) => a.aim === p.aim))
              .map((p, i) => (
                <button
                  key={i}
                  type="button"
                  disabled={loading}
                  className={`text-[11px] px-2 py-0.5 rounded-full border transition-colors ${loading ? "cursor-not-allowed opacity-50" : "bg-ic-violet-soft/20 text-ic-violet border-ic-violet/20 hover:bg-ic-violet-soft/40"}`}
                  onClick={() => runProposal(p)}
                >
                  + {p.aim}
                </button>
              ))}
          </div>
        </div>
      )}
    </section>
  );
}
