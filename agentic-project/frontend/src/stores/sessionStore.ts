import { create } from "zustand";
import * as api from "../api/client";
import { generateSessionName } from "../lib/names";
import { newId } from "../lib/id";
import type { MessageResponse, SchemaSnapshot, SessionListItem, SessionMeta, Turn, TurnUi } from "../types/manager";
import { useUiStore } from "./uiStore";
import { useOutputStore, type CollectedResult } from "./outputStore";
import { useDatasetStore } from "./datasetStore";
import { useAuthStore } from "./authStore";
import { useToastStore } from "./toastStore";
import { t } from "../lib/i18n";
import type { QueryResultState } from "../sections/QueryActions";

function turnFromResponse(res: MessageResponse, userMessage: string, attachedAims?: string[], attachedDatasets?: string[]): Turn {
  return {
    turn_index: res.turn_index ?? 0,
    user: userMessage,
    agent: res.agent_message || "",
    ui: res.ui || null,
    schema: res.schema || null,
    created_at: new Date().toISOString(),
    result_uuid: res.result_uuid || undefined,
    aims: attachedAims?.length ? attachedAims : undefined,
    datasets: attachedDatasets?.length ? attachedDatasets : undefined,
    description: res.description || null,
    benefits: res.benefits || null,
    columns: res.columns || null,
    analysis_actions: res.analysis_actions || undefined,
    deep_iterations: res.deep_iterations || undefined,
    truncated: res.truncated || false,
    stopped_reason: res.stopped_reason || "",
    query_results: res.query_results ? res.query_results.map((qr: any) => ({ loading: false, ...qr })) : undefined,
  };
}

function reconstructTemplateCards(rawTurns: any[], existing: CollectedResult[]): CollectedResult[] {
  // Rebuild an OutputPanel card for any stored template turn that doesn't already have one.
  // Cards are normally created by ChatSection.handleSend (browser-only) and persisted as
  // session_state.output_results; template runs done before that path existed — or before the
  // route===template branch was ordered first — left no card, so we synthesize it from the turn.
  const results = [...existing];
  const byName = new Map<string, number>();
  const seen = new Set<string>();
  for (const r of existing) {
    if (r.kind !== "template") continue;
    const name = r.template_name || "Report";
    byName.set(name, (byName.get(name) || 0) + 1);
    seen.add(`${name}|${r.aim}`);
  }
  for (const t of rawTurns) {
    const isTemplate = t?.route === "template" || Boolean(t?.template_name && String(t.template_name).trim());
    if (!isTemplate) continue;
    const templateName = (t?.template_name && String(t.template_name).trim()) || "Report";
    const prior = byName.get(templateName) || 0;
    const runNumber = prior + 1;
    byName.set(templateName, runNumber);
    const runLabel = `${String(runNumber).padStart(2, "0")} · ${templateName}`;
    if (seen.has(`${templateName}|${runLabel}`)) continue;
    seen.add(`${templateName}|${runLabel}`);
    const resultState: QueryResultState = { loading: false, ...(t.query_result || {}) } as QueryResultState;
    const queryResults: QueryResultState[] | undefined = Array.isArray(t.query_results)
      ? t.query_results.map((qr: any) => ({ loading: false, ...qr }))
      : undefined;
    results.push({
      id: newId(),
      aim: runLabel,
      description: templateName,
      datasets: Array.isArray(t.datasets) ? t.datasets : undefined,
      result: resultState,
      created_at: Date.now(),
      kind: "template",
      template_name: templateName,
      report: t.agent || "",
      queryResults,
    });
  }
  return results;
}

function reconstructAimCards(rawTurns: any[], existing: CollectedResult[]): CollectedResult[] {
  const results = [...existing];
  const seen = new Set<string>(existing.map((r) => r.aim));
  for (const t of rawTurns) {
    const isTemplate = t?.route === "template" || Boolean(t?.template_name && String(t.template_name).trim());
    if (isTemplate) continue;
    if (!t?.result_uuid || !t?.query_result) continue;
    const firstAction = Array.isArray(t.analysis_actions) ? t.analysis_actions[0] : undefined;
    const aimLabel = firstAction?.name || (typeof t.user === "string" ? t.user.slice(0, 60) : "");
    if (!aimLabel || seen.has(aimLabel)) continue;
    seen.add(aimLabel);
    const desc = firstAction?.description || undefined;
    const ds = Array.isArray(firstAction?.datasets) ? firstAction.datasets : Array.isArray(t.datasets) ? t.datasets : undefined;
    const resultState: QueryResultState = { loading: false, ...(t.query_result || {}) } as QueryResultState;
    results.push({
      id: newId(),
      aim: aimLabel,
      description: desc,
      datasets: ds,
      result: resultState,
      created_at: Date.now(),
    });
  }
  return results;
}

let _pollTimer: ReturnType<typeof setInterval> | null = null;

/** If the client aborts the send (REQUEST_TIMEOUT_MS), the backend keeps processing and
 * eventually persists the completed turn. Poll the session until that turn appears, then
 * reconstruct a MessageResponse so the normal rendering path can show the result instead
 * of surfacing a spurious timeout error. */
async function pollForCompletedTurn(
  sessionId: string,
  userId: string | undefined,
  sentAt: number,
  userText: string,
): Promise<MessageResponse> {
  const deadline = Date.now() + 10 * 60 * 1000; // up to 10 extra minutes
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 2000));
    try {
      const detail = await api.getSession(sessionId, userId);
      const turns = detail?.turns || [];
      const match = [...turns]
        .reverse()
        .find(
          (t: any) =>
            t.user === userText &&
            new Date(t.timestamp || t.created_at || 0).getTime() >= sentAt &&
            Boolean(t.agent)
        );
      if (match) {
        const qResults: QueryResultState[] | undefined = Array.isArray(match.query_results)
          ? match.query_results.map((qr: any) => ({ loading: false, ...qr }))
          : undefined;
        return {
          session_id: sessionId,
          turn_index: 0,
          agent_message: match.agent || "",
          route: match.route || "template",
          phase: match.phase || "chat",
          status: match.status || "active",
          done: true,
          result_uuid: match.result_uuid || undefined,
          query_result: (qResults?.length ? qResults[qResults.length - 1] : undefined) as any,
          query_results: qResults,
          truncated: Boolean(match.truncated),
          stopped_reason: match.stopped_reason || "",
          aim_proposals: [],
          analysis_actions: match.analysis_actions || undefined,
          deep_iterations: [],
        } as MessageResponse;
      }
    } catch {
      // keep polling
    }
  }
  throw new api.ApiError("The report is still being generated on the server. Please refresh in a moment.", 0);
}

function getErrorMessage(e: unknown): string {
  if (e instanceof Error) return e.message;
  if (typeof e === "object" && e !== null) {
    const obj = e as Record<string, unknown>;
    if (typeof obj.detail === "string") return obj.detail;
  }
  return t("session.requestFailed");
}

interface PendingTurn {
  user: string;
  agent: string | null;
  ui: TurnUi | null;
  schema: SchemaSnapshot | null;
  loading: boolean;
}

export interface ProcessingStep {
  step: string;
  status: string;
  detail: string;
  ts: number;
}

