import axios from "axios";
import type { MessageResponse, SessionDetail, SessionListItem } from "../types/manager";

const managerClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:7009",
  timeout: 30000,
});

export async function createSession(title?: string): Promise<{ session_id: string; title: string | null; status: string }> {
  const { data } = await managerClient.post("/manager/sessions", title ? { title } : {});
  return data;
}

export async function listSessions(): Promise<SessionListItem[]> {
  const { data } = await managerClient.get("/manager/sessions");
  return data;
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  const { data } = await managerClient.get(`/manager/sessions/${sessionId}`);
  return data;
}

export async function sendMessage(
  sessionId: string,
  message: string,
  lineName = ""
): Promise<MessageResponse> {
  const { data } = await managerClient.post(`/manager/sessions/${sessionId}/messages`, {
    message,
    line_name: lineName,
  });
  return data;
}

export async function reopenSession(sessionId: string): Promise<SessionDetail> {
  const { data } = await managerClient.post(`/manager/sessions/${sessionId}/reopen`);
  return data;
}

export async function forkSession(sessionId: string): Promise<{ session_id: string }> {
  const { data } = await managerClient.post(`/manager/sessions/${sessionId}/fork`);
  return data;
}

export async function updateSessionTitle(
  sessionId: string,
  title: string
): Promise<{ session_id: string; title: string | null }> {
  const { data } = await managerClient.patch(`/manager/sessions/${sessionId}`, { title });
  return data;
}
