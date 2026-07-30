// Empty = same-origin (nginx proxies /api/ → backend). Avoids CORS "Failed to fetch".
const API = import.meta.env.VITE_API_URL ?? "";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

/** Matches backend max_upload_size_mb / nginx client_max_body_size. */
export const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(body || res.statusText, res.status);
  }
  return res.json();
}

async function withRetry<T>(fn: () => Promise<T>, maxRetries = 3): Promise<T> {
  let lastErr: unknown;
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (e) {
      lastErr = e;
      if (e instanceof ApiError && e.status === 409) {
        const delay = 1000 * Math.pow(2, i);
        await new Promise((r) => setTimeout(r, delay));
        continue;
      }
      throw e;
    }
  }
  throw lastErr;
}

export async function resolveLine(lineName: string) {
  return request<{
    found: boolean;
    line_name: string;
    canonical: string | null;
    source: string | null;
    candidates: string[];
    datasets: any[];
  }>("/api/v2/resolve-line", {
    method: "POST",
    body: JSON.stringify({ line_name: lineName }),
  });
}

export async function generateNewResearch(userText: string, datasets: any[]) {
  return request<{
    aim: string;
    how_we_will_do_it: string;
    datasets_used: string[];
    joins: string | null;
  }>("/api/v2/aim/new-research", {
    method: "POST",
    body: JSON.stringify({ user_text: userText, datasets }),
  });
}

