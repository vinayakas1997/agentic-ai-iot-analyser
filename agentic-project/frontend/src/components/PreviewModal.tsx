import { btnPrimary, btnSecondary, monoClass } from "../lib/styles";
import { IconGrid } from "../lib/icons";
import { datasetColor } from "../lib/datasetColors";
import { DatasetColumns } from "./DatasetColumns";
import type { DatasetInfo } from "../types";

interface Aim {
  aim: string;
  description?: string;
  benefits?: string;
  datasets?: string[];
  columns?: { dataset: string; names: string[] }[];
}

export function PreviewModal({
  aim,
  datasetLookup,
  expandedDataset,
  onToggleDataset,
  onUseAim,
  onClose,
  isAlreadyAdded,
}: {
  aim: Aim;
  datasetLookup: Map<string, DatasetInfo>;
  expandedDataset: string | null;
  onToggleDataset: (name: string) => void;
  onUseAim: () => void;
  onClose: () => void;
  isAlreadyAdded: boolean;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-surface-1 rounded-2xl border-2 border-border shadow-2xl w-full max-w-lg mx-4 max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-border/50">
          <h3 className="text-base font-semibold text-text leading-tight pr-2">{aim.aim}</h3>
          <button
            type="button"
            className="shrink-0 w-7 h-7 flex items-center justify-center rounded-lg hover:bg-white/[0.06] text-muted hover:text-text transition-colors"
            onClick={onClose}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="16" height="16" strokeWidth="2.5"><path d="M18 6L6 18M6 6l12 12" /></svg>
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          {aim.description && (
            <div className="rounded-xl border-l-3 border-l-ic-blue bg-ic-blue-soft/10 border border-border/40 p-3">
              <div className="flex items-center gap-1.5 text-[10.5px] font-semibold tracking-wider uppercase text-ic-blue mb-1">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="12" height="12" strokeWidth="2.2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
                Description
              </div>
              <p className="text-sm text-text leading-relaxed">{aim.description}</p>
            </div>
          )}

          {aim.benefits && (
            <div>
              <div className="text-[10.5px] font-semibold tracking-wider uppercase text-tertiary mb-1">Benefits</div>
              <p className="text-sm text-text/80 leading-relaxed">{aim.benefits}</p>
            </div>
          )}

          {aim.columns && aim.columns.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 text-[10.5px] font-semibold tracking-wider uppercase text-tertiary mb-1.5">
                <IconGrid size={11} />
                Columns used
              </div>
              <div className="flex flex-wrap gap-1">
                {aim.columns.map((c, i) =>
                  c.names.map((n) => (
                    <span
                      key={`${c.dataset}.${n}`}
                      className={`${monoClass} text-[11px] px-2 py-0.5 rounded-full border ${datasetColor(c.dataset)}`}
                    >
                      {n}
                    </span>
                  ))
                )}
              </div>
            </div>
          )}

          {aim.datasets && aim.datasets.length > 0 && (
            <div>
              <div className="text-[10.5px] font-semibold tracking-wider uppercase text-tertiary mb-1.5">Datasets</div>
              <div className="flex flex-wrap gap-1.5">
                {aim.datasets.map((dsName) => {
                  const ds = datasetLookup.get(dsName);
                  return (
                    <div key={dsName} className="flex items-center gap-1.5">
                      <span className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full border ${datasetColor(dsName)}`}>
                        {dsName}
                        <span className="opacity-60">({ds?.column_definitions?.length || 0} cols)</span>
                      </span>
                      {ds && ds.column_definitions?.length > 0 && (
                        <button
                          type="button"
                          className="text-[11px] font-medium text-accent hover:text-accent/80 transition-colors"
                          onClick={() => onToggleDataset(dsName)}
                        >
                          {expandedDataset === dsName ? "Hide" : "Details"}
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
              {aim.datasets.map((dsName) => {
                const ds = datasetLookup.get(dsName);
                if (!ds || expandedDataset !== dsName) return null;
                return (
                  <div key={`cols-${dsName}`} className="mt-2">
                    <DatasetColumns columns={ds.column_definitions} />
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 px-5 pb-5 pt-2 border-t border-border/50">
          <button type="button" className={btnSecondary} onClick={onClose}>
            Close
          </button>
          <button
            type="button"
            className={btnPrimary}
            onClick={onUseAim}
            disabled={isAlreadyAdded}
          >
            {isAlreadyAdded ? "Already added" : "Use this"}
          </button>
        </div>
      </div>
    </div>
  );
}
