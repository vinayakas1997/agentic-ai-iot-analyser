import axios from "axios";
import { create } from "zustand";
import { createSession, forkSession as forkSessionApi, getSession, listSessions, reopenSession as reopenSessionApi, sendMessage, updateSessionTitle } from "../api/manager";
import { generateSessionName } from "../lib/names";
import type { MessageResponse, SchemaSnapshot, SessionListItem, SessionMeta, Turn, TurnUi } from "../types/manager";
import { useUiStore } from "./uiStore";

function turnFromResponse(res: MessageResponse, userMessage: string): Turn {
  return {
    turn_index: res.turn_index ?? 0,
    user: userMessage,
    agent: res.agent_message || "",
    ui: res.ui || null,
    schema: res.schema || null,
    created_at: new Date().toISOString(),
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
  bootstrap: () => Promise<void>;
  refreshSessions: () => Promise<SessionListItem[]>;
  switchSession: (id: string) => Promise<void>;
  newSession: () => void;
  sendUserMessage: (text: string, lineName?: string) => Promise<MessageResponse | undefined>;
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

  refreshSessions: async () => {
    const list = await listSessions();
    set({ sessions: list });
    return list;
  },

  bootstrap: async () => {
    set({ error: null, loading: true });
    try {
      const list = await get().refreshSessions();
      if (list.length > 0) {
        const detail = await getSession(list[0].session_id);
        set({
          sessionMeta: detail.session,
          turns: detail.turns,
          sessionId: detail.session.session_id,
          isLocalSession: false,
        });
        useUiStore.getState().selectTurn(detail.turns.length ? detail.turns.length - 1 : -1);
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
      const detail = await getSession(id);
      set({
        sessionMeta: detail.session,
        turns: detail.turns,
        sessionId: detail.session.session_id,
        executionEvents: [],
      });
      useUiStore.getState().selectTurn(detail.turns.length ? detail.turns.length - 1 : -1);
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
      executionEvents: [],
      pendingTurn: null,
    });
    useUiStore.getState().selectTurn(-1);
  },

  sendUserMessage: async (text, lineName = "") => {
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
        const created = await createSession(name);
        activeSessionId = created.session_id;
        set({
          sessionId: activeSessionId,
          isLocalSession: false,
          pendingTitle: null,
          sessionMeta: { session_id: activeSessionId, title: name, mode: "ask", status: "active", phase: "extract" },
        });
      }

      const res = await sendMessage(activeSessionId, userText, lineName);
      clearInterval(statusTimer);
      set({ statusMessage: "Response received" });
      const newTurn = turnFromResponse(res, userText);
      set((state) => ({
        turns: [...state.turns, newTurn],
        pendingTurn: null,
        sessionMeta: {
          ...(state.sessionMeta || { session_id: activeSessionId }),
          phase: res.phase,
          status: res.status,
        },
      }));
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
      const detail = await reopenSessionApi(sessionId);
      set({
        sessionMeta: detail.session,
        turns: detail.turns,
        executionEvents: [],
      });
      useUiStore.getState().selectTurn(detail.turns.length - 1);
      await get().refreshSessions();
    } catch (e: unknown) {
      if (axios.isAxiosError(e) && e.response?.status === 400) {
        set({ error: e.response.data?.detail || "Cannot edit — planner already started." });
      } else {
        set({ error: getErrorMessage(e) });
      }
    } finally {
      set({ loading: false });
    }
  },

  forkSession: async () => {
    const { sessionId } = get();
    if (!sessionId) return;
    set({ error: null, loading: true });
    try {
      const { session_id } = await forkSessionApi(sessionId);
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
      await updateSessionTitle(sessionId, title);
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

  setError: (error) => set({ error }),

  setStatusMessage: (msg) => set({ statusMessage: msg }),

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
        const list = await listSessions();
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
