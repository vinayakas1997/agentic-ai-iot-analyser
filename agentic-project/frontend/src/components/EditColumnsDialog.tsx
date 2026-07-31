import { useState, useRef, useEffect } from "react";
import { updateDatasetColumns, llmFillMeanings, saveColumnTemplate, listColumnTemplates, matchColumnTemplates } from "../api/client";
import { IconDatabase, IconCheck, IconSave } from "../lib/icons";
import { btnPrimary, btnSecondary } from "../lib/styles";
import { useUploadStore } from "../stores/uploadStore";
import { useUiStore } from "../stores/uiStore";
import { useAuthStore } from "../stores/authStore";
import { useT } from "../lib/i18n";
import type { ColumnDraft, PersonalDataset, ColumnTemplate, TemplateMatch } from "../types";

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

  const [templateList, setTemplateList] = useState<ColumnTemplate[]>([]);
  const [savingTemplate, setSavingTemplate] = useState(false);
  const [templateNameInput, setTemplateNameInput] = useState("");
  const [showTemplateInput, setShowTemplateInput] = useState(false);
  const [templateStatus, setTemplateStatus] = useState("");
  const [templateMatches, setTemplateMatches] = useState<TemplateMatch[]>([]);
  const [showMatchingBanner, setShowMatchingBanner] = useState(true);
  const [hasEdited, setHasEdited] = useState(false);

  const definitionsInputRef = useRef<HTMLInputElement>(null);

  const setMeaning = (colName: string, meaning: string) => {
    setColumns(columns.map((c) => (c.name === colName ? { ...c, meaning } : c)));
    setHasEdited(true);
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
        setDefinitionsError(t("upload.failedToRead"));
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
      setHasEdited(true);
      setDefinitionsApplying(false);
    };
    reader.onerror = () => {
      setDefinitionsError(t("upload.failedToRead"));
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
      const language = useUiStore.getState().language;
      const uid = useAuthStore.getState().userId || undefined;
      const res = await llmFillMeanings(dataset.id, emptyNames, language, uid);
      const byName = new Map(res.columns.map((c) => [c.name, c.meaning]));
      setColumns(columns.map((col) => ({
        ...col,
        meaning: byName.get(col.name) ?? col.meaning,
      })));
      setHasEdited(true);
    } catch (e) {
      setDefinitionsError(e instanceof Error ? e.message : t("upload.llmFillFailed"));
    } finally {
      setLlmFilling(false);
    }
  };

  const handleSaveTemplate = async () => {
    const name = templateNameInput.trim();
    if (!name) return;
    setSavingTemplate(true);
    setTemplateStatus("");
    try {
      const uid = useAuthStore.getState().userId || undefined;
      await saveColumnTemplate(name, columns, uid);
      setTemplateStatus(t("clarify.templateSaved"));
      setShowTemplateInput(false);
      setTemplateNameInput("");
      const res = await listColumnTemplates(uid);
      setTemplateList(res.templates);
    } catch {
      setTemplateStatus(t("upload.failedToSave"));
    } finally {
      setSavingTemplate(false);
    }
  };

  const applyTemplateColumns = (tmpl: ColumnTemplate | TemplateMatch) => {
    const cols = columns;
    const templateCols = "matched_columns" in tmpl ? tmpl.matched_columns : tmpl.column_definitions;
    const byName = new Map<string, string>();
    for (const tc of templateCols) {
      byName.set(tc.name.toLowerCase(), tc.meaning);
    }
    setColumns(cols.map((col) => {
      const match = byName.get(col.name.toLowerCase()) ?? byName.get((col.original_name || "").toLowerCase());
      return match !== undefined ? { ...col, meaning: match || col.meaning } : col;
    }));
    setHasEdited(true);
    setTemplateStatus(t("clarify.templateApplied", { name: tmpl.template_name }));
  };

  const handleTemplateDropdownChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    if (!val) return;
    const tmpl = templateList.find((t) => String(t.id) === val);
    if (tmpl) applyTemplateColumns(tmpl);
  };

  const dismissMatchingBanner = () => setShowMatchingBanner(false);

  const handleSave = async () => {
    setSaving(true);
    setError("");
    try {
      const uid = useAuthStore.getState().userId || undefined;
      await updateDatasetColumns(dataset.id, columns, description, uid);
      bumpPersonalDatasetsVersion();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("upload.failedToSave"));
    } finally {
      setSaving(false);
    }
  };

  const emptyCount = columns.filter((c) => !c.meaning.trim()).length;
  const hasDefinitions = definitionsFileName.length > 0;

  // Load templates & auto-match when dialog opens
  useEffect(() => {
    setTemplateMatches([]);
    setShowMatchingBanner(true);
    const uid = useAuthStore.getState().userId || undefined;
    const columnNames = columns.map((c) => c.original_name || c.name);

    listColumnTemplates(uid).then((res) => {
      setTemplateList(res.templates);
    }).catch(() => {});

    matchColumnTemplates(columnNames, uid).then((res) => {
      if (res.matches.length > 0) {
        setTemplateMatches(res.matches);
      }
    }).catch(() => {});
  }, [dataset.id]);

  return (
    <div className="fixed inset-0 z-50 bg-bg-deep/95 flex items-center justify-center p-6 overflow-y-auto">
      <div className="rounded-2xl border-2 border-border bg-surface-1 p-6 max-w-4xl w-full my-6">
        <div className="flex items-center gap-2 mb-1">
          <span className="inline-flex items-center justify-center w-[26px] h-[26px] rounded-[8px] bg-ic-amber-soft text-ic-amber">
            <IconDatabase size={14} />
          </span>
          <div className="text-base font-semibold text-text">{t("editColumns.title")}</div>
        </div>
        <div className="text-[12px] text-tertiary mb-4">
          {dataset.dataset_name} · {dataset.original_filename} · {dataset.row_count} rows
        </div>

        <div className="text-[12px] text-muted mb-3">
          <label className="block mb-1 text-[11px] font-medium text-tertiary uppercase tracking-wider">{t("editColumns.description")}</label>
          <textarea
            className="w-full rounded-lg border border-border bg-app text-text px-3 py-2 text-[13px] focus:outline-none focus:border-accent transition-colors resize-none leading-relaxed"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            placeholder={t("editColumns.descriptionPlaceholder")}
          />
        </div>
        <div className="text-[11px] text-muted mb-3">
          {t("editColumns.instruction")}
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
                {t("clarify.reuploadDefs")}
              </button>
            </>
          ) : (
            <button
              type="button"
              className="text-[11px] font-medium text-accent hover:text-accent/80 inline-flex items-center gap-1"
              onClick={() => definitionsInputRef.current?.click()}
              disabled={definitionsApplying}
            >
              {t("editColumns.uploadDefs")}
            </button>
          )}
          {emptyCount > 0 && (
            <button
              type="button"
              className="text-[11px] font-medium text-ic-amber hover:text-ic-amber/80"
              onClick={handleLlmFillEmpty}
              disabled={llmFilling}
            >
              {llmFilling ? "..." : t("editColumns.llmFill", { count: emptyCount })}
            </button>
          )}

          {/* Save Template */}
          {showTemplateInput ? (
            <div className="flex items-center gap-1.5">
              <input
                className="text-[11px] rounded-lg border border-border bg-app text-text px-2 py-1.5 w-[130px] focus:outline-none focus:border-[rgba(61,220,151,0.6)]"
                placeholder={t("clarify.templateNamePlaceholder")}
                value={templateNameInput}
                onChange={(e) => setTemplateNameInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") handleSaveTemplate(); }}
                autoFocus
              />
              <button
                type="button"
                className="inline-flex items-center gap-1 text-[11px] font-semibold text-black bg-[#3ddc97] hover:bg-[#4ee8a5] rounded-full px-2.5 py-1.5 transition-colors disabled:opacity-50"
                onClick={handleSaveTemplate}
                disabled={savingTemplate || !templateNameInput.trim()}
              >
                <IconSave size={12} />
                {savingTemplate ? "..." : t("clarify.saveTemplate")}
              </button>
              <button
                type="button"
                className="text-[11px] text-muted hover:text-text"
                onClick={() => { setShowTemplateInput(false); setTemplateNameInput(""); }}
              >
                {t("common.cancel")}
              </button>
            </div>
          ) : (
            <button
              type="button"
              className={`glass-pill glass-pill--template ${hasEdited ? "template-notify" : ""}`}
              onClick={() => setShowTemplateInput(true)}
            >
              <span className={hasEdited ? "template-glow" : ""}>
                <IconSave size={13} />
              </span>
              {t("clarify.saveTemplate")}
            </button>
          )}

          {/* Template dropdown */}
          <select
            className="text-[11px] rounded border border-border bg-app text-text px-2 py-1 max-w-[160px] focus:outline-none focus:border-accent"
            onChange={handleTemplateDropdownChange}
            defaultValue=""
          >
            <option value="" disabled>{templateList.length > 0 ? t("clarify.selectTemplate") : t("clarify.noTemplates")}</option>
            {templateList.map((tmpl) => (
              <option key={tmpl.id} value={tmpl.id}>{tmpl.template_name}</option>
            ))}
          </select>
        </div>

        {templateStatus && (
          <div className="mb-3 text-[12px] text-[#3ddc97]">{templateStatus}</div>
        )}

        {definitionsError && (
          <div className="mb-3 text-[12px] text-ic-amber">{definitionsError}</div>
        )}
        {error && (
          <div className="mb-3 text-[12px] text-ic-amber">{error}</div>
        )}

        {showMatchingBanner && templateMatches.length > 0 && (
          <div className="mb-3 rounded-lg bg-accent/10 border border-accent/30 px-3 py-2">
            <div className="flex items-center justify-between">
              <div className="text-[12px] font-medium text-accent">{t("clarify.matchingBanner")}</div>
              <button type="button" className="text-[11px] text-muted hover:text-text" onClick={dismissMatchingBanner}>
                {t("clarify.dismiss")}
              </button>
            </div>
            <div className="flex flex-wrap gap-2 mt-1">
              {templateMatches.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  className="text-[11px] bg-surface-2 hover:bg-surface-2/80 text-text rounded px-2 py-1 border border-border/40 transition-colors"
                  onClick={() => applyTemplateColumns(m)}
                  title={m.matched_columns.map((mc) => `${mc.name}: ${mc.meaning}`).join("\n")}
                >
                  {m.template_name} <span className="text-accent font-medium">{m.match_pct}%</span>
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="rounded-xl border border-border mb-4 max-h-[60vh] overflow-y-auto">
          <table className="w-full text-[13px]">
            <colgroup>
              <col className="w-[22%]" />
              <col className="w-[78%]" />
            </colgroup>
            <thead>
              <tr className="bg-surface-2 text-[11px] uppercase tracking-wider text-muted sticky top-0 z-10">
                <th className="text-left px-3 py-2 font-medium">{t("editColumns.column")}</th>
                <th className="text-left px-3 py-2 font-medium">{t("editColumns.meaning")}</th>
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
            {t("common.cancel")}
          </button>
          <button
            type="button"
            className={`${btnPrimary} inline-flex items-center gap-1.5`}
            onClick={handleSave}
            disabled={saving}
          >
            <IconCheck size={13} />
            {saving ? t("clarify.saving") : t("editColumns.save")}
          </button>
        </div>
      </div>
    </div>
  );
}
