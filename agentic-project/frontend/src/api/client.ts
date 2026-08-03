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
}, userId?: string) {
  return request<{ status: string; version: number }>("/api/v2/bucket/proceed", {
    method: "POST",
    body: JSON.stringify({ ...params, user_id: userId }),
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

export async function deleteSession(sessionId: string, userId?: string) {
  const params = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return request<{ status: string; session_id: string }>(`/api/v2/sessions/${sessionId}${params}`, {
    method: "DELETE",
  });
}

export async function getSession(sessionId: string, userId?: string) {
  const params = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return request<{
    session_id: string;
    title: string;
    phase: string;
    status: string;
    mode?: string;
    state: any;
    turns: { user: string; agent: string; timestamp: string; aims?: string[]; datasets?: string[]; analysis_actions?: any; result_uuid?: string }[];
  }>(`/api/v2/sessions/${sessionId}${params}`);
}

export async function sendMessage(sessionId: string, message: string, lineName = "", attachedAims: string[] = [], enrichmentMode = "research", history?: { role: string; content: string }[], routeOverride?: string, aimDescriptions?: Record<string, string>, language?: string, userId?: string, formatSpec?: string) {
  const body: Record<string, unknown> = { session_id: sessionId, message, line_name: lineName, attached_aims: attachedAims, enrichment_mode: enrichmentMode, history: history ?? [] };
  if (routeOverride) body.route_override = routeOverride;
  if (aimDescriptions && Object.keys(aimDescriptions).length > 0) body.aim_descriptions = aimDescriptions;
  if (language) body.language = language;
  if (userId) body.user_id = userId;
  if (formatSpec) body.format_spec = formatSpec;
  // No withRetry: 409 after LLM work must not re-run the whole pipeline.
  // Backend retries the DB save without calling the LLM again.
  return request<{
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
  });
}

export async function updateSessionState(sessionId: string, state: Record<string, unknown>, userId?: string) {
  return withRetry(() => request<{ session_id: string }>(`/api/v2/sessions/${sessionId}`, {
    method: "PATCH",
    body: JSON.stringify({ state, user_id: userId }),
  }));
}

export async function updateSessionTitle(sessionId: string, title: string) {
  return request<{ session_id: string; title: string | null }>(`/api/v2/sessions/${sessionId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

import type { ChartConfig } from "../sections/QueryActions";

export async function executeQuery(sessionId: string, message: string, lineName = "", history?: { role: string; content: string }[], userId?: string) {
  // No withRetry: SQL/LLM critic loop must not be replayed on 409.
  return request<{
    session_id: string;
    sql: string;
    columns: string[];
    column_types: string[];
    rows: Record<string, unknown>[];
    row_count: number;
    chart_suggestions?: { advanced: ChartConfig[]; basic: ChartConfig[] };
  }>("/api/v2/execute-query", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, message, line_name: lineName, history, user_id: userId }),
  });
}

export async function getProgress(sessionId: string, userId?: string) {
  const params = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return request<{ steps: { step: string; status: string; detail: string; ts: number }[] }>(
    `/api/v2/sessions/${sessionId}/progress${params}`
  );
}

export async function summarizeContext(sessionId: string, tag: string, turnTimestamps: string[], userId?: string) {
  // No withRetry: backend already retries save without re-calling the LLM.
  return request<{
    tag: string;
    summary: string;
    created_at: string;
  }>(`/api/v2/sessions/${sessionId}/summarize-context`, {
    method: "POST",
    body: JSON.stringify({ tag, turn_timestamps: turnTimestamps, user_id: userId }),
  });
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

import type { UploadedFileDraft, UploadFailure, PersonalDataset, ColumnDraft, ColumnTemplate, TemplateMatch, AnswerTemplate } from "../types";

export async function uploadCsvFiles(files: File[], userId?: string) {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  if (userId) form.append("user_id", userId);
  const res = await fetch(`${API}/api/v2/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(body || res.statusText, res.status);
  }
  return res.json() as Promise<{ status: string; files: UploadedFileDraft[]; failures: UploadFailure[] }>;
}

export async function confirmUploadDataset(datasetId: number, columns: ColumnDraft[], description = "", userId?: string) {
  return request<{ id: number; dataset_name: string; status: string }>(
    `/api/v2/upload/${datasetId}/confirm`,
    { method: "POST", body: JSON.stringify({ columns, description, user_id: userId }) }
  );
}

export async function llmFillMeanings(datasetId: number, columns: string[], language?: string, userId?: string) {
  return request<{ columns: ColumnDraft[] }>(
    `/api/v2/upload/${datasetId}/llm-fill`,
    { method: "POST", body: JSON.stringify({ columns, language, user_id: userId }) }
  );
}

export async function registryLlmFill(
  tableName: string,
  columns: string[],
  sampleRows: Record<string, unknown>[],
  language?: string,
  connectionId?: number,
  userId?: string,
) {
  return request<{ columns: { name: string; meaning: string }[] }>("/api/v2/registry-admin/llm-fill", {
    method: "POST",
    body: JSON.stringify({
      table_name: tableName,
      columns,
      sample_rows: sampleRows,
      language,
      connection_id: connectionId,
      user_id: userId,
    }),
  });
}

export async function registryDraftDescription(
  tableName: string,
  columns: { name: string; meaning: string }[],
  language?: string,
  userId?: string,
) {
  return request<{ description: string }>("/api/v2/registry-admin/draft-description", {
    method: "POST",
    body: JSON.stringify({
      table_name: tableName,
      columns,
      language,
      user_id: userId,
    }),
  });
}

export async function listUserDatasets(userId?: string) {
  const params = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return request<{ datasets: PersonalDataset[] }>(`/api/v2/user-datasets${params}`);
}

export async function updateDatasetColumns(datasetId: number, columns: ColumnDraft[], description?: string, userId?: string) {
  return request<{ id: number; dataset_name: string; status: string }>(
    `/api/v2/user-datasets/${datasetId}/columns`,
    { method: "PATCH", body: JSON.stringify({ columns, description, user_id: userId }) }
  );
}

export async function deleteUserDataset(datasetId: number, userId?: string) {
  const params = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return request<{ status: string; id: number }>(`/api/v2/user-datasets/${datasetId}${params}`, { method: "DELETE" });
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

export interface DbConnection {
  id: number;
  name: string;
  db_type: "postgres" | "mysql";
  host: string;
  port: number;
  database_name: string;
  username: string;
  password?: string;
  schema_name: string | null;
  created_by?: string | null;
  created_at?: string | null;
}

export interface ConnectionTestResult {
  connection_id: number;
  ok: boolean;
  latency_ms: number;
  error?: string;
}

export async function createDbConnection(params: {
  name: string;
  db_type: string;
  host: string;
  port: number;
  database_name: string;
  username: string;
  password: string;
  schema_name?: string;
  user_id?: string;
}) {
  return request<{ id: number; status: string }>("/api/v2/db-connections", {
    method: "POST",
    body: JSON.stringify({ ...params, user_id: params.user_id || "" }),
  });
}

export async function listDbConnections() {
  return request<{ connections: DbConnection[] }>("/api/v2/db-connections");
}

export async function deleteDbConnection(connectionId: number, userId?: string) {
  const qs = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return request<{ status: string; id: number }>(`/api/v2/db-connections/${connectionId}${qs}`, { method: "DELETE" });
}

export async function testDbConnection(connectionId: number, userId?: string) {
  const qs = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return request<ConnectionTestResult>(`/api/v2/db-connections/${connectionId}/test${qs}`, { method: "POST" });
}

export async function listConnectionTables(connectionId: number, userId?: string) {
  const qs = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return request<{ connection_id: number; tables: string[] }>(`/api/v2/db-connections/${connectionId}/tables${qs}`);
}

export interface IntrospectResult {
  table_name: string;
  columns: RegistryColumnDraft[];
  sample_rows: Record<string, unknown>[];
  data_earliest_ts: string | null;
  data_earliest_col: string | null;
}

export async function introspectTable(tableName: string, userId?: string, connectionId?: number) {
  return request<IntrospectResult>(
    "/api/v2/registry-admin/introspect",
    { method: "POST", body: JSON.stringify({ table_name: tableName, user_id: userId, connection_id: connectionId }) }
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
  connection_id?: number;
  data_earliest_ts?: string | null;
  user_id?: string;
}) {
  return request<{ id: number; status: string }>("/api/v2/registry-admin/entries", {
    method: "POST",
    body: JSON.stringify({ ...params, user_id: params.user_id || params.maintained_by }),
  });
}

export async function confirmRegistryEntry(entryId: number, columns: RegistryColumnDraft[], description = "", userId?: string) {
  return request<{ id: number; dataset_name: string; status: string }>(
    `/api/v2/registry-admin/entries/${entryId}/confirm`,
    { method: "POST", body: JSON.stringify({ columns, description, user_id: userId }) }
  );
}

export interface RegistryEntry {
  id: number;
  line_name: string;
  dataset_name: string;
  table: string | null;
  connection_id: number | null;
  db_type: string | null;
  description: string | null;
  column_definitions: RegistryColumnDraft[];
  role: string | null;
  join_hints: unknown;
  suggested_aims: unknown;
  synonyms: string[] | null;
  status: string;
  maintained_by: string | null;
  data_earliest_ts: string | null;
}

export async function listRegistryEntries(maintainedBy?: string) {
  const qs = maintainedBy ? `?maintained_by=${encodeURIComponent(maintainedBy)}` : "";
  return request<{ entries: RegistryEntry[] }>(`/api/v2/registry-admin/entries${qs}`);
}

export async function deleteRegistryEntry(entryId: number, userId?: string) {
  const params = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return request<{ status: string; id: number }>(`/api/v2/registry-admin/entries/${entryId}${params}`, { method: "DELETE" });
}

export async function saveColumnTemplate(templateName: string, columns: ColumnDraft[], userId?: string) {
  return request<ColumnTemplate>("/api/v2/column-templates", {
    method: "POST",
    body: JSON.stringify({ template_name: templateName, columns, user_id: userId }),
  });
}

export async function listColumnTemplates(userId?: string) {
  const params = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return request<{ templates: ColumnTemplate[] }>(`/api/v2/column-templates${params}`);
}

export async function deleteColumnTemplate(templateId: number, userId?: string) {
  const params = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return request<{ status: string; id: number }>(`/api/v2/column-templates/${templateId}${params}`, { method: "DELETE" });
}

export async function matchColumnTemplates(columnNames: string[], userId?: string) {
  return request<{ matches: TemplateMatch[] }>("/api/v2/column-templates/match", {
    method: "POST",
    body: JSON.stringify({ column_names: columnNames, user_id: userId }),
  });
}

export async function saveAnswerTemplate(templateName: string, formatSpec: string, userId?: string) {
  return request<AnswerTemplate>("/api/v2/answer-templates", {
    method: "POST",
    body: JSON.stringify({ template_name: templateName, format_spec: formatSpec, user_id: userId }),
  });
}

export async function listAnswerTemplates(userId?: string) {
  const params = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return request<{ templates: AnswerTemplate[] }>(`/api/v2/answer-templates${params}`);
}

export async function deleteAnswerTemplate(templateId: number, userId?: string) {
  const params = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return request<{ status: string; id: number }>(`/api/v2/answer-templates/${templateId}${params}`, { method: "DELETE" });
}