interface SessionState {
  sessionId: string | null;
  isLocalSession: boolean;
  pendingTitle: string | null;
  sessions: SessionListItem[];
  turns: Turn[];
  sessionMeta: SessionMeta | null;
  loading: boolean;
  progressSteps: ProcessingStep[];
  statusMessage: string | null;
  error: string | null;
  pendingTurn: PendingTurn | null;
  aimProposals: { aim: string; description: string; datasets: string[]; goal?: string; columns?: string[]; insight?: string }[];
  selectedAims: { aim: string; description?: string; datasets?: string[] }[];
  outputResults: CollectedResult[];
  chatQueryResults: Record<string, QueryResultState>;
  completedActions: Record<string, string>;
  contextSummaries: Record<string, { turn_timestamps: string[]; summary: string; created_at: string }[]>;
  enrichmentMode: string;
  clearAll: () => void;
  bootstrap: () => Promise<void>;
  refreshSessions: (userId?: string) => Promise<SessionListItem[]>;
  switchSession: (id: string) => Promise<void>;
  newSession: () => void;
  deleteSession: (id: string) => Promise<void>;
  sendUserMessage: (text: string, lineName?: string, attachedAims?: string[], enrichmentMode?: string, routeOverride?: string, aimDescriptions?: Record<string, string>, formatSpec?: string, templateName?: string) => Promise<MessageResponse | undefined>;
  setError: (error: string | null) => void;
  setStatusMessage: (msg: string | null) => void;
  setPendingTurn: (user: string) => void;
  updatePendingSchema: (update: Partial<SchemaSnapshot>) => void;
  updatePendingUi: (update: Partial<TurnUi>) => void;
  clearPendingTurn: () => void;
  updateSessionTitle: (sessionId: string, title: string) => Promise<void>;
  setPendingTitle: (title: string) => void;
  setEnrichmentMode: (mode: string) => void;
  setOutputResults: (results: CollectedResult[]) => void;
  updateOutputResults: (results: CollectedResult[]) => Promise<void>;
  updateChatQueryResults: (results: Record<string, QueryResultState>) => Promise<void>;
  startPoller: () => void;
  stopPoller: () => void;
}

