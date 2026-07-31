import { IconDatabase } from "../lib/icons";
import { btnSecondary } from "../lib/styles";
import { useT } from "../lib/i18n";
import type { DatasetInfo, PersonalDataset } from "../types";

interface Props {
  dataset: DatasetInfo | PersonalDataset;
  onClose: () => void;
}

function isPersonalDataset(ds: DatasetInfo | PersonalDataset): ds is PersonalDataset {
  return "row_count" in ds;
}

function suggestedAimsText(aims: any): string[] {
  if (!aims) return [];
  if (typeof aims === "string") return [aims];
  if (Array.isArray(aims)) {
    return aims.map((a) => {
      if (typeof a === "string") return a;
      if (a && typeof a === "object") return a.aim || a.description || JSON.stringify(a);
      return String(a);
    });
  }
  return [];
}

export default function DatasetDetailsDialog({ dataset, onClose }: Props) {
  const t = useT();
  const isPersonal = isPersonalDataset(dataset);

  const subtitle = isPersonal
    ? `${dataset.dataset_name} · ${dataset.original_filename} · ${dataset.row_count} rows`
    : `${dataset.line_name}${dataset.table ? ` · ${dataset.table}` : ""}`;

  const extra: { label: string; value: string[] }[] = [];
  if (!isPersonal) {
    if (dataset.role) extra.push({ label: t("context.datasetRole"), value: [dataset.role] });
    if (dataset.synonyms && dataset.synonyms.length > 0) extra.push({ label: t("context.datasetSynonyms"), value: dataset.synonyms });
    const aims = suggestedAimsText(dataset.suggested_aims);
    if (aims.length > 0) extra.push({ label: t("context.suggestedAimsLabel"), value: aims });
    if (dataset.join_hints) {
      const joinText = typeof dataset.join_hints === "string"
        ? dataset.join_hints
        : Array.isArray(dataset.join_hints)
          ? dataset.join_hints.map((j: any) => (typeof j === "string" ? j : JSON.stringify(j))).join("\n")
          : JSON.stringify(dataset.join_hints);
      if (joinText) extra.push({ label: t("context.datasetJoinHints"), value: joinText.split("\n").map((s) => s.trim()).filter(Boolean) });
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-bg-deep/95 flex items-center justify-center p-6 overflow-y-auto">
      <div className="rounded-2xl border-2 border-border bg-surface-1 p-6 max-w-4xl w-full my-6">
        <div className="flex items-center gap-2 mb-1">
          <span className="inline-flex items-center justify-center w-[26px] h-[26px] rounded-[8px] bg-ic-amber-soft text-ic-amber">
            <IconDatabase size={14} />
          </span>
          <div className="text-base font-semibold text-text">{t("context.datasetDetails")}</div>
        </div>
        <div className="text-[12px] text-tertiary mb-4">
          {subtitle}
          {!isPersonal && dataset.role ? ` · ${dataset.role}` : ""}
        </div>

        {dataset.description && (
          <div className="text-[12px] text-muted mb-4">
            <label className="block mb-1 text-[11px] font-medium text-tertiary uppercase tracking-wider">{t("common.description")}</label>
            <div className="rounded-lg border border-border bg-app text-text px-3 py-2 text-[13px] leading-relaxed whitespace-pre-wrap">
              {dataset.description}
            </div>
          </div>
        )}

        <div className="rounded-xl border border-border mb-4 max-h-[55vh] overflow-y-auto">
          <table className="w-full text-[13px]">
            <colgroup>
              <col className="w-[28%]" />
              <col className="w-[15%]" />
              <col className="w-[57%]" />
            </colgroup>
            <thead>
              <tr className="bg-surface-2 text-[11px] uppercase tracking-wider text-muted sticky top-0 z-10">
                <th className="text-left px-3 py-2 font-medium">{t("common.name")}</th>
                <th className="text-left px-3 py-2 font-medium">{t("common.type")}</th>
                <th className="text-left px-3 py-2 font-medium">{t("common.description")}</th>
              </tr>
            </thead>
            <tbody>
              {dataset.column_definitions.map((col) => (
                <tr key={col.name} className="border-t border-border/40 align-top">
                  <td className="px-3 py-2 font-mono text-[12px] text-text break-words whitespace-normal">
                    {col.name}
                  </td>
                  <td className="px-3 py-2">
                    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-surface-1 text-muted border border-border/30 whitespace-nowrap">
                      {col.datatype}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-muted whitespace-normal break-words">{col.meaning || ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {extra.length > 0 && (
          <div className="space-y-3 mb-4">
            {extra.map((item) => (
              <div key={item.label} className="text-[12px]">
                <label className="block mb-1 text-[11px] font-medium text-tertiary uppercase tracking-wider">{item.label}</label>
                <div className="flex flex-wrap gap-1.5">
                  {item.value.map((v, i) => (
                    <span
                      key={`${item.label}-${i}`}
                      className="text-[11px] font-medium px-2 py-1 rounded-full bg-white/[0.04] text-text border border-border/30"
                    >
                      {v}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center justify-end gap-2">
          <button type="button" className={btnSecondary} onClick={onClose}>
            {t("common.close")}
          </button>
        </div>
      </div>
    </div>
  );
}
