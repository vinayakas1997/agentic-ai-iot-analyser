import { create } from "zustand";

export type AppView = "workspace" | "dashboard";

interface UiState {
  view: AppView;
  selectedTurnIndex: number;
  setView: (view: AppView) => void;
  selectTurn: (index: number) => void;
}

export const useUiStore = create<UiState>((set) => ({
  view: "workspace",
  selectedTurnIndex: -1,
  setView: (view) => set({ view }),
  selectTurn: (index) => set({ selectedTurnIndex: index }),
}));
