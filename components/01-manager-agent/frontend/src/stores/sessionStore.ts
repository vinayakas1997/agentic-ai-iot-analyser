import axios from "axios";
import { create } from "zustand";
import { createSession, forkSession as forkSessionApi, getSession, listSessions, reopenSession as reopenSessionApi, sendMessage } from "../api/manager";
import type { MessageResponse, SessionListItem, SessionMeta, Turn } from "../types/manager";
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

interface ExecutionEvent {
  topic: string;
  payload: Record<string, unknown>;
  timestamp: number;
}

interface SessionState {
  sessionId: string | null;
  sessions: SessionListItem[];
  turns: Turn[];
  sessionMeta: SessionMeta | null;
  loading: boolean;
  error: string | null;
  executionEvents: ExecutionEvent[];
  bootstrap: () => Promise<void>;
  refreshSessions: () => Promise<SessionListItem[]>;
  switchSession: (id: string) => Promise<void>;
  newSession: () => Promise<void>;
  sendUserMessage: (text: string, lineName?: string) => Promise<MessageResponse | undefined>;
  reopenSession: () => Promise<void>;
  forkSession: () => Promise<void>;
  setError: (error: string | null) => void;
  pushExecutionEvent: (event: ExecutionEvent) => void;
  clearExecutionEvents: () => void;
}

export const useSessionStore = create<SessionState>((set, get) => ({
  sessionId: null,
  sessions: [],
  turns: [],
  sessionMeta: null,
  loading: false,
  error: null,
  executionEvents: [],

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
        });
        useUiStore.getState().selectTurn(detail.turns.length ? detail.turns.length - 1 : -1);
      } else {
        const created = await createSession();
        set({
          sessionId: created.session_id,
          sessionMeta: { session_id: created.session_id, status: "active", phase: "extract" },
          turns: [],
        });
        useUiStore.getState().selectTurn(-1);
        await get().refreshSessions();
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
      });
      useUiStore.getState().selectTurn(detail.turns.length ? detail.turns.length - 1 : -1);
    } catch (e) {
      set({ error: getErrorMessage(e) });
    } finally {
      set({ loading: false });
    }
  },

  newSession: async () => {
    set({ error: null, loading: true });
    try {
      const created = await createSession();
      set({
        sessionId: created.session_id,
        sessionMeta: { session_id: created.session_id, status: "active", phase: "extract" },
        turns: [],
      });
      useUiStore.getState().selectTurn(-1);
      await get().refreshSessions();
    } catch (e) {
      set({ error: getErrorMessage(e) });
    } finally {
      set({ loading: false });
    }
  },

  sendUserMessage: async (text, lineName = "") => {
    const { sessionId, turns } = get();
    const selectedTurnIndex = useUiStore.getState().selectedTurnIndex;
    const isDone = turns.length > 0 && Boolean(turns[turns.length - 1]?.ui?.done);
    const isLive = turns.length === 0 || selectedTurnIndex === turns.length - 1;

    if (!sessionId || !text.trim() || isDone || !isLive) return;

    set({ error: null, loading: true, executionEvents: [] });
    const userText = text.trim();
    try {
      const res = await sendMessage(sessionId, userText, lineName);
      const newTurn = turnFromResponse(res, userText);
      set((state) => ({
        turns: [...state.turns, newTurn],
        sessionMeta: {
          ...(state.sessionMeta || { session_id: sessionId }),
          phase: res.phase,
          status: res.status,
        },
      }));
      useUiStore.getState().selectTurn(selectedTurnIndex < 0 ? 0 : selectedTurnIndex + 1);
      await get().refreshSessions();
      return res;
    } catch (e) {
      set({ error: getErrorMessage(e) });
      throw e;
    } finally {
      set({ loading: false });
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
    } catch (e) {
      set({ error: getErrorMessage(e) });
    } finally {
      set({ loading: false });
    }
  },

  setError: (error) => set({ error }),

  pushExecutionEvent: (event) =>
    set((state) => ({
      executionEvents: [...state.executionEvents.slice(-49), event],
    })),

  clearExecutionEvents: () => set({ executionEvents: [] }),
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
