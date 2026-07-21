import { FormEvent, useState } from "react";
import { submitTask } from "../../api/client";
import { btnPrimary } from "../../lib/styles";

export default function TaskInput({
  onSubmitted,
}: {
  onSubmitted?: (result: unknown) => void;
}) {
  const [task, setTask] = useState("");
  const [dataSource, setDataSource] = useState("sample.csv");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!task.trim()) return;
    setLoading(true);
    setError("");
    try {
      const result = await submitTask(task.trim(), dataSource.trim());
      onSubmitted?.(result);
      setTask("");
    } catch (err: unknown) {
      const detail =
        typeof err === "object" &&
        err !== null &&
        "response" in err &&
        typeof (err as { response?: { data?: { detail?: string } } }).response?.data?.detail ===
          "string"
          ? (err as { response: { data: { detail: string } } }).response.data.detail
          : "Failed to submit task";
      setError(detail);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl border border-border bg-panel p-4">
      <h2 className="text-base font-semibold mb-3">New analysis task</h2>
      <form className="flex flex-col gap-3" onSubmit={handleSubmit}>
        <textarea
          rows={3}
          className="rounded-lg border border-border bg-app text-text px-3 py-2 text-sm resize-y"
          placeholder="Describe what you want to analyze…"
          value={task}
          onChange={(e) => setTask(e.target.value)}
        />
        <input
          className="rounded-lg border border-border bg-app text-text px-3 py-2 text-sm"
          placeholder="Data source (CSV filename)"
          value={dataSource}
          onChange={(e) => setDataSource(e.target.value)}
        />
        {error && <p className="text-red-400 text-sm">{error}</p>}
        <button type="submit" className={btnPrimary} disabled={loading}>
          {loading ? "Submitting…" : "Submit task"}
        </button>
      </form>
    </div>
  );
}
