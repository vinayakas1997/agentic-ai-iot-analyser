import type { ProcessingStep } from "../stores/sessionStore";
import { t } from "../lib/i18n";

interface Props {
  steps: ProcessingStep[];
}

function formatTime(ts: number): string {
  const secs = Math.floor((Date.now() / 1000 - ts) * 10) / 10;
  if (secs < 0.5) return "";
  if (secs < 60) return `${secs.toFixed(1)}s`;
  return `${Math.floor(secs / 60)}m${Math.floor(secs % 60)}s`;
}

function stepLabel(step: string): string {
  if (step.startsWith("agent_round_") || step.startsWith("agent_template_round_")) return t("processing.agent_round");
  if (step.startsWith("aim_")) return t("processing.aim_prefix");
  if (step.includes("llm")) return t("processing.thinking");
  if (step.includes("tool")) return t("processing.tool_call");
  const key = `processing.${step}`;
  const translated = t(key);
  if (translated !== key) return translated;
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
          <span className="text-text font-medium">{t("processing.processingLabel")}</span>
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
