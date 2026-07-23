import { create } from "zustand";

interface Toast {
  id: string;
  message: string;
  sessionId: string;
  sessionTitle: string;
  createdAt: number;
}

interface ToastState {
  toasts: Toast[];
  pushToast: (message: string, sessionId: string, sessionTitle: string) => void;
  dismissToast: (id: string) => void;
  dismissAll: () => void;
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  pushToast: (message, sessionId, sessionTitle) => {
    const id = crypto.randomUUID();
    set((state) => ({
      toasts: [...state.toasts, { id, message, sessionId, sessionTitle, createdAt: Date.now() }],
    }));
    // Auto-dismiss after 8 seconds
    setTimeout(() => {
      set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
    }, 8000);
  },
  dismissToast: (id) => {
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
  },
  dismissAll: () => set({ toasts: [] }),
}));
