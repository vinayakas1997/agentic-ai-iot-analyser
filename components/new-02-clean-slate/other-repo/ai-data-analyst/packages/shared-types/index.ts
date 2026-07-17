// Shared TypeScript types for the monorepo

export interface ExampleType {
  id: string;
  createdAt: string; // ISO timestamp
}

export type Result<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };