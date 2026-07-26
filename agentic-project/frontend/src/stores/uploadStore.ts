import { create } from "zustand";
import type { UploadedFileDraft, UploadFailure } from "../types";

interface UploadState {
  pendingDrafts: UploadedFileDraft[];
  failures: UploadFailure[];
  personalDatasetsVersion: number;
  isProcessing: boolean;
  processingLabel: string;
  openClarify: (drafts: UploadedFileDraft[], failures: UploadFailure[]) => void;
  closeClarify: () => void;
  bumpPersonalDatasetsVersion: () => void;
  setProcessing: (isProcessing: boolean, label?: string) => void;
}

export const useUploadStore = create<UploadState>((set) => ({
  pendingDrafts: [],
  failures: [],
  personalDatasetsVersion: 0,
  isProcessing: false,
  processingLabel: "",
  openClarify: (drafts, failures) => set({ pendingDrafts: drafts, failures }),
  closeClarify: () => set({ pendingDrafts: [], failures: [] }),
  bumpPersonalDatasetsVersion: () => set((s) => ({ personalDatasetsVersion: s.personalDatasetsVersion + 1 })),
  setProcessing: (isProcessing, label = "") => set({ isProcessing, processingLabel: label }),
}));
