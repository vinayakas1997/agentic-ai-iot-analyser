import StatusBadge from "./StatusBadge";

export interface TaskResult {
  task?: string;
  status?: string;
  result?: {
    summary?: string;
    error?: string;
    [key: string]: unknown;
  };
}

export default function ResultCard({ result }: { result: TaskResult | null }) {
  if (!result) return null;
  const summary =
    result.result?.summary || result.result?.error || JSON.stringify(result.result);
  return (
    <div className="rounded-xl border border-border bg-panel p-4">
      <h2 className="text-base font-semibold mb-2 flex items-center gap-2">
        Result <StatusBadge status={result.status} />
      </h2>
      <p className="font-semibold text-sm">{result.task}</p>
      <p className="text-sm mt-2 whitespace-pre-wrap">{summary}</p>
    </div>
  );
}
