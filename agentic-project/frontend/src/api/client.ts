const API = import.meta.env.VITE_API_URL || "http://localhost:7010";

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

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

export async function createSession(title?: string) {
  return request<{ session_id: string; title: string }>("/api/v2/sessions", {
    method: "POST",
    body: title ? JSON.stringify({ title }) : undefined,
  });
}

export async function listSessions() {
  return request<{ session_id: string; title: string; phase: string; status: string }[]>(
    "/api/v2/sessions"
  );
}

export async function getSession(sessionId: string) {
  return request<{
    session_id: string;
    title: string;
    phase: string;
    status: string;
    state: any;
    turns: { user: string; agent: string; timestamp: string }[];
  }>(`/api/v2/sessions/${sessionId}`);
}

export async function sendMessage(sessionId: string, message: string, lineName = "", attachedAims: string[] = [], enrichmentMode = "research", history?: { role: string; content: string }[]) {
  const body: Record<string, unknown> = { session_id: sessionId, message, line_name: lineName, attached_aims: attachedAims, enrichment_mode: enrichmentMode, history: history ?? [] };
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
    aim_proposals?: { aim: string; description: string; datasets: string[] }[];
    analysis_actions?: { name: string; description: string; datasets: string[] }[];
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

export async function reopenSession(sessionId: string) {
  return request<{ session_id: string; turns?: any[] }>(`/api/v2/sessions/${sessionId}/reopen`, {
    method: "POST",
  });
}

export async function forkSession(sessionId: string) {
  return request<{ session_id: string }>(`/api/v2/sessions/${sessionId}/fork`, {
    method: "POST",
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
