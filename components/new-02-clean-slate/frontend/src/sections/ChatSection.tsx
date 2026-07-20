import { useState, useEffect, useMemo, useRef, useCallback, KeyboardEvent } from "react";
import { panelClass, btnPrimary } from "../lib/styles";
import { useSessionStore } from "../stores/sessionStore";
import { useOutputStore } from "../stores/outputStore";
import { listDatasets, executeQuery } from "../api/client";
import { useDatasetStore } from "../stores/datasetStore";
import { IconDatabase, IconCheck, IconUser, IconTarget } from "../lib/icons";
import { QueryResultState } from "./QueryActions";
import { DatasetColumns } from "../components/DatasetColumns";
import { TurnBubble } from "../components/TurnBubble";
import { AimBar } from "../components/AimBar";
import { PreviewModal } from "../components/PreviewModal";
import { ViewingResultModal } from "../components/ViewingResultModal";
import { datasetColor } from "../lib/datasetColors";

interface DatasetInfo {
  line_name: string;
  dataset_name: string;
  description: string | null;
  table: string | null;
  column_definitions: { name: string; datatype: string; meaning?: string }[];
  role: string | null;
  join_hints: any;
  suggested_aims: any;
  synonyms: string[] | null;
}

interface Aim {
  aim: string;
  description?: string;
  benefits?: string;
  datasets?: string[];
  columns?: { dataset: string; names: string[] }[];
}

