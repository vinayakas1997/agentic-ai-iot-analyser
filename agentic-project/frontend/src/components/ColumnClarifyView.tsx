import { useState } from "react";
import { useUploadStore } from "../stores/uploadStore";
import { useDatasetStore } from "../stores/datasetStore";
import { confirmUploadDataset } from "../api/client";
import { IconDatabase, IconCheck } from "../lib/icons";
import { btnPrimary, btnSecondary } from "../lib/styles";
import { useT } from "../lib/i18n";
import type { ColumnDraft } from "../types";

export default function ColumnClarifyView() {
  const t = useT();
  const pendingDrafts = useUploadStore((s) => s.pendingDrafts);
  const failures = useUploadStore((s) => s.failures);
  const closeClarify = useUploadStore((s) => s.closeClarify);
  const bumpPersonalDatasetsVersion = useUploadStore((s) => s.bumpPersonalDatasetsVersion);
  const storeAddMultiple = useDatasetStore((s) => s.addMultiple);
  const storeAttachMultiple = useDatasetStore((s) => s.attachMultiple);

  const [index, setIndex] = useState(0);
  const [editedColumns, setEditedColumns] = useState<ColumnDraft[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [confirmedNames, setConfirmedNames] = useState<string[]>([]);

  if (pendingDrafts.length === 0) {
    if (failures.length === 0) return null;
    // Only failures, nothing to clarify — show a dismissible error summary.
    return (
      <div className="fixed inset-0 z-50 bg-bg-deep/90 flex items-center justify-center p-6">
        <div className="rounded-2xl border-2 border-border bg-surface-1 p-6 max-w-lg w-full">
          <div className="text-sm font-semibold text-text mb-3">{t("clarify.uploadFailed")}</div>
          {failures.map((f) => (
            <div key={f.filename} className="mb-3">
              <div className="text-[13px] font-medium text-text">{f.filename}</div>
              {f.errors.map((e, i) => (
                <div key={i} className="text-[12px] text-ic-amber mt-0.5">{e}</div>
              ))}
            </div>
          ))}
          <button type="button" className={`${btnPrimary} w-full mt-2`} onClick={closeClarify}>
            {t("common.close")}
          </button>
        </div>
      </div>
    );
  }

  const current = pendingDrafts[index];
  const columns = editedColumns ?? current.columns;
  const isLast = index === pendingDrafts.length - 1;

  const setMeaning = (colName: string, meaning: string) => {
    setEditedColumns(columns.map((c) => (c.name === colName ? { ...c, meaning } : c)));
  };

  const handleAllSet = async () => {
    setSaving(true);
    setError("");
    try {
      await confirmUploadDataset(current.dataset_id, columns);
      const nextConfirmed = [...confirmedNames, current.dataset_name];
      setConfirmedNames(nextConfirmed);
      if (isLast) {
        storeAddMultiple(nextConfirmed);
        storeAttachMultiple(nextConfirmed);
        bumpPersonalDatasetsVersion();
        closeClarify();
      } else {
        setIndex(index + 1);
        setEditedColumns(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to confirm dataset");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-bg-deep/95 flex items-center justify-center p-6 overflow-y-auto">
      <div className="rounded-2xl border-2 border-border bg-surface-1 p-6 max-w-4xl w-full my-6">
        <div className="flex items-center gap-2 mb-1">
          <span className="inline-flex items-center justify-center w-[26px] h-[26px] rounded-[8px] bg-ic-amber-soft text-ic-amber">
            <IconDatabase size={14} />
          </span>
          <div className="text-base font-semibold text-text">{t("clarify.title")}</div>
        </div>
        <div className="text-[12px] text-tertiary mb-1">
          {current.filename} · table <span className="font-mono">{current.table_name}</span> · {current.row_count} rows
        </div>
        {pendingDrafts.length > 1 && (
          <div className="text-[11px] text-muted mb-4">
            {t("clarify.fileOf", { current: index + 1, total: pendingDrafts.length })}
          </div>
        )}
        {current.warnings.length > 0 && (
          <div className="mb-3 rounded-lg bg-ic-amber-soft/40 border border-ic-amber/30 px-3 py-2 text-[12px] text-ic-amber">
            {current.warnings.join(" · ")}
          </div>
        )}

        <div className="text-[11px] text-muted mb-3">
          {t("clarify.instructions")}
        </div>

        <div className="rounded-xl border border-border overflow-hidden mb-4">
          <table className="w-full table-fixed text-[13px]">
            <colgroup>
              <col className="w-[22%]" />
              <col className="w-[78%]" />
            </colgroup>
            <thead>
              <tr className="bg-surface-2 text-[11px] uppercase tracking-wider text-muted">
                <th className="text-left px-3 py-2 font-medium">{t("clarify.column")}</th>
                <th className="text-left px-3 py-2 font-medium">{t("clarify.meaning")}</th>
              </tr>
            </thead>
            <tbody>
              {columns.map((col) => (
                <tr key={col.name} className="border-t border-border/40">
                  <td className="px-3 py-2 font-mono text-[12px] text-text align-top break-words">{col.name}</td>
                  <td className="px-3 py-2">
                    <input
                      type="text"
                      className="w-full rounded-lg border border-border bg-app text-text px-2 py-1.5 text-[13px] focus:outline-none focus:border-accent transition-colors"
                      value={col.meaning}
                      onChange={(e) => setMeaning(col.name, e.target.value)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {error && <div className="text-[12px] text-ic-amber mb-3">{error}</div>}

        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            className={btnSecondary}
            onClick={() => {
              closeClarify();
              if (confirmedNames.length > 0) {
                storeAddMultiple(confirmedNames);
                storeAttachMultiple(confirmedNames);
                bumpPersonalDatasetsVersion();
              }
            }}
            disabled={saving}
          >
            {t("clarify.cancelRemaining")}
          </button>
          <button type="button" className={`${btnPrimary} inline-flex items-center gap-1.5`} onClick={handleAllSet} disabled={saving}>
            <IconCheck size={13} />
            {saving ? t("clarify.saving") : isLast ? t("clarify.allSet") : t("clarify.allSetNext")}
          </button>
        </div>
      </div>
    </div>
  );
}
