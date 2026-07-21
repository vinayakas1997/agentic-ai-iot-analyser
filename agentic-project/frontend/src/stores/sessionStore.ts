import { create } from "zustand";
import * as api from "../api/client";
import { generateSessionName } from "../lib/names";
import type { MessageResponse, SchemaSnapshot, SessionListItem, SessionMeta, Turn, TurnUi } from "../types/manager";
import { useUiStore } from "./uiStore";
import { useOutputStore, type CollectedResult } from "./outputStore";
import { useDatasetStore } from "./datasetStore";
import type { QueryResultState } from "../sections/QueryActions";

function turnFromResponse(res: MessageResponse, userMessage: string, attachedAims?: string[], attachedDatasets?: string[]): Turn {
  return {
    turn_index: res.turn_index ?? 0,
    user: userMessage,
    agent: res.agent_message || "",
    ui: res.ui || null,
    schema: res.schema || null,
    created_at: new Date().toISOString(),
    result_uuid: undefined,
    aims: attachedAims?.length ? attachedAims : undefined,
    datasets: attachedDatasets?.length ? attachedDatasets : undefined,
    description: res.description || null,
    benefits: res.benefits || null,
    columns: res.columns || null,
    analysis_actions: res.analysis_actions || undefined,
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

interface ExecutionEvent {
  topic: string;
  payload: Record<string, unknown>;
  timestamp: number;
}

interface SessionState {
  sessionId: string | null;
  isLocalSession: boolean;
  pendingTitle: string | null;
  sessions: SessionListItem[];
  turns: Turn[];
  sessionMeta: SessionMeta | null;
  loading: boolean;
  statusMessage: string | null;
  error: string | null;
  executionEvents: ExecutionEvent[];
  wsStatus: "connecting" | "connected" | "disconnected";
  pendingTurn: PendingTurn | null;
  aimProposals: { aim: string; description: string; datasets: string[] }[];
  selectedAims: { aim: string; description?: string; datasets?: string[] }[];
  outputResults: CollectedResult[];
  chatQueryResults: Record<string, QueryResultState>;
  completedActions: Record<string, string>;
  contextSummaries: Record<string, { turn_timestamps: string[]; summary: string; created_at: string }[]>;
  enrichmentMode: string;
  bootstrap: () => Promise<void>;
  refreshSessions: () => Promise<SessionListItem[]>;
  switchSession: (id: string) => Promise<void>;
  newSession: () => void;
  sendUserMessage: (text: string, lineName?: string, attachedAims?: string[], enrichmentMode?: string) => Promise<MessageResponse | undefined>;
  reopenSession: () => Promise<void>;
  forkSession: () => Promise<void>;
  setError: (error: string | null) => void;
  setStatusMessage: (msg: string | null) => void;
  pushExecutionEvent: (event: ExecutionEvent) => void;
  clearExecutionEvents: () => void;
  setWsStatus: (status: "connecting" | "connected" | "disconnected") => void;
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
  statusMessage: null,
  error: null,
  executionEvents: [],
  wsStatus: "connecting",
  pendingTurn: null,
  aimProposals: [],
  selectedAims: [],
  outputResults: [],
  chatQueryResults: {},
  completedActions: {},
  contextSummaries: {},
  enrichmentMode: "research",

  refreshSessions: async () => {
    const list = await api.listSessions();
    const withMode = list.map((s) => ({ ...s, mode: (s as any).mode || "ask" }));
    set({ sessions: withMode });
    return withMode;
  },

  bootstrap: async () => {
    set({ error: null, loading: true });
    try {
      const list = await get().refreshSessions();
      if (list.length > 0) {
        const detail = await api.getSession(list[0].session_id);
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
          useDatasetStore.getState().addMultiple(attachedDs);
        }
      } else {
        const tempId = crypto.randomUUID();
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
      const detail = await api.getSession(id);
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
        executionEvents: [],
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
        useDatasetStore.getState().addMultiple(attachedDs);
      }
    } catch (e) {
      set({ error: getErrorMessage(e) });
    } finally {
      set({ loading: false });
    }
  },

  newSession: () => {
    const tempId = crypto.randomUUID();
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
      executionEvents: [],
      pendingTurn: null,
    });
    useOutputStore.getState().clearResults();
    useDatasetStore.getState().clear();
    useUiStore.getState().selectTurn(-1);
  },

  sendUserMessage: async (text, lineName = "", attachedAims: string[] = [], enrichmentMode = "research") => {
    const { sessionId, turns, isLocalSession, pendingTitle, sessionMeta } = get();
    const isDone = turns.length > 0 && Boolean(turns[turns.length - 1]?.ui?.done);

    if (!sessionId || !text.trim() || isDone) return;

    const userText = text.trim();
    set({ error: null, loading: true, statusMessage: "Analyzing your request...", executionEvents: [], pendingTurn: null });
    get().setPendingTurn(userText);

    const statusSteps = [
      "Analyzing your request...",
      "Resolving line and time...",
      "Fetching data schema...",
      "Building analysis plan...",
      "Generating response...",
    ];
    let stepIndex = 0;
    const statusTimer = setInterval(() => {
      stepIndex = (stepIndex + 1) % statusSteps.length;
      set({ statusMessage: statusSteps[stepIndex] });
    }, 3000);

    try {
      let activeSessionId = sessionId;

      if (isLocalSession) {
        set({ statusMessage: "Creating new session..." });
        const name = pendingTitle || generateSessionName();
        const created = await api.createSession(name);
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
          api.updateSessionState(activeSessionId, prePayload).catch(() => {});
        }
      }

      // Send empty history — enrichment block replaces it (built server-side)
      const res = await api.sendMessage(activeSessionId, userText, lineName, attachedAims, enrichmentMode, []);
      clearInterval(statusTimer);
      set({ statusMessage: "Response received" });
      const datasetNames = lineName.split(",").map((d) => d.trim()).filter(Boolean);
      const newTurn = turnFromResponse(res, userText, attachedAims, datasetNames);
      const isFirstTurn = turns.length === 0;
      set((state) => ({
        turns: [...state.turns, newTurn],
        pendingTurn: null,
        sessionMeta: {
          ...(state.sessionMeta || { session_id: activeSessionId }),
          phase: res.phase,
          status: res.status,
        },
      }));
      // Auto-name session after first message
      if (isFirstTurn) {
        const name = userText.slice(0, 50).trim();
        if (name) {
          api.updateSessionTitle(activeSessionId, name).catch(() => {});
          set((s) => ({
            sessionMeta: s.sessionMeta ? { ...s.sessionMeta, title: name } : s.sessionMeta,
          }));
        }
      }
      // Store aim proposals from response
      if (res.aim_proposals?.length) {
        set((state) => {
          const seen = new Set(state.aimProposals.map((p) => p.aim));
          const fresh = res.aim_proposals!.filter((p) => !seen.has(p.aim));
          return fresh.length ? { aimProposals: [...state.aimProposals, ...fresh] } : {};
        });
      }
      const nextIdx = useUiStore.getState().selectedTurnIndex;
      useUiStore.getState().selectTurn(nextIdx < 0 ? 0 : nextIdx + 1);
      await get().refreshSessions();
      return res;
    } catch (e) {
      clearInterval(statusTimer);
      set({ error: getErrorMessage(e), pendingTurn: null });
      throw e;
    } finally {
      clearInterval(statusTimer);
      set({ loading: false, statusMessage: null });
    }
  },

  reopenSession: async () => {
    const { sessionId } = get();
    if (!sessionId) return;
    set({ error: null, loading: true });
    try {
      await api.reopenSession(sessionId);
      set({ executionEvents: [] });
      await get().switchSession(sessionId);
    } catch (e) {
      set({ error: getErrorMessage(e) });
    } finally {
      set({ loading: false });
    }
  },

  forkSession: async () => {
    const { sessionId } = get();
    if (!sessionId) return;
    set({ error: null, loading: true });
    try {
      const { session_id } = await api.forkSession(sessionId);
      await get().switchSession(session_id);
      await get().refreshSessions();
    } catch (e) {
      set({ error: getErrorMessage(e) });
    } finally {
      set({ loading: false });
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
      await api.updateSessionState(get().sessionId!, { output_results: results });
      set({ outputResults: results });
      useOutputStore.getState().setResults(results);
    } catch (e) {
      set({ error: getErrorMessage(e) });
    }
  },

  updateChatQueryResults: async (results) => {
    try {
      await api.updateSessionState(get().sessionId!, { chat_query_results: results });
      set({ chatQueryResults: results });
    } catch (e) {
      set({ error: getErrorMessage(e) });
    }
  },

  setError: (error) => set({ error }),

  setStatusMessage: (msg) => set({ statusMessage: msg }),

  setPendingTitle: (title) => set({ pendingTitle: title }),

  setEnrichmentMode: (mode) => set({ enrichmentMode: mode }),

  pushExecutionEvent: (event) =>
    set((state) => ({
      executionEvents: [...state.executionEvents.slice(-49), event],
    })),

  clearExecutionEvents: () => set({ executionEvents: [] }),

  setWsStatus: (status) => set({ wsStatus: status }),

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
        const list = await api.listSessions();
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