export const useSessionStore = create<SessionState>((set, get) => ({
  sessionId: null,
  isLocalSession: false,
  pendingTitle: null,
  sessions: [],
  turns: [],
  sessionMeta: null,
  loading: false,
  progressSteps: [],
  statusMessage: null,
  error: null,
  pendingTurn: null,
  aimProposals: [],
  selectedAims: [],
  outputResults: [],
  chatQueryResults: {},
  completedActions: {},
  contextSummaries: {},
  enrichmentMode: "research",

  clearAll: () => {
    if (_pollTimer) clearInterval(_pollTimer);
    _pollTimer = null;
    set({
      sessionId: null,
      isLocalSession: false,
      pendingTitle: null,
      sessions: [],
      turns: [],
      sessionMeta: null,
      loading: false,
      progressSteps: [],
      statusMessage: null,
      error: null,
      pendingTurn: null,
      aimProposals: [],
      selectedAims: [],
      outputResults: [],
      chatQueryResults: {},
      completedActions: {},
      contextSummaries: {},
      enrichmentMode: "research",
    });
    useUiStore.getState().selectTurn(-1);
  },

  refreshSessions: async (userId?: string) => {
    const list = await api.listSessions(userId);
    const withMode = list.map((s) => ({ ...s, mode: s.mode || "ask" }));
    set({ sessions: withMode });
    return withMode;
  },

  bootstrap: async () => {
    _bootstrapEpoch++;
    const epoch = _bootstrapEpoch;
    set({ error: null, loading: true });
    try {
      const uid = useAuthStore.getState().userId || undefined;
      const list = await get().refreshSessions(uid);
      if (epoch !== _bootstrapEpoch) return;
      if (list.length > 0) {
        const detail = await api.getSession(list[0].session_id, uid);
        if (epoch !== _bootstrapEpoch) return;
        const sessionMeta = { session_id: detail.session_id, title: detail.title, phase: detail.phase || "lines", status: detail.status || "active", mode: detail.mode || "ask" };
        const apiTurns = detail.turns || [];
        const loadedTurns: Turn[] = apiTurns.map((t: any) => ({
          turn_index: 0,
          user: t.user,
          agent: t.agent || "",
          ui: null as any,
          schema: null as any,
          created_at: t.created_at || t.timestamp || new Date().toISOString(),
          result_uuid: t.result_uuid,
          aims: t.aims || [],
          datasets: t.datasets || [],
          description: null,
          benefits: null,
          columns: null,
          analysis_actions: t.analysis_actions || undefined,
          truncated: Boolean(t.truncated),
          stopped_reason: t.stopped_reason || "",
          template_name: t.template_name || undefined,
          route: t.route || undefined,
          query_results: Array.isArray(t.query_results) ? t.query_results.map((qr: any) => ({ loading: false, ...qr })) : undefined,
        }));
        let outputResults = reconstructTemplateCards(
          apiTurns,
          Array.isArray(detail.state?.output_results) ? detail.state.output_results : []
        );
        outputResults = reconstructAimCards(apiTurns, outputResults);
        set({
          sessionMeta,
          turns: loadedTurns,
          sessionId: detail.session_id || list[0].session_id,
          isLocalSession: false,
          aimProposals: detail.state?.aim_proposals || [],
          selectedAims: Array.isArray(detail.state?.selected_aims) ? detail.state.selected_aims : [],
          outputResults,
          chatQueryResults: detail.state?.chat_query_results || {},
          completedActions: detail.state?.completed_actions || {},
          contextSummaries: detail.state?.context_summaries || {},
          enrichmentMode: detail.state?.enrichment_mode || "research",
        });
        useUiStore.getState().selectTurn(loadedTurns.length - 1);
        useOutputStore.getState().setResults(outputResults);
        const attachedDs = detail.state?.attached_datasets;
        if (Array.isArray(attachedDs) && attachedDs.length > 0) {
          const [allDatasets, userRes] = await Promise.all([
            api.listDatasets(),
            api.listUserDatasets(uid),
          ]);
          if (epoch !== _bootstrapEpoch) return;
          const validNames = new Set(allDatasets.map((d) => d.dataset_name));
          for (const d of (userRes.datasets || [])) {
            if (d.status === "active") validNames.add(d.dataset_name);
          }
          const validDs = attachedDs.filter((d: string) => validNames.has(d));
          if (validDs.length > 0) {
            useDatasetStore.getState().addMultiple(validDs);
          }
        }
      } else {
        const tempId = newId();
        const name = generateSessionName();
        set({
          sessionId: tempId,
          isLocalSession: true,
          pendingTitle: name,
          sessionMeta: null,
          turns: [],
        });
        useUiStore.getState().selectTurn(-1);
      }
    } catch (e) {
      set({ error: getErrorMessage(e) });
    } finally {
      set({ loading: false });
    }
  },

  switchSession: async (id) => {
    const { sessionId } = get();
    if (!id || id === sessionId) return;
    _switchEpoch++;
    const epoch = _switchEpoch;
    set({ error: null, loading: true });
    try {
      const uid = useAuthStore.getState().userId || undefined;
      const detail = await api.getSession(id, uid);
      // Discard this response if a newer switchSession call has started in the
      // meantime (e.g. the user clicked another session before this one loaded) —
      // otherwise a slow response can overwrite a session that's already been
      // superseded, showing mismatched title/turns/datasets.
      if (epoch !== _switchEpoch) return;
      const sessionMeta = { session_id: detail.session_id, title: detail.title, phase: detail.phase || "lines", status: detail.status || "active", mode: (detail as any).mode || "ask" };
      const rawTurns = detail.turns || [];
      const loadedTurns = rawTurns.map((t: any) => ({
        turn_index: 0,
        user: t.user,
        agent: t.agent || "",
        ui: null as any,
        schema: null as any,
        created_at: t.created_at || t.timestamp || new Date().toISOString(),
        result_uuid: t.result_uuid,
        aims: t.aims || [],
        datasets: t.datasets || [],
        description: null,
        benefits: null,
        columns: null,
        analysis_actions: t.analysis_actions || undefined,
        truncated: Boolean(t.truncated),
        stopped_reason: t.stopped_reason || "",
        template_name: t.template_name || undefined,
        route: t.route || undefined,
        query_results: Array.isArray(t.query_results) ? t.query_results.map((qr: any) => ({ loading: false, ...qr })) : undefined,
      }));
      let outputResults = reconstructTemplateCards(
        rawTurns,
        Array.isArray(detail.state?.output_results) ? detail.state.output_results : []
      );
      outputResults = reconstructAimCards(rawTurns, outputResults);
      set({
        sessionMeta,
        turns: loadedTurns,
        sessionId: detail.session_id || id,
        isLocalSession: false,
        pendingTitle: null,
        aimProposals: detail.state?.aim_proposals || [],
        selectedAims: Array.isArray(detail.state?.selected_aims) ? detail.state.selected_aims : [],
        outputResults,
        chatQueryResults: detail.state?.chat_query_results || {},
        completedActions: detail.state?.completed_actions || {},
        contextSummaries: detail.state?.context_summaries || {},
        enrichmentMode: detail.state?.enrichment_mode || "research",
      });
      useUiStore.getState().selectTurn(loadedTurns.length - 1);
      useOutputStore.getState().setResults(outputResults);
      useDatasetStore.getState().clear();
      const attachedDs = detail.state?.attached_datasets;
      if (Array.isArray(attachedDs) && attachedDs.length > 0) {
        const [allDatasets, userRes] = await Promise.all([
          api.listDatasets(),
          api.listUserDatasets(uid),
        ]);
        if (epoch !== _switchEpoch) return;
        const validNames = new Set(allDatasets.map((d) => d.dataset_name));
        for (const d of (userRes.datasets || [])) {
          if (d.status === "active") validNames.add(d.dataset_name);
        }
        const validDs = attachedDs.filter((d: string) => validNames.has(d));
        if (validDs.length > 0) {
          useDatasetStore.getState().addMultiple(validDs);
        }
      }
    } catch (e) {
      if (epoch === _switchEpoch) set({ error: getErrorMessage(e) });
    } finally {
      if (epoch === _switchEpoch) set({ loading: false });
    }
  },

  newSession: () => {
    const tempId = newId();
    const name = generateSessionName();
    set({
      error: null,
      sessionId: tempId,
      isLocalSession: true,
      pendingTitle: name,
      sessionMeta: null,
      turns: [],
      selectedAims: [],
      completedActions: {},
      chatQueryResults: {},
      aimProposals: [],
      contextSummaries: {},
      enrichmentMode: "research",
      outputResults: [],
      pendingTurn: null,
    });
    useOutputStore.getState().clearResults();
    useDatasetStore.getState().clear();
    useUiStore.getState().selectTurn(-1);
  },

  deleteSession: async (id) => {
    const { sessionId, sessions } = get();
    const uid = useAuthStore.getState().userId || undefined;
    await api.deleteSession(id, uid);
    const remaining = sessions.filter((s) => s.session_id !== id);
    set({ sessions: remaining });
    if (id === sessionId) {
      if (remaining.length > 0) {
        await get().switchSession(remaining[0].session_id);
      } else {
        get().newSession();
      }
    }
  },

  sendUserMessage: async (text, lineName = "", attachedAims: string[] = [], enrichmentMode = "research", routeOverride?: string, aimDescriptions?: Record<string, string>, formatSpec?: string, templateName?: string) => {
    const { sessionId, turns, isLocalSession, pendingTitle, sessionMeta, loading } = get();
    const isDone = turns.length > 0 && Boolean(turns[turns.length - 1]?.ui?.done);

    if (!sessionId || !text.trim() || isDone || loading) return;

    // Track the session that will actually process this message. For the first prompt in a
    // fresh (local) session this starts as the temp id and is reassigned to the real session
    // id after createSession() — the poller must follow it, or progress steps never appear.
    let activeSessionId = sessionId;

    const userText = text.trim();
    const sendUid = useAuthStore.getState().userId || undefined;
    set({ error: null, loading: true, progressSteps: [], statusMessage: t("processing.processingLabel"), pendingTurn: null });
    get().setPendingTurn(userText);

    // Progress polling — fetches live steps from backend while message is being processed.
    // Pinned to the session that sent this message (activeSessionId), not whatever session
    // is currently displayed — otherwise switching sessions mid-send redirects the poller
    // to the new session's progress and overwrites its (unrelated) progressSteps.
    const progressTimer = setInterval(async () => {
      if (!activeSessionId || get().sessionId !== activeSessionId) return;
      try {
        const res = await api.getProgress(activeSessionId, sendUid);
        if (get().sessionId === activeSessionId) set({ progressSteps: res.steps });
      } catch { /* ignore poll errors */ }
    }, 600);

    try {

      if (isLocalSession) {
        set({ statusMessage: t("session.creating") });
        const name = pendingTitle || generateSessionName();
        const created = await api.createSession(name, sendUid);
        activeSessionId = created.session_id;
        set({
          sessionId: activeSessionId,
          isLocalSession: false,
          pendingTitle: null,
          sessionMeta: { session_id: activeSessionId, title: name, mode: "ask", status: "active", phase: "lines" },
        });
        // Persist any pre-existing selected aims and attached datasets to the new session
        const preState = get();
        const prePayload: Record<string, unknown> = {};
        if (preState.selectedAims.length > 0) prePayload.selected_aims = preState.selectedAims;
        const attached = useDatasetStore.getState().attached;
        if (attached.length > 0) prePayload.attached_datasets = attached;
        if (Object.keys(prePayload).length > 0) {
          api.updateSessionState(activeSessionId, prePayload, sendUid).catch((err) => console.error("Failed to persist pre-existing state:", err));
        }
      }

      // History built server-side from stored turns (via enrichment block + conv history)
      const language = useUiStore.getState().language;
      let res: MessageResponse;
      const sentAt = Date.now();
      try {
        res = await api.sendMessage(activeSessionId, userText, lineName, attachedAims, enrichmentMode, [], routeOverride, aimDescriptions, language, sendUid, formatSpec, templateName);
      } catch (e) {
        // Client-side abort (REQUEST_TIMEOUT_MS) while the backend is still working on a
        // long template run: don't surface a timeout error — keep polling progress and,
        // once the backend persists the turn, render the completed result normally.
        const timedOut = e instanceof api.ApiError && e.status === 0 && /timed out/i.test(e.message);
        if (!timedOut) throw e;
        res = await pollForCompletedTurn(activeSessionId, sendUid, sentAt, userText);
      }
      clearInterval(progressTimer);
      set({ statusMessage: t("session.responseReceived") });

      // If user switched sessions during loading, show toast instead of updating UI
      const currentSessionId = get().sessionId;
      if (currentSessionId !== activeSessionId) {
        const title = get().sessions.find((s) => s.session_id === activeSessionId)?.title || activeSessionId.slice(0, 8);
        useToastStore.getState().pushToast(t("session.responseToast"), activeSessionId, title);
        return res;
      }

      const datasetNames = lineName.split(",").map((d) => d.trim()).filter(Boolean);
      const newTurn = turnFromResponse(res, userText, attachedAims, datasetNames);
      _lastLocalMetaUpdate = Date.now();
      set((state) => ({
        turns: [...state.turns, newTurn],
        pendingTurn: null,
        sessionMeta: {
          ...(state.sessionMeta || { session_id: activeSessionId }),
          phase: res.phase,
          status: res.status,
        },
      }));
      // Session keeps its randomly generated name — the user renames it manually
      // (via the edit-title control in ContextSection) if they want to.
      // Store inline query result for persistence across reloads
      if (res.result_uuid && res.query_result) {
        const updatedResults = {
          ...get().chatQueryResults,
          [res.result_uuid!]: res.query_result as QueryResultState,
        };
        set({ chatQueryResults: updatedResults });
        // Persist to backend so results survive page reload
        api.updateSessionState(activeSessionId, { chat_query_results: updatedResults }, sendUid).catch((err) => console.error("Failed to persist chat query results:", err));
      }

      // Multi-step responses (DEEP route, multi-aim FOCUS) carry one result per
      // iteration instead of a single query_result — persist each into memory too,
      // so future enrichment lookups can recall the SQL/rows, not just the summary text.
      if (res.deep_iterations?.length) {
        const iterResults: Record<string, QueryResultState> = {};
        for (const it of res.deep_iterations) {
          if (it.result_uuid && it.sql) {
            iterResults[it.result_uuid] = {
              loading: false,
              sql: it.sql,
              columns: it.columns,
              column_types: it.column_types,
              rows: it.rows,
              row_count: it.row_count,
              chart_suggestions: it.chart_suggestions ?? null,
            } as QueryResultState;
          }
        }
        if (Object.keys(iterResults).length > 0) {
          const updatedResults = { ...get().chatQueryResults, ...iterResults };
          set({ chatQueryResults: updatedResults });
          api.updateSessionState(activeSessionId, { chat_query_results: updatedResults }, sendUid).catch((err) => console.error("Failed to persist deep iteration results:", err));
        }
      }

      // Replace aimProposals with latest turn's proposals
      const latestProposals = res.aim_proposals?.length
        ? res.aim_proposals
        : res.analysis_actions?.map((a) => ({ aim: a.name, description: a.description, datasets: a.datasets, goal: a.goal, columns: a.columns, insight: a.insight }));
      if (latestProposals?.length) {
        set({ aimProposals: latestProposals });
      }
      const nextIdx = useUiStore.getState().selectedTurnIndex;
      useUiStore.getState().selectTurn(nextIdx < 0 ? 0 : nextIdx + 1);
      // Clear the "Processing..." indicator the moment the response is rendered —
      // the non-critical session-list refresh must not keep it visible if it stalls.
      set({ loading: false, progressSteps: [], statusMessage: null });
      get().refreshSessions(useAuthStore.getState().userId || undefined).catch(() => {});
      return res;
    } catch (e) {
      clearInterval(progressTimer);
      if (get().sessionId === activeSessionId) {
        set({ error: getErrorMessage(e), pendingTurn: null });
      }
      throw e;
    } finally {
      clearInterval(progressTimer);
      set({ loading: false, progressSteps: [], statusMessage: null });
    }
  },

  updateSessionTitle: async (sessionId: string, title: string) => {
    try {
      await api.updateSessionTitle(sessionId, title);
      set((state) => ({
        sessionMeta: state.sessionMeta?.session_id === sessionId
          ? { ...state.sessionMeta, title: title || undefined }
          : state.sessionMeta,
        sessions: state.sessions.map((s) =>
          s.session_id === sessionId ? { ...s, title: title || undefined } : s
        ),
      }));
    } catch (e) {
      set({ error: getErrorMessage(e) });
    }
  },

  setOutputResults: (results) => {
    set({ outputResults: results });
    useOutputStore.getState().setResults(results);
  },

  updateOutputResults: async (results) => {
    try {
      const updateUid = useAuthStore.getState().userId || undefined;
      await api.updateSessionState(get().sessionId!, { output_results: results }, updateUid);
      set({ outputResults: results });
      useOutputStore.getState().setResults(results);
    } catch (e) {
      set({ error: getErrorMessage(e) });
    }
  },

  updateChatQueryResults: async (results) => {
    try {
      const updateUid = useAuthStore.getState().userId || undefined;
      await api.updateSessionState(get().sessionId!, { chat_query_results: results }, updateUid);
      set({ chatQueryResults: results });
    } catch (e) {
      set({ error: getErrorMessage(e) });
    }
  },

  setError: (error) => set({ error }),

  setStatusMessage: (msg) => set({ statusMessage: msg }),

  setPendingTitle: (title) => set({ pendingTitle: title }),

  setEnrichmentMode: (mode) => set({ enrichmentMode: mode }),

  setPendingTurn: (user) => {
    set({
      pendingTurn: { user, agent: null, ui: null, schema: null, loading: true },
    });
  },

  updatePendingSchema: (update) => {
    set((state) => {
      if (!state.pendingTurn) return state;
      return {
        pendingTurn: {
          ...state.pendingTurn,
          schema: { ...(state.pendingTurn.schema || {} as SchemaSnapshot), ...update },
        },
      };
    });
  },

  updatePendingUi: (update) => {
    set((state) => {
      if (!state.pendingTurn) return state;
      return {
        pendingTurn: {
          ...state.pendingTurn,
          ui: { ...(state.pendingTurn.ui || {} as TurnUi), ...update },
        },
      };
    });
  },

  clearPendingTurn: () => set({ pendingTurn: null }),

  startPoller: () => {
    if (_pollTimer) return;
    _pollTimer = setInterval(async () => {
      try {
        const uid = useAuthStore.getState().userId || undefined;
        const list = await api.listSessions(uid);
        const state = get();
        const current = list.find((s) => s.session_id === state.sessionId);
        // Skip merging phase/status/mode from the (lighter, possibly-lagging) list
        // endpoint if we just set them locally from a message response — otherwise
        // a poll tick landing right after can briefly revert the UI to a stale value
        // until the backend's list index catches up.
        const recentLocalUpdate = Date.now() - _lastLocalMetaUpdate < 5000;
        set({
          sessions: list,
          sessionMeta: current && !recentLocalUpdate
            ? { ...(state.sessionMeta || {}), ...current }
            : state.sessionMeta,
        });
      } catch (e) {
        console.warn("[sessionStore] poller failed", e);
      }
    }, 15000);
  },

  stopPoller: () => {
    if (_pollTimer) {
      clearInterval(_pollTimer);
      _pollTimer = null;
    }
  },
}));

