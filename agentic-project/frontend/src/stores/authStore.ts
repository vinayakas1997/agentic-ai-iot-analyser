import { create } from "zustand";
import { useSessionStore } from "./sessionStore";
import { useDatasetStore } from "./datasetStore";
import { useOutputStore } from "./outputStore";

const AUTH_STORAGE_KEY = "edas.auth";

export type Role = "iot" | "normal";

interface StoredAuth {
  userId: string;
  role: Role;
  viewingDashboard?: boolean;
}

function loadStoredAuth(): StoredAuth | null {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed.userId === "string" && (parsed.role === "iot" || parsed.role === "normal")) {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

function persist(auth: StoredAuth) {
  try {
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(auth));
  } catch {
    // localStorage unavailable — state just won't persist across reloads
  }
}

interface AuthState {
  userId: string | null;
  role: Role | null;
  viewingDashboard: boolean;
  login: (userId: string, role: Role) => void;
  logout: () => void;
  setViewingDashboard: (viewing: boolean) => void;
}

const stored = loadStoredAuth();

export const useAuthStore = create<AuthState>((set, get) => ({
  userId: stored?.userId ?? null,
  role: stored?.role ?? null,
  viewingDashboard: stored?.viewingDashboard ?? false,
  login: (userId, role) => {
    persist({ userId, role, viewingDashboard: false });
    useSessionStore.getState().clearAll();
    useDatasetStore.getState().clear();
    useOutputStore.getState().clearResults();
    set({ userId, role, viewingDashboard: false });
  },
  logout: () => {
    try {
      localStorage.removeItem(AUTH_STORAGE_KEY);
    } catch {
      // ignore
    }
    useSessionStore.getState().clearAll();
    useDatasetStore.getState().clear();
    useOutputStore.getState().clearResults();
    set({ userId: null, role: null, viewingDashboard: false });
  },
  setViewingDashboard: (viewing) => {
    const { userId, role } = get();
    if (userId && role) persist({ userId, role, viewingDashboard: viewing });
    set({ viewingDashboard: viewing });
  },
}));
