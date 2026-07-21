import axios from "axios";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:7009";

const client = axios.create({ baseURL: API_URL });

export async function submitTask(task: string, dataSource = "sample.csv") {
  const { data } = await client.post("/task", { task, data_source: dataSource });
  return data;
}

export async function fetchResults() {
  const { data } = await client.get("/results");
  return data;
}

export async function fetchTasks() {
  const { data } = await client.get("/tasks");
  return data;
}

export { API_URL };
