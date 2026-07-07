import { create } from "zustand";

interface UiState {
  selectedTurnIndex: number;
  selectTurn: (index: number) => void;
}

export const useUiStore = create<UiState>((set) => ({
  selectedTurnIndex: -1,
  selectTurn: (index) => set({ selectedTurnIndex: index }),
}));
