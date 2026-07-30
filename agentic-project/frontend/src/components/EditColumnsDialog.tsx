import { useState, useRef } from "react";
import { updateDatasetColumns, llmFillMeanings } from "../api/client";
import { IconDatabase, IconCheck } from "../lib/icons";
import { btnPrimary, btnSecondary } from "../lib/styles";
import { useUploadStore } from "../stores/uploadStore";
import { useT } from "../lib/i18n";
import type { ColumnDraft, PersonalDataset } from "../types";

interface Props {
  dataset: PersonalDataset;
  onClose: () => void;
}

export default function EditColumnsDialog({ dataset, onClose }: Props) {
  const t = useT();
  const bumpPersonalDatasetsVersion = useUploadStore((s) => s.bumpPersonalDatasetsVersion);

  const [description, setDescription] = useState(dataset.description ?? "");
  const [columns, setColumns] = useState<ColumnDraft[]>(() =>
    dataset.column_definitions.map((c) => ({ ...c }))
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [llmFilling, setLlmFilling] = useState(false);
  const [definitionsFileName, setDefinitionsFileName] = useState("");
  const [definitionsApplying, setDefinitionsApplying] = useState(false);
  const [definitionsError, setDefinitionsError] = useState("");
  const definitionsInputRef = useRef<HTMLInputElement>(null);

  const setMeaning = (colName: string, meaning: string) => {
    setColumns(columns.map((c) => (c.name === colName ? { ...c, meaning } : c)));
  };

  const handleDefinitionsFileSelected = (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    const file = fileList[0];
    setDefinitionsApplying(true);
    setDefinitionsError("");
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      if (!text) {
        setDefinitionsError("Failed to read file");
        setDefinitionsApplying(false);
        return;
      }
      const lines = text.split(/\r?\n/).map((l) => l.trim()).filter((l) => l.length > 0);
      const meanings: string[] = [];
      for (const line of lines) {
        const commaIdx = line.indexOf(",");
        if (commaIdx >= 0) {
          meanings.push(line.slice(commaIdx + 1).trim());
        } else {
          meanings.push(line);
        }
      }
      setDefinitionsFileName(file.name);
      setColumns(columns.map((col, i) => ({
        ...col,
        meaning: i < meanings.length ? meanings[i] : col.meaning,
      })));
      setDefinitionsApplying(false);
    };
    reader.onerror = () => {
      setDefinitionsError("Failed to read file");
      setDefinitionsApplying(false);
    };
    reader.readAsText(file);
  };

  const handleLlmFillEmpty = async () => {
    const emptyNames = columns.filter((c) => !c.meaning.trim()).map((c) => c.name);
    if (emptyNames.length === 0) return;
    setLlmFilling(true);
    setDefinitionsError("");
    try {
      const res = await llmFillMeanings(dataset.id, emptyNames);
      const byName = new Map(res.columns.map((c) => [c.name, c.meaning]));
      setColumns(columns.map((col) => ({
        ...col,
        meaning: byName.get(col.name) ?? col.meaning,
      })));
    } catch (e) {
      setDefinitionsError(e instanceof Error ? e.message : "LLM fill failed");
    } finally {
      setLlmFilling(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError("");
    try {
      await updateDatasetColumns(dataset.id, columns, description);
      bumpPersonalDatasetsVersion();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const emptyCount = columns.filter((c) => !c.meaning.trim()).length;
  const hasDefinitions = definitionsFileName.length > 0;

  return (
    <div className="fixed inset-0 z-50 bg-bg-deep/95 flex items-center justify-center p-6 overflow-y-auto">
      <div className="rounded-2xl border-2 border-border bg-surface-1 p-6 max-w-4xl w-full my-6">
        <div className="flex items-center gap-2 mb-1">
          <span className="inline-flex items-center justify-center w-[26px] h-[26px] rounded-[8px] bg-ic-amber-soft text-ic-amber">
            <IconDatabase size={14} />
          </span>
          <div className="text-base font-semibold text-text">Edit Dataset</div>
        </div>
        <div className="text-[12px] text-tertiary mb-4">
          {dataset.dataset_name} · {dataset.original_filename} · {dataset.row_count} rows
        </div>

        <div className="text-[12px] text-muted mb-3">
          <label className="block mb-1 text-[11px] font-medium text-tertiary uppercase tracking-wider">Dataset Description</label>
          <textarea
            className="w-full rounded-lg border border-border bg-app text-text px-3 py-2 text-[13px] focus:outline-none focus:border-accent transition-colors resize-none leading-relaxed"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            placeholder="Describe what this dataset contains..."
          />
        </div>
        <div className="text-[11px] text-muted mb-3">
          Edit the dataset description and column meanings. Changes are saved immediately.
        </div>

        <div className="mb-3 flex flex-wrap items-center gap-2">
          <input
            ref={definitionsInputRef}
            type="file"
            accept=".csv,.txt"
            className="hidden"
            onChange={(e) => handleDefinitionsFileSelected(e.target.files)}
          />
          {hasDefinitions ? (
            <>
              <span className="text-[11px] text-tertiary mr-1">{definitionsFileName}</span>
              <button
                type="button"
                className="text-[11px] font-medium text-accent hover:text-accent/80 inline-flex items-center gap-1"
                onClick={() => definitionsInputRef.current?.click()}
                disabled={definitionsApplying}
              >
                Re-upload
              </button>
            </>
          ) : (
            <button
              type="button"
              className="text-[11px] font-medium text-accent hover:text-accent/80 inline-flex items-center gap-1"
              onClick={() => definitionsInputRef.current?.click()}
              disabled={definitionsApplying}
            >
              Upload definitions file
            </button>
          )}
          {emptyCount > 0 && (
            <button
              type="button"
              className="text-[11px] font-medium text-ic-amber hover:text-ic-amber/80"
              onClick={handleLlmFillEmpty}
              disabled={llmFilling}
            >
              {llmFilling ? "..." : `LLM fill ${emptyCount} empty`}
            </button>
          )}
        </div>

        {definitionsError && (
          <div className="mb-3 text-[12px] text-ic-amber">{definitionsError}</div>
        )}
        {error && (
          <div className="mb-3 text-[12px] text-ic-amber">{error}</div>
        )}

        <div className="rounded-xl border border-border mb-4 max-h-[60vh] overflow-y-auto">
          <table className="w-full text-[13px]">
            <colgroup>
              <col className="w-[22%]" />
              <col className="w-[78%]" />
            </colgroup>
            <thead>
              <tr className="bg-surface-2 text-[11px] uppercase tracking-wider text-muted sticky top-0 z-10">
                <th className="text-left px-3 py-2 font-medium">Column</th>
                <th className="text-left px-3 py-2 font-medium">Meaning</th>
              </tr>
            </thead>
            <tbody>
              {columns.map((col) => (
                <tr key={col.name} className="border-t border-border/40">
                  <td className="px-3 py-2 font-mono text-[12px] text-text align-top break-words whitespace-normal">
                    {col.original_name && col.original_name !== col.name ? (
                      <span title={col.name}>{col.original_name}</span>
                    ) : (
                      col.name
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <textarea
                      className="w-full rounded-lg border border-border bg-app text-text px-2 py-1.5 text-[13px] focus:outline-none focus:border-accent transition-colors resize-none min-h-[32px] leading-tight whitespace-normal"
                      value={col.meaning}
                      onChange={(e) => setMeaning(col.name, e.target.value)}
                      rows={1}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-end gap-2">
          <button type="button" className={btnSecondary} onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button
            type="button"
            className={`${btnPrimary} inline-flex items-center gap-1.5`}
            onClick={handleSave}
            disabled={saving}
          >
            <IconCheck size={13} />
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}
