import { useState, useEffect, useMemo, useRef, useCallback, KeyboardEvent } from "react";
import { panelClass, btnPrimary, btnGlass } from "../lib/styles";
import { useSessionStore } from "../stores/sessionStore";
import { useOutputStore } from "../stores/outputStore";
import { listDatasets, listUserDatasets, updateSessionState, summarizeContext, uploadCsvFiles, ApiError, MAX_UPLOAD_BYTES } from "../api/client";
import type { UploadedFileDraft, UploadFailure } from "../types";
import { useDatasetStore } from "../stores/datasetStore";
import { useUploadStore } from "../stores/uploadStore";
import { useAuthStore } from "../stores/authStore";
import { useT, tCount } from "../lib/i18n";
import { newId } from "../lib/id";
import { IconDatabase, IconCheck, IconUser, IconTarget, IconUpload } from "../lib/icons";
import { QueryResultState } from "./QueryActions";
import type { Turn } from "../types/manager";
import { DatasetColumns } from "../components/DatasetColumns";
import { TurnBubble } from "../components/TurnBubble";
import ProcessingPanel from "../components/ProcessingPanel";
import { AimBar } from "../components/AimBar";
import { PreviewModal } from "../components/PreviewModal";
import { ViewingResultModal } from "../components/ViewingResultModal";
import { datasetColor } from "../lib/datasetColors";
import type { DatasetInfo } from "../types";

interface Aim {
  aim: string;
  description?: string;
  benefits?: string;
  datasets?: string[];
  columns?: { dataset: string; names: string[] }[];
}

