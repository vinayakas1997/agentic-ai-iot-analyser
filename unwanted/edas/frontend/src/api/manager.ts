import axios from "axios";
import type { MessageResponse, SessionDetail, SessionListItem } from "../types/manager";

const managerClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:7009",
});

export async function createSession(): Promise<{ session_id: string; status: string }> {
  const { data } = await managerClient.post("/manager/sessions");
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