export default function ChatSection() {
  const sessionId = useSessionStore((s) => s.sessionId);
  const turns = useSessionStore((s) => s.turns);
  const loading = useSessionStore((s) => s.loading);
  const pendingTurn = useSessionStore((s) => s.pendingTurn);
  const sendUserMessage = useSessionStore((s) => s.sendUserMessage);
  const aimProposals = useSessionStore((s) => s.aimProposals);

  const storeSelected = useDatasetStore((s) => s.selected);
  const storeToggle = useDatasetStore((s) => s.toggle);
  const storeAddMultiple = useDatasetStore((s) => s.addMultiple);
  const storeAttached = useDatasetStore((s) => s.attached);
  const storeDetach = useDatasetStore((s) => s.detach);
  const storeAttachMultiple = useDatasetStore((s) => s.attachMultiple);
  const lockedByAims = useDatasetStore((s) => s.lockedByAims);
  const setLockedByAims = useDatasetStore((s) => s.setLockedByAims);

  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [input, setInput] = useState("");
  const [previewAim, setPreviewAim] = useState<Aim | null>(null);
  const [selectedAims, setSelectedAims] = useState<Aim[]>([]);
  const [expandedDataset, setExpandedDataset] = useState<string | null>(null);
  const [showSearch, setShowSearch] = useState(true);
  const [queryResults, setQueryResults] = useState<Record<string, QueryResultState>>({});
  const [aimResults, setAimResults] = useState<Record<string, QueryResultState>>({});
  const [runningAim, setRunningAim] = useState<string | null>(null);
  const [viewingResult, setViewingResult] = useState<{ aim: string; description?: string; datasets?: string[]; result: QueryResultState } | null>(null);
  const viewingResultRef = useRef(viewingResult);
  viewingResultRef.current = viewingResult;
  const composerRef = useRef<HTMLTextAreaElement>(null);

  const datasetLookup = useMemo(() => {
    const map = new Map<string, DatasetInfo>();
    for (const ds of datasets) {
      map.set(ds.dataset_name, ds);
    }
    return map;
  }, [datasets]);

  useEffect(() => {
    listDatasets().then(setDatasets).catch(() => {});
  }, []);

  const filtered = useMemo(() => {
    if (!searchQuery.trim()) return datasets;
    const q = searchQuery.toLowerCase();
    return datasets.filter(
      (d) =>
        d.dataset_name.toLowerCase().includes(q) ||
        d.line_name.toLowerCase().includes(q) ||
        (d.description && d.description.toLowerCase().includes(q)) ||
        (d.synonyms && d.synonyms.some((s) => s.toLowerCase().includes(q)))
    );
  }, [datasets, searchQuery]);

  const selectedDatasets = useMemo(
    () => datasets.filter((d) => storeSelected.includes(d.dataset_name)),
    [datasets, storeSelected]
  );

  const suggestedAims = useMemo(() => {
    const aims: Aim[] = [];
    for (const ds of selectedDatasets) {
      if (Array.isArray(ds.suggested_aims)) {
        for (const sa of ds.suggested_aims) {
          const key = typeof sa === "string" ? sa : sa.aim;
          const idx = aims.findIndex((a) => a.aim === key);
          if (idx < 0) {
            const base = typeof sa === "string" ? { aim: sa } : sa;
            aims.push({
              ...base,
              datasets: [...new Set([...(base.datasets || []), ds.dataset_name])],
            });
          } else if (!aims[idx].datasets?.includes(ds.dataset_name)) {
            aims[idx].datasets = [...(aims[idx].datasets || []), ds.dataset_name];
          }
        }
      }
    }
    return aims;
  }, [selectedDatasets]);

  const closePreview = useCallback(() => setPreviewAim(null), []);

  useEffect(() => {
    if (!previewAim) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closePreview();
    };
    document.addEventListener("keydown", onKey as any);
    return () => document.removeEventListener("keydown", onKey as any);
  }, [previewAim, closePreview]);

  const useAim = (aim: Aim) => {
    closePreview();
    if (!selectedAims.find((a) => a.aim === aim.aim)) {
      setSelectedAims((prev) => [...prev, aim]);
    }
    useSessionStore.setState((s) => ({
      aimProposals: s.aimProposals.filter((p) => p.aim.toLowerCase() !== aim.aim.toLowerCase()),
    }));
    if (aim.datasets && aim.datasets.length > 0) {
      storeAddMultiple(aim.datasets);
      storeAttachMultiple(aim.datasets);
    }
    composerRef.current?.focus();
  };

  const removeAim = (aimText: string) => {
    setSelectedAims((prev) => prev.filter((a) => a.aim !== aimText));
  };

  const handleRunAimSql = async (aimDef: {aim: string; description: string; datasets?: string[]}) => {
    if (!sessionId) return;
    const aimName = aimDef.aim;
    setRunningAim(aimName);
    setAimResults((prev) => ({ ...prev, [aimName]: { loading: true } }));
    try {
      const parts: string[] = [];
      for (const dsName of (aimDef.datasets && aimDef.datasets.length > 0 ? aimDef.datasets : storeAttached)) {
        const ds = datasetLookup.get(dsName);
        const table = ds?.table || dsName;
        const allCols = ds?.column_definitions?.map((c) => c.name) || [];
        parts.push(`  Dataset: ${dsName} → table \`${table}\`, columns: ${allCols.join(", ")}`);
      }
      const sqlMessage = `Generate a SQL query for: ${aimDef.aim}\n\n${aimDef.description || ""}\n\nAvailable datasets:\n${parts.join("\n\n")}`;
      const lineName = storeAttached.join(",");
      const res = await executeQuery(sessionId, sqlMessage, lineName);
      const resultState: QueryResultState = { loading: false, ...res };
      setRunningAim(null);
      setAimResults((prev) => ({ ...prev, [aimName]: resultState }));
      useOutputStore.getState().addResult({
        aim: aimDef.aim,
        description: aimDef.description,
        datasets: aimDef.datasets,
        result: resultState,
      });
    } catch (e: any) {
      const msg = e.message || "";
      let clean = "Failed to generate a working query. Try rephrasing your request.";
      try {
        const parsed = JSON.parse(msg);
        if (parsed.detail) clean = parsed.detail;
      } catch {}
      const resultState: QueryResultState = { loading: false, error: clean };
      setRunningAim(null);
      setAimResults((prev) => ({ ...prev, [aimName]: resultState }));
      useOutputStore.getState().addResult({
        aim: aimDef.aim,
        description: aimDef.description,
        datasets: aimDef.datasets,
        result: resultState,
      });
    }
  };

  const handleSend = async () => {
    const msg = input.trim() || (selectedAims.length > 0 ? selectedAims.map((a) => a.aim).join(", ") : "");
    if (!msg || !sessionId) return;
    setInput("");
    setShowSearch(false);
    const lineName = storeAttached.join(",");
    await sendUserMessage(msg, lineName);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && (input.trim() || selectedAims.length > 0)) {
      e.preventDefault();
      handleSend();
    }
  };

  useEffect(() => {
    const unsub = useOutputStore.subscribe(
      (state) => state.results,
      (results) => {
        const map: Record<string, QueryResultState> = {};
        for (const r of results) {
          map[r.aim] = r.result;
        }
        setAimResults(map);
      }
    );
    return unsub;
  }, []);

  useEffect(() => {
    const cur = viewingResultRef.current;
    if (!cur) return;
    const updated = aimResults[cur.aim];
    if (updated && updated !== cur.result) {
      setViewingResult((prev) => prev ? { ...prev, result: updated } : null);
    }
  }, [aimResults]);

  useEffect(() => {
    const locked = new Set<string>();
    for (const aim of selectedAims) {
      if (aim.datasets) {
        aim.datasets.forEach((ds) => locked.add(ds));
      }
    }
    setLockedByAims(Array.from(locked));
  }, [selectedAims, setLockedByAims]);

  return (
    <section className={`${panelClass} order-2 lg:order-none`}>
      <div className="rounded-xl border-2 border-border bg-surface-1 p-3 mb-4">
        <button
          type="button"
          className="flex items-center gap-2 w-full text-sm text-left mb-2"
          onClick={() => setShowSearch(!showSearch)}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="14" height="14" strokeWidth="2.2" className={`transition-transform ${showSearch ? 'rotate-90' : ''}`}>
            <path d="M9 18l6-6-6-6" />
          </svg>
          <span className="text-muted text-[11px] font-semibold tracking-wider uppercase">Search datasets</span>
          {!showSearch && storeAttached.length > 0 && (
            <span className="text-[11px] text-muted">({storeAttached.length} attached)</span>
          )}
        </button>

        {showSearch && (
          <div className="space-y-3">
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="14" height="14" strokeWidth="2.2">
                  <circle cx="10.5" cy="10.5" r="7.5" />
                  <path d="M16.5 16.5L21 21" />
                </svg>
              </span>
              <input
                type="text"
                className="w-full rounded-xl border-2 border-border bg-surface-1 text-text text-sm pl-9 pr-3 py-2.5 focus:outline-none focus:border-accent transition-colors"
                placeholder="Search datasets..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            {searchQuery && (
              <div className="mt-2 rounded-xl border-2 border-border bg-surface-1 max-h-[240px] overflow-y-auto">
                {filtered.length === 0 && (
                  <div className="px-3 py-4 text-sm text-muted text-center">No datasets found</div>
                )}
                {filtered.map((ds) => (
                  <div
                    key={ds.dataset_name}
                    className={`border-b border-border/30 last:border-b-0 ${storeSelected.includes(ds.dataset_name) ? "bg-ic-blue-soft/20" : ""}`}
                  >
                    <div
                      className="flex items-center gap-3 w-full text-left px-3 py-2.5 text-sm cursor-pointer hover:bg-white/[0.04] transition-colors"
                      onClick={() => storeToggle(ds.dataset_name)}
                    >
                      <span
                        className={`w-4 h-4 rounded border-2 flex items-center justify-center shrink-0 transition-colors ${
                          storeSelected.includes(ds.dataset_name)
                            ? "bg-accent border-accent text-white"
                            : "border-border"
                        }`}
                      >
                        {storeSelected.includes(ds.dataset_name) && <IconCheck size={10} />}
                      </span>
                      <span className="inline-flex items-center justify-center w-[22px] h-[22px] rounded-[7px] bg-ic-amber-soft text-ic-amber shrink-0">
                        <IconDatabase size={12} />
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-text truncate">{ds.dataset_name}</div>
                        <div className="text-[11px] text-tertiary truncate">
                          {ds.line_name}
                          {ds.role ? ` · ${ds.role}` : ""}
                          {ds.table ? ` · ${ds.table}` : ""}
                        </div>
                      </div>
                      <span className="text-[11px] text-muted shrink-0 whitespace-nowrap">{ds.column_definitions.length} cols</span>
                      <span
                        className="text-[11px] font-medium text-accent hover:text-accent/80 transition-colors shrink-0 ml-1 cursor-pointer"
                        onClick={(e) => {
                          e.stopPropagation();
                          setExpandedDataset(expandedDataset === ds.dataset_name ? null : ds.dataset_name);
                        }}
                      >
                        {expandedDataset === ds.dataset_name ? "Hide" : "Details"}
                      </span>
                    </div>
                    {expandedDataset === ds.dataset_name && (
                      <div className="px-11 pb-3">
                        <DatasetColumns columns={ds.column_definitions} />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {suggestedAims.length > 0 && (
              <div className="mt-3 rounded-xl border-2 border-border bg-surface-1 p-3">
                <div className="flex items-center gap-1.5 text-[10.5px] font-semibold tracking-wider uppercase text-muted mb-2">
                  <IconTarget size={12} />
                  Suggested Aims
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {suggestedAims.filter((sa) => !selectedAims.some((a) => a.aim === sa.aim)).map((sa, i) => {
                    const multi = (sa.datasets?.length || 0) > 1;
                    return (
                      <button
                        key={i}
                        type="button"
                        className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${
                          multi
                            ? "bg-ic-violet-soft/40 text-ic-violet border-ic-violet/30 hover:bg-ic-violet-soft/60"
                            : "bg-stage-planner-soft/40 text-stage-planner border-stage-planner-line/30 hover:bg-stage-planner-soft/60"
                        }`}
                        onClick={() => setPreviewAim(sa)}
                      >
                        {sa.aim}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto min-h-0 pr-1">
        {turns.length === 0 && !pendingTurn ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-6">
            <span className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-ic-violet-soft text-ic-violet mb-4">
              <IconDatabase size={22} />
            </span>
            <h3 className="text-base font-semibold text-text mb-1">
              {selectedDatasets.length > 0 ? "Ask about your data" : "Select a dataset to begin"}
            </h3>
            <p className="text-sm text-muted max-w-sm">
              {selectedDatasets.length > 0
                ? `Ask questions about ${selectedDatasets.map((d) => d.dataset_name).join(", ")}`
                : "Search and select datasets above to start exploring your data."}
            </p>
            {selectedDatasets.length > 0 && suggestedAims.length > 0 && (
              <p className="text-xs text-tertiary mt-2">Or click a suggested aim above</p>
            )}
          </div>
        ) : (
          <>
            {turns.map((t) => (
              <TurnBubble
                key={t.created_at}
                turn={t}
                queryResult={queryResults[t.created_at]}
              />
            ))}
            {pendingTurn && (
              <div className="mb-4">
                <div className="flex items-start gap-2 mb-2">
                  <span className="inline-flex items-center justify-center w-[26px] h-[26px] rounded-lg bg-ic-blue-soft text-ic-blue shrink-0 mt-0.5">
                    <IconUser size={13} />
                  </span>
                  <div className="rounded-xl border-2 border-user-blue-line border-l-3 border-l-user-blue bg-surface-1 p-3 flex-1 text-sm">
                    {pendingTurn.user}
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {loading && (
          <div className="flex items-center gap-2 text-sm text-muted py-3">
            <span className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
            Thinking...
          </div>
        )}
      </div>

      {storeAttached.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2 shrink-0">
          {storeAttached.map((ds) => (
            <span
              key={ds}
              className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-1 rounded-full border ${datasetColor(ds)}`}
            >
              <IconDatabase size={11} />
              {ds}
              <button
                type="button"
                className={`transition-colors shrink-0 ${lockedByAims.includes(ds) ? "text-muted/40 cursor-not-allowed" : "hover:text-text"}`}
                disabled={lockedByAims.includes(ds)}
                onClick={() => storeDetach(ds)}
                title={lockedByAims.includes(ds) ? "Locked by a selected aim — remove the aim first" : undefined}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      <AimBar
        selectedAims={selectedAims}
        aimResults={aimResults}
        runningAim={runningAim}
        onRunSql={handleRunAimSql}
        onViewResult={setViewingResult}
        onRemove={removeAim}
        onPreview={setPreviewAim}
      />

      <div className="shrink-0 mt-3">
        <div className="flex gap-2 items-end">
          <textarea
            ref={composerRef}
            className="flex-1 rounded-xl border-2 border-border bg-surface-1 text-text text-sm px-3 py-2.5 resize-none overflow-y-auto focus:outline-none focus:border-accent transition-colors min-h-[42px] max-h-[120px]"
            placeholder="Ask about your data..."
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button
            type="button"
            className={btnPrimary + " shrink-0"}
            onClick={() => handleSend()}
            disabled={(!input.trim() && selectedAims.length === 0) || !sessionId || loading}
          >
            Send
          </button>
        </div>
      </div>

      {previewAim && (
        <PreviewModal
          aim={previewAim}
          datasetLookup={datasetLookup}
          expandedDataset={expandedDataset}
          onToggleDataset={setExpandedDataset}
          onUseAim={() => useAim(previewAim)}
          onClose={closePreview}
          isAlreadyAdded={selectedAims.some((a) => a.aim === previewAim.aim)}
        />
      )}

      {viewingResult && (
        <ViewingResultModal
          state={viewingResult}
          onClose={() => setViewingResult(null)}
        />
      )}
    </section>
  );
}