export async function proceedToTaskRegistry(params: {
  session_id: string;
  bucket_id: string;
  aim: string;
  line_name: string;
  datasets_used: string[];
  how_we_will_do_it: string;
}) {
  return request<{ status: string; version: number }>("/api/v2/bucket/proceed", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function createSession(title?: string, userId?: string) {
  const body: Record<string, unknown> = {};
  if (title) body.title = title;
  if (userId) body.user_id = userId;
  return request<{ session_id: string; title: string }>("/api/v2/sessions", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function listSessions(userId?: string) {
  const params = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return request<{ session_id: string; title: string; phase: string; status: string; mode?: string }[]>(
    `/api/v2/sessions${params}`
  );
}

export async function deleteSession(sessionId: string) {
  return request<{ status: string; session_id: string }>(`/api/v2/sessions/${sessionId}`, {
    method: "DELETE",
  });
}

export async function getSession(sessionId: string) {
  return request<{
    session_id: string;
    title: string;
    phase: string;
    status: string;
    mode?: string;
    state: any;
    turns: { user: string; agent: string; timestamp: string; aims?: string[]; datasets?: string[]; analysis_actions?: any; result_uuid?: string }[];
  }>(`/api/v2/sessions/${sessionId}`);
}

export async function sendMessage(sessionId: string, message: string, lineName = "", attachedAims: string[] = [], enrichmentMode = "research", history?: { role: string; content: string }[], routeOverride?: string, aimDescriptions?: Record<string, string>, language?: string) {
  const body: Record<string, unknown> = { session_id: sessionId, message, line_name: lineName, attached_aims: attachedAims, enrichment_mode: enrichmentMode, history: history ?? [] };
  if (routeOverride) body.route_override = routeOverride;
  if (aimDescriptions && Object.keys(aimDescriptions).length > 0) body.aim_descriptions = aimDescriptions;
  if (language) body.language = language;
  return withRetry(() => request<{
    session_id: string;
    turn_index?: number;
    agent_message?: string;
    next_step?: string | null;
    phase?: string;
    status?: string;
    ui?: any;
    schema?: any;
    done?: boolean;
    aim_proposals?: { aim: string; description: string; datasets: string[]; goal?: string; columns?: string[]; insight?: string }[];
    analysis_actions?: { name: string; description: string; datasets: string[]; goal?: string; columns?: string[]; insight?: string }[];
    result_uuid?: string;
    route?: string;
    query_result?: {
      sql: string;
      columns: string[];
      column_types?: string[];
      rows: Record<string, unknown>[];
      row_count: number;
      chart_suggestions?: any;
    };
    deep_iterations?: {
      iteration: number;
      result_uuid?: string;
      aim?: string;
      explanation: string;
      sql: string;
      columns: string[];
      column_types?: string[];
      rows: Record<string, unknown>[];
      row_count: number;
      chart_suggestions?: any;
    }[];
  }>("/api/v2/messages", {
    method: "POST",
    body: JSON.stringify(body),
  }));
}

export async function updateSessionState(sessionId: string, state: Record<string, unknown>) {
  return withRetry(() => request<{ session_id: string }>(`/api/v2/sessions/${sessionId}`, {
    method: "PATCH",
    body: JSON.stringify({ state }),
  }));
}

export async function updateSessionTitle(sessionId: string, title: string) {
  return request<{ session_id: string; title: string | null }>(`/api/v2/sessions/${sessionId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

import type { ChartConfig } from "../sections/QueryActions";

export async function executeQuery(sessionId: string, message: string, lineName = "", history?: { role: string; content: string }[]) {
  return withRetry(() => request<{
    session_id: string;
    sql: string;
    columns: string[];
    column_types: string[];
    rows: Record<string, unknown>[];
    row_count: number;
    chart_suggestions?: { advanced: ChartConfig[]; basic: ChartConfig[] };
  }>("/api/v2/execute-query", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, message, line_name: lineName, history }),
  }));
}

export async function getProgress(sessionId: string) {
  return request<{ steps: { step: string; status: string; detail: string; ts: number }[] }>(
    `/api/v2/sessions/${sessionId}/progress`
  );
}

export async function summarizeContext(sessionId: string, tag: string, turnTimestamps: string[]) {
  return withRetry(() => request<{
    tag: string;
    summary: string;
    created_at: string;
  }>(`/api/v2/sessions/${sessionId}/summarize-context`, {
    method: "POST",
    body: JSON.stringify({ tag, turn_timestamps: turnTimestamps }),
  }));
}

export async function listDatasets() {
  return request<{
    line_name: string;
    dataset_name: string;
    description: string | null;
    table: string | null;
    column_definitions: { name: string; datatype: string; meaning?: string }[];
    role: string | null;
    join_hints: any;
    suggested_aims: any;
    synonyms: string[] | null;
  }[]>("/api/v2/datasets");
}

import type { UploadedFileDraft, UploadFailure, PersonalDataset, ColumnDraft } from "../types";

export async function uploadCsvFiles(files: File[]) {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  const res = await fetch(`${API}/api/v2/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(body || res.statusText, res.status);
  }
  return res.json() as Promise<{ status: string; files: UploadedFileDraft[]; failures: UploadFailure[] }>;
}

export async function confirmUploadDataset(datasetId: number, columns: ColumnDraft[], description = "") {
  return request<{ id: number; dataset_name: string; status: string }>(
    `/api/v2/upload/${datasetId}/confirm`,
    { method: "POST", body: JSON.stringify({ columns, description }) }
  );
}

export async function llmFillMeanings(datasetId: number, columns: string[], language?: string) {
  return request<{ columns: ColumnDraft[] }>(
    `/api/v2/upload/${datasetId}/llm-fill`,
    { method: "POST", body: JSON.stringify({ columns, language }) }
  );
}

export async function listUserDatasets() {
  return request<{ datasets: PersonalDataset[] }>("/api/v2/user-datasets");
}

export async function updateDatasetColumns(datasetId: number, columns: ColumnDraft[], description?: string) {
  return request<{ id: number; dataset_name: string; status: string }>(
    `/api/v2/user-datasets/${datasetId}/columns`,
    { method: "PATCH", body: JSON.stringify({ columns, description }) }
  );
}

export async function deleteUserDataset(datasetId: number) {
  return request<{ status: string; id: number }>(`/api/v2/user-datasets/${datasetId}`, { method: "DELETE" });
}

export async function login(userId: string) {
  return request<{ user_id: string; role: "iot" | "normal" }>("/api/v2/login", {
    method: "POST",
    body: JSON.stringify({ user_id: userId }),
  });
}

export interface RegistryColumnDraft {
  name: string;
  datatype: string;
  meaning: string;
}

export async function introspectTable(tableName: string) {
  return request<{ table_name: string; columns: RegistryColumnDraft[]; sample_rows: Record<string, unknown>[] }>(
    "/api/v2/registry-admin/introspect",
    { method: "POST", body: JSON.stringify({ table_name: tableName }) }
  );
}

export async function createRegistryEntry(params: {
  maintained_by: string;
  line_name: string;
  dataset_name: string;
  table_name: string;
  description?: string;
  column_definitions: RegistryColumnDraft[];
  role?: string;
  join_hints?: unknown;
  suggested_aims?: unknown;
  synonyms?: string[];
}) {
  return request<{ id: number; status: string }>("/api/v2/registry-admin/entries", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function confirmRegistryEntry(entryId: number, columns: RegistryColumnDraft[], description = "") {
  return request<{ id: number; dataset_name: string; status: string }>(
    `/api/v2/registry-admin/entries/${entryId}/confirm`,
    { method: "POST", body: JSON.stringify({ columns, description }) }
  );
}

export interface RegistryEntry {
  id: number;
  line_name: string;
  dataset_name: string;
  table: string | null;
  description: string | null;
  column_definitions: RegistryColumnDraft[];
  role: string | null;
  join_hints: unknown;
  suggested_aims: unknown;
  synonyms: string[] | null;
  status: string;
  maintained_by: string | null;
}

export async function listRegistryEntries(maintainedBy?: string) {
  const qs = maintainedBy ? `?maintained_by=${encodeURIComponent(maintainedBy)}` : "";
  return request<{ entries: RegistryEntry[] }>(`/api/v2/registry-admin/entries${qs}`);
}

export async function deleteRegistryEntry(entryId: number) {
  return request<{ status: string; id: number }>(`/api/v2/registry-admin/entries/${entryId}`, { method: "DELETE" });
}
