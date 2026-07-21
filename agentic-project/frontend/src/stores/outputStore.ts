import { create } from "zustand";
import type { QueryResultState } from "../sections/QueryActions";

export interface CollectedResult {
  id: string;
  aim: string;
  description?: string;
  datasets?: string[];
  result: QueryResultState;
  created_at: number;
}

interface OutputState {
  results: CollectedResult[];
  addResult: (r: Omit<CollectedResult, "id" | "created_at">) => void;
  removeResult: (id: string) => void;
  clearResults: () => void;
  setResults: (results: CollectedResult[]) => void;
}

export const useOutputStore = create<OutputState>((set, get) => ({
  results: [],

  addResult: (r) => {
    set((state) => {
      const existing = state.results.find((x) => x.aim === r.aim);
      const entry: CollectedResult = {
        ...r,
        id: existing?.id || crypto.randomUUID(),
        created_at: existing?.created_at || Date.now(),
      };
      if (existing) {
        return { results: state.results.map((x) => (x.aim === r.aim ? entry : x)) };
      }
      return { results: [...state.results, entry] };
    });
  },

  removeResult: (id) => {
    set((state) => ({ results: state.results.filter((r) => r.id !== id) }));
  },

  clearResults: () => set({ results: [] }),

  setResults: (results) => set({ results }),
}));
