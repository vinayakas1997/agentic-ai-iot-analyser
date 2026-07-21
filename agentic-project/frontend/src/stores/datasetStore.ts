import { create } from "zustand";

interface DatasetSelection {
  selected: string[];
  attached: string[];
  lockedByAims: string[];
  toggle: (name: string) => void;
  attach: (name: string) => void;
  detach: (name: string) => void;
  remove: (name: string) => void;
  addMultiple: (names: string[]) => void;
  attachMultiple: (names: string[]) => void;
  clear: () => void;
  setLockedByAims: (names: string[]) => void;
}

export const useDatasetStore = create<DatasetSelection>((set) => ({
  selected: [],
  attached: [],
  lockedByAims: [],
  toggle: (name) =>
    set((s) => {
      const inSelected = s.selected.includes(name);
      return {
        selected: inSelected
          ? s.selected.filter((n) => n !== name)
          : [...s.selected, name],
        attached: inSelected
          ? s.attached.filter((n) => n !== name)
          : [...s.attached, name],
      };
    }),
  attach: (name) =>
    set((s) => ({
      attached: s.attached.includes(name) ? s.attached : [...s.attached, name],
    })),
  detach: (name) =>
    set((s) => ({
      attached: s.attached.filter((n) => n !== name),
    })),
  remove: (name) =>
    set((s) => ({
      selected: s.selected.filter((n) => n !== name),
      attached: s.attached.filter((n) => n !== name),
    })),
  addMultiple: (names) =>
    set((s) => ({
      selected: [...new Set([...s.selected, ...names])],
      attached: [...new Set([...s.attached, ...names])],
    })),
  attachMultiple: (names) =>
    set((s) => ({
      attached: [...new Set([...s.attached, ...names])],
    })),
  clear: () => set({ selected: [], attached: [], lockedByAims: [] }),
  setLockedByAims: (names) => set({ lockedByAims: names }),
}));
