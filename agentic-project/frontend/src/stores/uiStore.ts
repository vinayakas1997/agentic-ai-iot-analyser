import { create } from "zustand";
import type { Language } from "../lib/translations";

const LANGUAGE_STORAGE_KEY = "edas.language";

function loadStoredLanguage(): Language {
  try {
    const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    return stored === "ja" ? "ja" : "en";
  } catch {
    return "en";
  }
}

interface UiState {
  selectedTurnIndex: number;
  selectTurn: (index: number) => void;
  language: Language;
  setLanguage: (lang: Language) => void;
  toggleLanguage: () => void;
  tourTemplateOpen: boolean;
  setTourTemplateOpen: (v: boolean) => void;
  tourTemplateApplied: boolean;
  setTourTemplateApplied: (v: boolean) => void;
}

export const useUiStore = create<UiState>((set, get) => ({
  selectedTurnIndex: -1,
  selectTurn: (index) => set({ selectedTurnIndex: index }),
  language: loadStoredLanguage(),
  setLanguage: (lang) => {
    try {
      localStorage.setItem(LANGUAGE_STORAGE_KEY, lang);
    } catch {
      // localStorage unavailable — language just won't persist across reloads
    }
    set({ language: lang });
  },
  toggleLanguage: () => get().setLanguage(get().language === "en" ? "ja" : "en"),
  tourTemplateOpen: false,
  setTourTemplateOpen: (v) => set({ tourTemplateOpen: v }),
  tourTemplateApplied: false,
  setTourTemplateApplied: (v) => set({ tourTemplateApplied: v }),
}));
