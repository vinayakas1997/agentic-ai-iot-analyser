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
  };
}

let _pollTimer: ReturnType<typeof setInterval> | null = null;

function getErrorMessage(e: unknown): string {
  if (axiosIsError(e)) {
    const detail = e.response?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  if (e instanceof Error) return e.message;
  return "Request failed";
}

function axiosIsError(e: unknown): e is { response?: { data?: { detail?: string } } } {
  return typeof e === "object" && e !== null && "response" in e;
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
  sendUserMessage: (text: string, lineName?: string, attachedAims?: string[], enrichmentMode?: string, routeOverride?: string, aimDescriptions?: Record<string, string>) => Promise<MessageResponse | undefined>;
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
    set({ error: null, loading: true });
    try {
      const uid = useAuthStore.getState().userId || undefined;
      const list = await get().refreshSessions(uid);
      if (list.length > 0) {
        const detail = await api.getSession(list[0].session_id, uid);
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
        }));
        set({
          sessionMeta,
          turns: loadedTurns,
          sessionId: detail.session_id || list[0].session_id,
          isLocalSession: false,
          aimProposals: detail.state?.aim_proposals || [],
          selectedAims: Array.isArray(detail.state?.selected_aims) ? detail.state.selected_aims : [],
          outputResults: Array.isArray(detail.state?.output_results) ? detail.state.output_results : [],
          chatQueryResults: detail.state?.chat_query_results || {},
          completedActions: detail.state?.completed_actions || {},
          contextSummaries: detail.state?.context_summaries || {},
          enrichmentMode: detail.state?.enrichment_mode || "research",
        });
        useUiStore.getState().selectTurn(loadedTurns.length - 1);
        useOutputStore.getState().setResults(Array.isArray(detail.state?.output_results) ? detail.state.output_results : []);
        const attachedDs = detail.state?.attached_datasets;
        if (Array.isArray(attachedDs) && attachedDs.length > 0) {
          const allDatasets = await api.listDatasets();
          const validNames = new Set(allDatasets.map((d) => d.dataset_name));
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
    set({ error: null, loading: true });
    try {
      const uid = useAuthStore.getState().userId || undefined;
      const detail = await api.getSession(id, uid);
      const sessionMeta = { session_id: detail.session_id, title: detail.title, phase: detail.phase || "lines", status: detail.status || "active", mode: (detail as any).mode || "ask" };
      const loadedTurns = (detail.turns || []).map((t: any) => ({
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
      }));
      set({
        sessionMeta,
        turns: loadedTurns,
        sessionId: detail.session_id || id,
        aimProposals: detail.state?.aim_proposals || [],
        selectedAims: Array.isArray(detail.state?.selected_aims) ? detail.state.selected_aims : [],
        outputResults: Array.isArray(detail.state?.output_results) ? detail.state.output_results : [],
        chatQueryResults: detail.state?.chat_query_results || {},
        completedActions: detail.state?.completed_actions || {},
        contextSummaries: detail.state?.context_summaries || {},
        enrichmentMode: detail.state?.enrichment_mode || "research",
      });
      useUiStore.getState().selectTurn(loadedTurns.length - 1);
      useOutputStore.getState().setResults(Array.isArray(detail.state?.output_results) ? detail.state.output_results : []);
      useDatasetStore.getState().clear();
      const attachedDs = detail.state?.attached_datasets;
      if (Array.isArray(attachedDs) && attachedDs.length > 0) {
        const allDatasets = await api.listDatasets();
        const validNames = new Set(allDatasets.map((d) => d.dataset_name));
        const validDs = attachedDs.filter((d: string) => validNames.has(d));
        if (validDs.length > 0) {
          useDatasetStore.getState().addMultiple(validDs);
        }
      }
    } catch (e) {
      set({ error: getErrorMessage(e) });
    } finally {
      set({ loading: false });
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

  sendUserMessage: async (text, lineName = "", attachedAims: string[] = [], enrichmentMode = "research", routeOverride?: string, aimDescriptions?: Record<string, string>) => {
    const { sessionId, turns, isLocalSession, pendingTitle, sessionMeta } = get();
    const isDone = turns.length > 0 && Boolean(turns[turns.length - 1]?.ui?.done);
    const origSessionId = sessionId;

    if (!sessionId || !text.trim() || isDone) return;

    const userText = text.trim();
    set({ error: null, loading: true, progressSteps: [], statusMessage: "Processing...", pendingTurn: null });
    get().setPendingTurn(userText);

    // Progress polling — fetches live steps from backend while message is being processed
    const progressTimer = setInterval(async () => {
      const sid = get().sessionId;
      if (!sid) return;
      try {
        const res = await api.getProgress(sid);
        set({ progressSteps: res.steps });
      } catch { /* ignore poll errors */ }
    }, 600);

    try {
      let activeSessionId = sessionId;
      const sendUid = useAuthStore.getState().userId || undefined;

      if (isLocalSession) {
        set({ statusMessage: "Creating new session..." });
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
      const res = await api.sendMessage(activeSessionId, userText, lineName, attachedAims, enrichmentMode, [], routeOverride, aimDescriptions, language);
      clearInterval(progressTimer);
      set({ statusMessage: "Response received" });

      // If user switched sessions during loading, show toast instead of updating UI
      const currentSessionId = get().sessionId;
      if (currentSessionId !== activeSessionId) {
        const title = get().sessions.find((s) => s.session_id === activeSessionId)?.title || activeSessionId.slice(0, 8);
        useToastStore.getState().pushToast("Response received in session", activeSessionId, title);
        return res;
      }

      const datasetNames = lineName.split(",").map((d) => d.trim()).filter(Boolean);
      const newTurn = turnFromResponse(res, userText, attachedAims, datasetNames);
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
      await get().refreshSessions();
      return res;
    } catch (e) {
      clearInterval(progressTimer);
      if (get().sessionId === origSessionId || !origSessionId) {
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
        set({
          sessions: list,
          sessionMeta: current
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

// Safety net: auto-reset loading if stuck for >20s (e.g. bootstrap before login)
let _loadingTimeout: ReturnType<typeof setTimeout> | null = null;
useSessionStore.subscribe((state, prev) => {
  if (state.loading && !prev.loading) {
    if (_loadingTimeout) clearTimeout(_loadingTimeout);
    _loadingTimeout = setTimeout(() => {
      _loadingTimeout = null;
      useSessionStore.setState({ loading: false, error: "Request timed out — please try again" });
    }, 20000);
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
