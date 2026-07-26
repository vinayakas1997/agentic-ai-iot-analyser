import { create } from "zustand";

const AUTH_STORAGE_KEY = "edas.auth";

export type Role = "iot" | "normal";

interface StoredAuth {
  userId: string;
  role: Role;
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

interface AuthState {
  userId: string | null;
  role: Role | null;
  login: (userId: string, role: Role) => void;
  logout: () => void;
}

const stored = loadStoredAuth();

export const useAuthStore = create<AuthState>((set) => ({
  userId: stored?.userId ?? null,
  role: stored?.role ?? null,
  login: (userId, role) => {
    try {
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify({ userId, role }));
    } catch {
      // localStorage unavailable — login just won't persist across reloads
    }
    set({ userId, role });
  },
  logout: () => {
    try {
      localStorage.removeItem(AUTH_STORAGE_KEY);
    } catch {
      // ignore
    }
    set({ userId: null, role: null });
  },
}));