// Safety net: auto-reset loading if stuck for >300s.
// Uses epoch counter so stale callbacks from previous loading cycles don't mutate state.
let _bootstrapEpoch = 0;
let _switchEpoch = 0;
let _lastLocalMetaUpdate = 0;
let _loadingTimeout: ReturnType<typeof setTimeout> | null = null;
let _loadingEpoch = 0;
useSessionStore.subscribe((state, prev) => {
  if (state.loading && !prev.loading) {
    _loadingEpoch++;
    const epoch = _loadingEpoch;
    if (_loadingTimeout) clearTimeout(_loadingTimeout);
    _loadingTimeout = setTimeout(() => {
      _loadingTimeout = null;
      if (epoch === _loadingEpoch) {
        useSessionStore.setState({ loading: false, error: t("session.timedOut") });
      }
    }, 300000);
  } else if (!state.loading && prev.loading && _loadingTimeout) {
    clearTimeout(_loadingTimeout);
    _loadingTimeout = null;
  }
});

export function useSelectedTurn(): Turn | null {
  const turns = useSessionStore((s) => s.turns);
  const selectedTurnIndex = useUiStore((s) => s.selectedTurnIndex);
  return selectedTurnIndex >= 0 ? turns[selectedTurnIndex] ?? null : null;
}

export function useIsLive(): boolean {
  const turns = useSessionStore((s) => s.turns);
  const selectedTurnIndex = useUiStore((s) => s.selectedTurnIndex);
  if (turns.length === 0) return true;
  return selectedTurnIndex === turns.length - 1;
}

export function useIsDone(): boolean {
  const turns = useSessionStore((s) => s.turns);
  if (!turns.length) return false;
  return Boolean(turns[turns.length - 1]?.ui?.done);
}
