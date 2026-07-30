import type { ProcessingStep } from "../stores/sessionStore";

interface Props {
  steps: ProcessingStep[];
}

function formatTime(ts: number): string {
  const secs = Math.floor((Date.now() / 1000 - ts) * 10) / 10;
  if (secs < 0.5) return "";
  if (secs < 60) return `${secs.toFixed(1)}s`;
  return `${Math.floor(secs / 60)}m${Math.floor(secs % 60)}s`;
}

const STEP_LABELS: Record<string, string> = {
  classifying: "Classifying question",
  building_context: "Analyzing dataset schema",
  processing: "Processing",
  llm: "Generating suggestions",
  generating_sql: "Generating SQL",
  validating_sql: "Validating SQL",
  executing_query: "Running query",
  building_charts: "Building chart suggestions",
  interpreting_results: "Interpreting results",
  focus_agent: "Running analysis agent",
};

function stepLabel(step: string): string {
  if (STEP_LABELS[step]) return STEP_LABELS[step];
  if (step.startsWith("agent_round_")) return "Agent analysis";
  if (step.startsWith("aim_")) return "Processing aim";
  if (step.includes("llm")) return "Thinking...";
  if (step.includes("tool")) return "Tool call";
  return step.replace(/_/g, " ");
}

function stepIcon(status: string) {
  if (status === "running") {
    return <span className="inline-block w-3 h-3 rounded-full bg-yellow-400 animate-pulse shrink-0" />;
  }
  if (status === "done") {
    return <span className="inline-block w-3 h-3 rounded-full bg-green-500 shrink-0" />;
  }
  return <span className="inline-block w-3 h-3 rounded-full border border-muted shrink-0" />;
}

export default function ProcessingPanel({ steps }: Props) {
  return (
    <div className="flex flex-col gap-0.5 text-xs text-muted py-3">
      {!steps.length ? (
        <div className="flex items-center gap-2">
          <span className="inline-block w-3 h-3 rounded-full bg-yellow-400 animate-pulse shrink-0" />
          <span className="text-text font-medium">Processing...</span>
        </div>
      ) : steps.map((s, i) => (
        <div key={`${s.step}-${i}`} className="flex items-start gap-2 leading-tight">
          <span className="mt-0.5">{stepIcon(s.status)}</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="font-medium text-text truncate">{stepLabel(s.step)}</span>
              {s.status === "running" && s.step === steps[steps.length - 1]?.step && (
                <span className="text-yellow-500 shrink-0">
                  {formatTime(s.ts)}
                </span>
              )}
              {s.status === "done" && (
                <span className="text-green-500 shrink-0">✓</span>
              )}
            </div>
            {s.detail && (
              <div className="truncate text-muted/70">{s.detail}</div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