export default function ChatSection() {
  const t = useT();
  const userId = useAuthStore((s) => s.userId);
  const sessionId = useSessionStore((s) => s.sessionId);
  const turns = useSessionStore((s) => s.turns);
  const loading = useSessionStore((s) => s.loading);
  const pendingTurn = useSessionStore((s) => s.pendingTurn);
  const sendUserMessage = useSessionStore((s) => s.sendUserMessage);
  const aimProposals = useSessionStore((s) => s.aimProposals);
  const chatQueryResults = useSessionStore((s) => s.chatQueryResults);
  const enrichmentMode = useSessionStore((s) => s.enrichmentMode);
  const contextSummaries = useSessionStore((s) => s.contextSummaries);
  const progressSteps = useSessionStore((s) => s.progressSteps);
  const sessionError = useSessionStore((s) => s.error);

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
  const selectedAims = useSessionStore((s) => s.selectedAims);
  const [expandedDataset, setExpandedDataset] = useState<string | null>(null);
  const [showSearch, setShowSearch] = useState(true);
  const [queryResults, setQueryResults] = useState<Record<string, QueryResultState>>({});
  const csvInputRef = useRef<HTMLInputElement>(null);
  const openClarify = useUploadStore((s) => s.openClarify);
  const setUploadProcessing = useUploadStore((s) => s.setProcessing);
  const uploadingCsv = useUploadStore((s) => s.isProcessing);
  const personalDatasetsVersion = useUploadStore((s) => s.personalDatasetsVersion);
  const [aimResults, setAimResults] = useState<Record<string, QueryResultState>>({});
  const [runningAim, setRunningAim] = useState<string | null>(null);
  const [missingDatasets, setMissingDatasets] = useState<string[]>([]);
  const [viewingResult, setViewingResult] = useState<{ aim: string; description?: string; datasets?: string[]; result: QueryResultState } | null>(null);
  const viewingResultRef = useRef(viewingResult);
  viewingResultRef.current = viewingResult;
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const [summarizingTags, setSummarizingTags] = useState<Set<string>>(new Set());
  const summaryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const scrollToBottom = useCallback(() => {
    const container = chatScrollRef.current;
    if (!container) return;
    requestAnimationFrame(() => {
      container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
    });
  }, []);

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
    const uid = useAuthStore.getState().userId || undefined;
    Promise.all([
      listDatasets(),
      listUserDatasets(uid),
    ]).then(([globalDs, personalRes]) => {
      const personalDs: DatasetInfo[] = (personalRes.datasets || [])
        .filter((d) => d.status === "active")
        .map((d) => ({
          dataset_name: d.dataset_name,
          line_name: d.dataset_name,
          description: d.description || `Uploaded CSV (${d.row_count} rows)`,
          table: d.table_name,
          column_definitions: d.column_definitions,
          role: null,
          join_hints: null,
          suggested_aims: null,
          synonyms: null,
        }));
      setDatasets([...globalDs, ...personalDs]);
    }).catch((err) => console.error("Failed to load datasets:", err));
  }, [personalDatasetsVersion]);

  useEffect(() => {
    if (missingDatasets.length === 0) return;
    const timer = setTimeout(() => setMissingDatasets([]), 5000);
    return () => clearTimeout(timer);
  }, [missingDatasets]);

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

  const useAim = (aim: Aim): boolean => {
    closePreview();
    const { available, missing } = filterAvailable(aim.datasets || []);
    if (missing.length > 0) {
      setMissingDatasets((prev) => [...new Set([...prev, ...missing])]);
      return false;
    }
    useSessionStore.setState((s) => ({
      selectedAims: s.selectedAims.some((a) => a.aim === aim.aim)
        ? s.selectedAims
        : [...s.selectedAims, { aim: aim.aim, description: aim.description, datasets: available }],
      aimProposals: s.aimProposals.filter((p) => p.aim.toLowerCase() !== aim.aim.toLowerCase()),
    }));
    if (available.length > 0) {
      storeAddMultiple(available);
      storeAttachMultiple(available);
    }
    composerRef.current?.focus();
    return true;
  };

  const removeAim = (aimText: string) => {
    const aim = selectedAims.find((a) => a.aim === aimText);
    if (!aim) return;
    
    useSessionStore.setState((s) => ({
      selectedAims: s.selectedAims.filter((a) => a.aim !== aimText),
    }));
    // Datasets stay attached — user can manually detach them if no other aim uses them
  };

  const handleToggleAction = async (action: { name: string; description: string; datasets?: string[] }) => {
    if (selectedAims.find((a) => a.aim === action.name)) {
      removeAim(action.name);
    } else {
      const ok = useAim({ aim: action.name, description: action.description, datasets: action.datasets });
      if (!ok) return;
      const msg = `Run analysis: ${action.description || action.name}`;
      const lineName = useDatasetStore.getState().attached.join(",");
      const res = await sendUserMessage(msg, lineName, [action.name], enrichmentMode, "focus", { [action.name]: action.description });
      if (res?.result_uuid && res?.query_result) {
        const resultState: QueryResultState = { loading: false, ...res.query_result } as QueryResultState;
        setQueryResults((prev) => ({
          ...prev,
          [res.result_uuid!]: resultState,
        }));
        useOutputStore.getState().addResult({
          aim: action.name,
          description: action.description,
          datasets: action.datasets,
          result: resultState,
        });
        useSessionStore.setState((s) => ({
          completedActions: { ...s.completedActions, [action.name]: res.result_uuid! },
        }));
        persistTurns();
      }
    }
  };

  const handleRerunAim = async (aimDef: { aim: string; description?: string; datasets?: string[] }) => {
    if (!selectedAims.find((a) => a.aim === aimDef.aim)) {
      const ok = useAim({ aim: aimDef.aim, description: aimDef.description, datasets: aimDef.datasets });
      if (!ok) return;
    }
    await handleRunAimSql({ aim: aimDef.aim, description: aimDef.description, datasets: aimDef.datasets });
  };

  const triggerSummary = useCallback(async (tag: string, timestamps: string[]) => {
    if (!sessionId) return;
    const timeoutId = setTimeout(() => {
      setSummarizingTags((prev) => {
        const next = new Set(prev);
        next.delete(tag);
        return next;
      });
    }, 5000);
    setSummarizingTags((prev) => new Set(prev).add(tag));
    try {
      const res = await summarizeContext(sessionId, tag, timestamps, userId || undefined);
      clearTimeout(timeoutId);
      useSessionStore.setState((s) => {
        const existing = s.contextSummaries[tag] || [];
        if (!existing.some((e) => e.created_at === res.created_at)) {
          return { contextSummaries: { ...s.contextSummaries, [tag]: [...existing, { turn_timestamps: timestamps, summary: res.summary, created_at: res.created_at }] } };
        }
        return {};
      });
    } catch {
      clearTimeout(timeoutId);
    } finally {
      setSummarizingTags((prev) => {
        const next = new Set(prev);
        next.delete(tag);
        return next;
      });
    }
  }, [sessionId]);

  // Auto-summarize turns in groups of 5 per tag
  useEffect(() => {
    if (summaryTimerRef.current) clearTimeout(summaryTimerRef.current);
    if (!turns.length) return;

    const tagTurnCount: Record<string, string[]> = {};
    for (const t of turns) {
        for (const aim of (t.aims || [])) {
          const tag = `aim:${aim}`;
          if (!tagTurnCount[tag]) tagTurnCount[tag] = [];
          if (t.created_at) tagTurnCount[tag].push(t.created_at);
        }
        for (const ds of (t.datasets || [])) {
          const tag = `dataset:${ds}`;
          if (!tagTurnCount[tag]) tagTurnCount[tag] = [];
          if (t.created_at) tagTurnCount[tag].push(t.created_at);
        }
      }
      for (const [tag, timestamps] of Object.entries(tagTurnCount)) {
        if (timestamps.length > 0 && timestamps.length % 5 === 0 && !summarizingTags.has(tag)) {
          const existingEntries = contextSummaries[tag] || [];
          const alreadyCovered = existingEntries.some((e) =>
            timestamps.every((ts) => e.turn_timestamps.includes(ts))
          );
          if (alreadyCovered) continue;
          const group = timestamps.slice(-5);
          summaryTimerRef.current = setTimeout(() => triggerSummary(tag, group), 2000);
        }
      }
  }, [turns, enrichmentMode, contextSummaries, summarizingTags, triggerSummary]);

  const persistTurns = useCallback(() => {
    if (!sessionId) return;
    const sState = useSessionStore.getState();
    if (sState.isLocalSession) return;
    const currentTurns = sState.turns.map((t) => ({
      user: t.user,
      agent: t.agent || "",
      timestamp: t.created_at || newId(),
      result_uuid: t.result_uuid,
      aims: t.aims || [],
      datasets: t.datasets || [],
      analysis_actions: t.analysis_actions,
    }));
    const payload: Record<string, unknown> = { turns: currentTurns };
    if (sState.selectedAims.length > 0) payload.selected_aims = sState.selectedAims;
    const attached = useDatasetStore.getState().attached;
    if (attached.length > 0) payload.attached_datasets = attached;
    const outputResults = useOutputStore.getState().results;
    if (outputResults.length > 0) payload.output_results = outputResults;
    if (sState.chatQueryResults && Object.keys(sState.chatQueryResults).length > 0) payload.chat_query_results = sState.chatQueryResults;
    if (sState.completedActions && Object.keys(sState.completedActions).length > 0) payload.completed_actions = sState.completedActions;
    if (sState.enrichmentMode) payload.enrichment_mode = sState.enrichmentMode;
    if (sState.contextSummaries && Object.keys(sState.contextSummaries).length > 0) payload.context_summaries = sState.contextSummaries;
    updateSessionState(sessionId, payload, userId || undefined).catch((err) => {
      console.warn("[persistTurns] PATCH failed for session", sessionId, err?.message || err);
    });
  }, [sessionId, userId]);

  const handleRunAimSql = async (aimDef: {aim: string; description?: string; datasets?: string[]}) => {
    if (!sessionId) return;
    const { missing } = filterAvailable(aimDef.datasets || []);
    if (missing.length > 0) {
      setMissingDatasets((prev) => [...new Set([...prev, ...missing])]);
      return;
    }
    const msg = `Run analysis: ${aimDef.description || aimDef.aim}`;
    const lineName = useDatasetStore.getState().attached.join(",");
    const res = await sendUserMessage(msg, lineName, [aimDef.aim], enrichmentMode, "focus", aimDef.description ? { [aimDef.aim]: aimDef.description } : undefined);
    if (res?.result_uuid && res?.query_result) {
      const resultState: QueryResultState = { loading: false, ...res.query_result } as QueryResultState;
      useOutputStore.getState().addResult({
        aim: aimDef.aim,
        description: aimDef.description,
        datasets: aimDef.datasets,
        result: resultState,
      });
      useSessionStore.setState((s) => ({
        completedActions: { ...s.completedActions, [aimDef.aim]: res.result_uuid! },
      }));
      persistTurns();
    } else if (res?.deep_iterations?.length) {
      // DEEP route: multiple refinement steps for this one aim — add each as its own card.
      let lastUuid: string | undefined;
      for (const it of res.deep_iterations) {
        if (!it.result_uuid) continue;
        const resultState: QueryResultState = {
          loading: false,
          sql: it.sql,
          columns: it.columns,
          column_types: it.column_types,
          rows: it.rows,
          row_count: it.row_count,
          chart_suggestions: it.chart_suggestions ?? null,
        } as QueryResultState;
        useOutputStore.getState().addResult({
          aim: aimDef.aim,
          description: aimDef.description,
          datasets: aimDef.datasets,
          result: resultState,
        });
        lastUuid = it.result_uuid;
      }
      if (lastUuid) {
        useSessionStore.setState((s) => ({
          completedActions: { ...s.completedActions, [aimDef.aim]: lastUuid! },
        }));
      }
      persistTurns();
    }
  };

  const handleScrollToTurn = useCallback((turnId: string) => {
    const el = document.querySelector(`[data-turn-id="${turnId}"]`);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.add("ring-2", "ring-emerald-400", "ring-offset-2", "rounded-xl");
    setTimeout(() => {
      el.classList.remove("ring-2", "ring-emerald-400", "ring-offset-2", "rounded-xl");
    }, 1500);
  }, []);

  // Restore persisted results on session change
  useEffect(() => {
    if (sessionId) {
      setQueryResults(chatQueryResults);
    }
  }, [sessionId]);

  // Attach datasets for selected aims when session loads
  useEffect(() => {
    if (sessionId) {
      const allDs = selectedAims.flatMap((a) => a.datasets || []);
      const { available } = filterAvailable(allDs);
      if (available.length > 0) {
        storeAddMultiple(available);
        storeAttachMultiple(available);
      }
    }
  }, [sessionId, datasetLookup]);

  // Auto-scroll to bottom when new turns arrive or pendingTurn changes
  useEffect(() => {
    scrollToBottom();
  }, [turns.length, pendingTurn, scrollToBottom]);

  // Persist selectedAims to backend whenever it changes
  const isLocalSession = useSessionStore((s) => s.isLocalSession);
  useEffect(() => {
    if (!sessionId || isLocalSession) return;
    updateSessionState(sessionId, { selected_aims: selectedAims }, userId || undefined).catch((err) => console.error("Failed to persist selected aims:", err));
  }, [selectedAims, sessionId, userId, isLocalSession]);

  const handleSend = async () => {
    const msg = input.trim() || (selectedAims.length > 0 ? selectedAims.map((a) => a.description ? `${a.aim}: ${a.description}` : a.aim).join("\n") : "");
    if (!msg || !sessionId) return;
    const sentInput = input;
    setInput("");
    setShowSearch(false);
    const { available, missing } = filterAvailable(storeAttached);
    if (missing.length > 0) setMissingDatasets((prev) => [...new Set([...prev, ...missing])]);
    const lineName = available.join(",");
    const aimNames = selectedAims.map((a) => a.aim);
    const aimDescriptions = Object.fromEntries(selectedAims.filter((a) => a.description).map((a) => [a.aim, a.description!]));
    try {
      const res = await sendUserMessage(msg, lineName, aimNames, enrichmentMode, undefined, aimDescriptions);
    if (res?.result_uuid && res?.query_result) {
      const resultState: QueryResultState = { loading: false, ...res.query_result } as QueryResultState;
      setQueryResults((prev) => ({
        ...prev,
        [res.result_uuid!]: resultState,
      }));
      // Push single-aim FOCUS results to output panel
      if (aimNames.length > 0) {
        useOutputStore.getState().addResult({
          aim: aimNames[0],
          description: selectedAims.find((a) => a.aim === aimNames[0])?.description,
          datasets: selectedAims.find((a) => a.aim === aimNames[0])?.datasets,
          result: resultState,
        });
        useSessionStore.setState((s) => ({
          completedActions: { ...s.completedActions, [aimNames[0]]: res.result_uuid! },
        }));
        persistTurns();
      }
    } else if (res?.deep_iterations?.length) {
      // Multi-aim FOCUS: one result per attached aim — add each as its own Output panel card.
      const newCompleted: Record<string, string> = {};
      for (const it of res.deep_iterations) {
        if (!it.result_uuid) continue;
        const resultState: QueryResultState = {
          loading: false,
          sql: it.sql,
          columns: it.columns,
          column_types: it.column_types,
          rows: it.rows,
          row_count: it.row_count,
          chart_suggestions: it.chart_suggestions ?? null,
        } as QueryResultState;
        const aimEntry = it.aim ? selectedAims.find((a) => a.aim === it.aim) : undefined;
        useOutputStore.getState().addResult({
          aim: it.aim || `Analysis ${it.iteration + 1}`,
          description: aimEntry?.description,
          datasets: aimEntry?.datasets,
          result: resultState,
        });
        if (it.aim) newCompleted[it.aim] = it.result_uuid;
      }
      if (Object.keys(newCompleted).length > 0) {
        useSessionStore.setState((s) => ({
          completedActions: { ...s.completedActions, ...newCompleted },
        }));
      }
      persistTurns();
    }
    } catch {
      setInput(sentInput);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && (input.trim() || selectedAims.length > 0)) {
      e.preventDefault();
      handleSend();
    }
  };

  useEffect(() => {
    let prevResults = useOutputStore.getState().results;
    const unsub = useOutputStore.subscribe((state) => {
      if (state.results === prevResults) return;
      prevResults = state.results;
      const map: Record<string, QueryResultState> = {};
      for (const r of state.results) {
        map[r.aim] = r.result;
      }
      setAimResults(map);
    });
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

  const handleCsvFilesSelected = async (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    const files = Array.from(fileList);
    const allDrafts: UploadedFileDraft[] = [];
    const allFailures: UploadFailure[] = [];

    const isTooLargeError = (e: unknown) => {
      if (e instanceof ApiError && e.status === 413) return true;
      const msg = e instanceof Error ? e.message : String(e);
      return /413|request entity too large/i.test(msg);
    };

    setUploadProcessing(
      true,
      files.length === 1
        ? t("chat.processingFile", { filename: files[0].name })
        : t("chat.uploadingProgress", { current: 1, total: files.length, filename: files[0].name }),
    );

    try {
      const uid = useAuthStore.getState().userId || undefined;
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        setUploadProcessing(
          true,
          t("chat.uploadingProgress", { current: i + 1, total: files.length, filename: file.name }),
        );

        if (file.size > MAX_UPLOAD_BYTES) {
          allFailures.push({ filename: file.name, errors: [t("chat.uploadTooLarge")] });
          continue;
        }

        try {
          const res = await uploadCsvFiles([file], uid);
          allDrafts.push(...res.files);
          allFailures.push(...res.failures);
        } catch (e) {
          console.error("CSV upload failed:", file.name, e);
          const errMsg = isTooLargeError(e)
            ? t("chat.uploadTooLarge")
            : e instanceof ApiError && e.status
              ? t("clarify.uploadFailed")
              : e instanceof Error && !e.message.includes("<")
                ? e.message
                : t("clarify.uploadFailed");
          allFailures.push({ filename: file.name, errors: [errMsg] });
        }
      }
      openClarify(allDrafts, allFailures);
    } finally {
      setUploadProcessing(false);
      if (csvInputRef.current) csvInputRef.current.value = "";
    }
  };

  return (
    <section className={`${panelClass} order-2 lg:order-none`}>
      <div className="rounded-xl border-2 border-border bg-surface-1 p-3 mb-4" data-tour="dataset-section">
        <div className="flex items-center gap-2 mb-2">
          <button
            type="button"
            className="flex items-center gap-2 flex-1 text-sm text-left"
            onClick={() => setShowSearch(!showSearch)}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="14" height="14" strokeWidth="2.2" className={`transition-transform ${showSearch ? 'rotate-90' : ''}`}>
              <path d="M9 18l6-6-6-6" />
            </svg>
            <span className="text-muted text-[11px] font-semibold tracking-wider uppercase">{t("chat.searchDatasets")}</span>
            {!showSearch && storeAttached.length > 0 && (
              <span className="text-[11px] text-muted">{t("chat.attachedCount", { count: storeAttached.length })}</span>
            )}
          </button>
          <button
            type="button"
            data-tour="upload-csv"
            className={`flex items-center gap-1.5 text-[11px] font-semibold text-accent rounded-lg px-2.5 py-1.5 shrink-0 ${btnGlass}`}
            onClick={() => csvInputRef.current?.click()}
            disabled={uploadingCsv}
          >
            <IconUpload size={13} />
            {uploadingCsv ? t("chat.uploading") : t("chat.uploadCsv")}
          </button>
          <input
            ref={csvInputRef}
            type="file"
            accept=".csv"
            multiple
            className="hidden"
            onChange={(e) => handleCsvFilesSelected(e.target.files)}
          />
        </div>

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
                placeholder={t("chat.searchPlaceholder")}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            {searchQuery && (
              <div className="mt-2 rounded-xl border-2 border-border bg-surface-1 max-h-[240px] overflow-y-auto">
                {filtered.length === 0 && (
                  <div className="px-3 py-4 text-sm text-muted text-center">{t("chat.noDatasetsFound")}</div>
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
                        {Array.isArray(ds.suggested_aims) && ds.suggested_aims.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {ds.suggested_aims.map((a, ai) => {
                              const aimText = typeof a === "string" ? a : a?.aim || "";
                              const aimDesc = typeof a === "string" ? undefined : a?.description;
                              return (
                                <button
                                  key={ai}
                                  type="button"
                                  className="inline-flex items-center gap-1 rounded-md bg-accent/10 border border-accent/20 text-accent text-[10px] px-1.5 py-0.5 truncate max-w-full hover:bg-accent/20 transition-colors"
                                  title={aimText}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    useAim({ aim: aimText, description: aimDesc, datasets: [ds.dataset_name] });
                                  }}
                                >
                                  <IconTarget size={9} />
                                  {aimText}
                                </button>
                              );
                            })}
                          </div>
                        )}
                      </div>
                      <span className="text-[11px] text-muted shrink-0 whitespace-nowrap">{ds.column_definitions.length} {t("chat.colsSuffix")}</span>
                      <span
                        className="text-[11px] font-medium text-accent hover:text-accent/80 transition-colors shrink-0 ml-1 cursor-pointer"
                        onClick={(e) => {
                          e.stopPropagation();
                          setExpandedDataset(expandedDataset === ds.dataset_name ? null : ds.dataset_name);
                        }}
                      >
                        {expandedDataset === ds.dataset_name ? t("common.hide") : t("common.details")}
                      </span>
                    </div>
                    {expandedDataset === ds.dataset_name && (
                      <div className="px-11 pb-3">
                        <DatasetColumns columns={ds.column_definitions} />
                        {Array.isArray(ds.suggested_aims) && ds.suggested_aims.length > 0 && (
                          <div className="mt-2">
                            <div className="text-[10.5px] font-semibold tracking-wider uppercase text-muted mb-1">
                              {t("chat.suggestedAims")}
                            </div>
                            <div className="flex flex-wrap gap-1">
                              {ds.suggested_aims.map((a, ai) => {
                                const aimText = typeof a === "string" ? a : a?.aim || "";
                                const aimDesc = typeof a === "string" ? undefined : a?.description;
                                return (
                                  <button
                                    key={ai}
                                    type="button"
                                    className="inline-flex items-center gap-1 rounded-md bg-accent/10 border border-accent/20 text-accent text-[10px] px-1.5 py-0.5 hover:bg-accent/20 transition-colors"
                                    title={aimText}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      useAim({ aim: aimText, description: aimDesc, datasets: [ds.dataset_name] });
                                    }}
                                  >
                                    <IconTarget size={9} />
                                    {aimText}
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        )}
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
                  {t("chat.suggestedAims")}
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

      <div ref={chatScrollRef} className="flex-1 overflow-y-auto min-h-0 pr-1">
        {turns.length === 0 && !pendingTurn ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-6">
            <span className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-ic-violet-soft text-ic-violet mb-4">
              <IconDatabase size={22} />
            </span>
            <h3 className="text-base font-semibold text-text mb-1">
              {selectedDatasets.length > 0 ? t("chat.askAboutData") : t("chat.selectDatasetToBegin")}
            </h3>
            <p className="text-sm text-muted max-w-sm">
              {selectedDatasets.length > 0
                ? t("chat.askQuestionsAbout", { datasets: selectedDatasets.map((d) => d.dataset_name).join(", ") })
                : t("chat.searchAndSelect")}
            </p>
            {selectedDatasets.length > 0 && suggestedAims.length > 0 && (
              <p className="text-xs text-tertiary mt-2">{t("chat.orClickSuggested")}</p>
            )}
          </div>
        ) : (
          <>
            {turns.map((t) => (
              <TurnBubble
                key={t.created_at}
                turn={t}
                queryResult={queryResults[t.result_uuid ?? ""] || queryResults[t.created_at ?? ""]}
                selectedAims={selectedAims}
                runningAim={runningAim}
                loading={loading}
                onToggleAction={handleToggleAction}
                onScrollToTurn={handleScrollToTurn}
                onRerunAim={handleRerunAim}
                datasets={datasets}
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
          <div className="border-t border-border/30 mt-1">
            <ProcessingPanel steps={progressSteps} />
          </div>
        )}
        {summarizingTags.size > 0 && (
          <div className="flex items-center gap-2 text-sm text-muted py-1 border-t border-border/30 mt-1">
            <span className="w-2 h-2 rounded-full bg-ic-teal animate-pulse" />
            {summarizingTags.size > 1 ? t("chat.summarizingGroups", { count: summarizingTags.size }) : t("chat.summarizing")}
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
                className={`transition-colors shrink-0 ${lockedByAims.includes(ds) || loading ? "text-muted/40 cursor-not-allowed" : "hover:text-text"}`}
                disabled={lockedByAims.includes(ds) || loading}
                onClick={() => storeDetach(ds)}
                title={lockedByAims.includes(ds) ? t("common.lockedByAim") : loading ? t("common.processingWait") : undefined}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {sessionError && (
        <div className="text-[11px] text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2 mb-2">
          {sessionError}
        </div>
      )}

      {missingDatasets.length > 0 && (
        <div className="text-[11px] text-amber-400 bg-amber-400/10 border border-amber-400/20 rounded-lg px-3 py-2 mb-2">
          {t("chat.datasetsNotAvailable", { names: missingDatasets.join(", ") })}
        </div>
      )}

      <AimBar
        selectedAims={selectedAims}
        aimResults={aimResults}
        runningAim={runningAim}
        loading={loading}
        onRunSql={handleRunAimSql}
        onRerun={handleRerunAim}
        onViewResult={setViewingResult}
        onRemove={removeAim}
        onPreview={setPreviewAim}
      />

      <div className="shrink-0 mt-3 space-y-2">
        {/* Composer */}
        <div className="flex gap-2 items-end">
          <textarea
            ref={composerRef}
            data-tour="composer"
            className="flex-1 rounded-xl border-2 border-border bg-surface-1 text-text text-sm px-3 py-2.5 resize-none overflow-y-auto focus:outline-none focus:border-accent transition-colors min-h-[42px] max-h-[120px]"
            placeholder={t("chat.composerResearchPlaceholder")}
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
            {t("common.send")}
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
