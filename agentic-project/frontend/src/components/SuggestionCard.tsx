import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { monoClass, insightNoteClass, fieldLabelClass } from "../lib/styles";
import { IconDatabase, IconGrid, IconTarget } from "../lib/icons";
import { datasetColor } from "../lib/datasetColors";
import type { ParsedSuggestion } from "../lib/parseSuggestions";
import type { DatasetInfo } from "../types";

// Renders a single line of markdown (bold/italic) inline, without the block-level <p> wrapper
// react-markdown normally adds — the model often bolds column names inline (e.g. "grouping by **fruits_name**").
function InlineMarkdown({ text }: { text: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ p: ({ children }) => <>{children}</> }}>
      {text}
    </ReactMarkdown>
  );
}

export function SuggestionCard({ suggestion, index, datasets }: { suggestion: ParsedSuggestion; index: number; datasets?: DatasetInfo[] }) {
  // Show the real SQL table name, not the friendly dataset label — stay transparent about what's actually queried.
  const tableFor = (name: string) => datasets?.find((d) => d.dataset_name === name)?.table || name;

  return (
    <div className="rounded-xl border border-border/40 bg-surface-1/60 p-3 mb-2.5 last:mb-0">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-stage-manager/10 text-stage-manager text-[10px] font-bold shrink-0">
          {index + 1}
        </span>
        <h4 className="font-semibold text-sm text-text leading-snug">{suggestion.name}</h4>
      </div>

      {suggestion.goal && (
        <div className="flex items-start gap-1.5 text-[13px] text-text/80 mb-2 pl-0.5">
          <IconTarget size={12} className="mt-0.5 text-ic-amber shrink-0" />
          <span><InlineMarkdown text={suggestion.goal} /></span>
        </div>
      )}

      {suggestion.datasets.length > 0 && (
        <div className="mb-1.5">
          <div className={fieldLabelClass}>
            <IconDatabase size={11} />
            Datasets
          </div>
          <div className="flex flex-wrap gap-1">
            {suggestion.datasets.map((d, i) => {
              const table = tableFor(d);
              return (
                <span
                  key={i}
                  className={`${monoClass} text-[11px] px-2 py-0.5 rounded-full border ${datasetColor(d)}`}
                  title={table !== d ? `dataset: ${d}` : undefined}
                >
                  {table}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {suggestion.columns.length > 0 && (
        <div className="mb-2">
          <div className={fieldLabelClass}>
            <IconGrid size={11} />
            Columns
          </div>
          <div className="flex flex-wrap gap-1">
            {suggestion.columns.map((c, i) => (
              <span
                key={i}
                className={`${monoClass} text-[11px] px-2 py-0.5 rounded-full border border-border/50 text-muted bg-black/[0.03]`}
              >
                {c}
              </span>
            ))}
          </div>
        </div>
      )}

      {suggestion.explanation && (
        <p className="text-[13px] text-text/70 leading-relaxed mb-1.5">
          <InlineMarkdown text={suggestion.explanation} />
        </p>
      )}

      {suggestion.insight && (
        <p className={insightNoteClass}>
          <strong>Expected insight:</strong> <InlineMarkdown text={suggestion.insight} />
        </p>
      )}
    </div>
  );
}
