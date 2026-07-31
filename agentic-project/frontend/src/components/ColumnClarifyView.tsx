import { useState, useRef, useEffect } from "react";
import { useUploadStore } from "../stores/uploadStore";
import { useDatasetStore } from "../stores/datasetStore";
import { useUiStore } from "../stores/uiStore";
import { useAuthStore } from "../stores/authStore";
import { confirmUploadDataset, llmFillMeanings, saveColumnTemplate, listColumnTemplates, matchColumnTemplates } from "../api/client";
import { IconDatabase, IconCheck, IconUpload, IconChart, IconRobot, IconSave } from "../lib/icons";
import { btnPrimary, btnSecondary } from "../lib/styles";
import { useT } from "../lib/i18n";
import type { ColumnDraft, ColumnTemplate, TemplateMatch } from "../types";

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
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [confirmedNames, setConfirmedNames] = useState<string[]>([]);

  const [definitionsFileName, setDefinitionsFileName] = useState("");
  const [definitionsApplying, setDefinitionsApplying] = useState(false);
  const [definitionsError, setDefinitionsError] = useState("");
  const [llmFilling, setLlmFilling] = useState(false);

  const [templateList, setTemplateList] = useState<ColumnTemplate[]>([]);
  const [savingTemplate, setSavingTemplate] = useState(false);
  const [templateNameInput, setTemplateNameInput] = useState("");
  const [showTemplateInput, setShowTemplateInput] = useState(false);
  const [templateStatus, setTemplateStatus] = useState("");
  const [templateMatches, setTemplateMatches] = useState<TemplateMatch[]>([]);
  const [showMatchingBanner, setShowMatchingBanner] = useState(true);

  const definitionsInputRef = useRef<HTMLInputElement>(null);
  const tableRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (pendingDrafts.length === 0) return;
    const textareas = tableRef.current?.querySelectorAll("textarea");
    if (!textareas) return;
    textareas.forEach((el) => {
      const ta = el as HTMLTextAreaElement;
      ta.style.height = "auto";
      ta.style.height = ta.scrollHeight + "px";
    });
  }, [index, pendingDrafts]);

  useEffect(() => {
    setEditedColumns(null);
    setIndex(0);
    setDescription("");
    setConfirmedNames([]);
    setError("");
    setDefinitionsFileName("");
    setDefinitionsError("");
    setDefinitionsApplying(false);
    setTemplateMatches([]);
    setShowMatchingBanner(true);
    setShowTemplateInput(false);
    setTemplateNameInput("");
    setTemplateStatus("");
  }, [pendingDrafts]);

  // Load saved templates & auto-match columns when dialog opens with a valid draft
  useEffect(() => {
    if (pendingDrafts.length === 0) return;
    const draft = pendingDrafts[index];
    if (!draft) return;
    const columnNames = draft.columns.map((c) => c.original_name || c.name);
    const uid = useAuthStore.getState().userId || undefined;

    listColumnTemplates(uid).then((res) => {
      setTemplateList(res.templates);
    }).catch(() => {});

    matchColumnTemplates(columnNames, uid).then((res) => {
      if (res.matches.length > 0) {
        setTemplateMatches(res.matches);
      }
    }).catch(() => {});
  }, [index, pendingDrafts]);

  if (pendingDrafts.length === 0) {
    if (failures.length === 0) return null;
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
  const profiling = current.profiling ?? {};
  const isLast = index === pendingDrafts.length - 1;

  const emptyCount = columns.filter((c) => !c.meaning.trim()).length;
  const canProceed = emptyCount === 0;
  const hasDefinitions = definitionsFileName.length > 0;

  const setMeaning = (colName: string, meaning: string) => {
    setEditedColumns(columns.map((c) => (c.name === colName ? { ...c, meaning } : c)));
  };

  const handleTextareaResize = (e: React.FormEvent<HTMLTextAreaElement>) => {
    const el = e.currentTarget;
    el.style.height = "auto";
    el.style.height = el.scrollHeight + "px";
  };

  const handleDefinitionsFileSelected = (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    const cols = columns;
    const file = fileList[0];
    setDefinitionsApplying(true);
    setDefinitionsError("");
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      if (!text) {
        setDefinitionsError(t("clarify.defsError"));
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
      setEditedColumns(cols.map((col, i) => ({
        ...col,
        meaning: i < meanings.length ? meanings[i] : col.meaning,
      })));
      setDefinitionsApplying(false);
    };
    reader.onerror = () => {
      setDefinitionsError(t("clarify.defsError"));
      setDefinitionsApplying(false);
    };
    reader.readAsText(file);
  };

  const handleLlmFillEmpty = async () => {
    const emptyNames = columns.filter((c) => !c.meaning.trim()).map((c) => c.name);
    if (emptyNames.length === 0) return;
    const cols = columns;
    setLlmFilling(true);
    setDefinitionsError("");
    try {
      const language = useUiStore.getState().language;
      const uid = useAuthStore.getState().userId || undefined;
      const res = await llmFillMeanings(current.dataset_id, emptyNames, language, uid);
      const byName = new Map(res.columns.map((c) => [c.name, c.meaning]));
      setEditedColumns(cols.map((col) => ({
        ...col,
        meaning: byName.get(col.name) ?? col.meaning,
      })));
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
    setEditedColumns(cols.map((col) => {
      const match = byName.get(col.name.toLowerCase()) ?? byName.get((col.original_name || "").toLowerCase());
      return match !== undefined ? { ...col, meaning: match || col.meaning } : col;
    }));
    setTemplateStatus(t("clarify.templateApplied", { name: tmpl.template_name }));
  };

  const handleTemplateDropdownChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    if (!val) return;
    const tmpl = templateList.find((t) => String(t.id) === val);
    if (tmpl) applyTemplateColumns(tmpl);
  };

  const dismissMatchingBanner = () => setShowMatchingBanner(false);

  const handleAllSet = async () => {
    setSaving(true);
    setError("");
    try {
      const uid = useAuthStore.getState().userId || undefined;
      await confirmUploadDataset(current.dataset_id, columns, description, uid);
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
        setDescription("");
        setDefinitionsFileName("");
        setDefinitionsError("");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : t("upload.failedToConfirm"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-bg-deep/95 flex items-center justify-center p-6 overflow-y-auto" data-tour="clarify-modal">
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
        {failures.length > 0 && (
          <div className="mb-3 rounded-lg bg-ic-amber-soft/40 border border-ic-amber/30 px-3 py-2">
            <div className="text-[12px] font-semibold text-ic-amber mb-1">{t("clarify.uploadFailed")}</div>
            {failures.map((f) => (
              <div key={f.filename} className="text-[12px] text-ic-amber">
                <span className="font-medium">{f.filename}</span>
                {f.errors.length > 0 ? ` — ${f.errors.join("; ")}` : ""}
              </div>
            ))}
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

        {/* Dataset description */}
        <div className="mb-3">
          <label className="text-[11px] text-muted block mb-1">
            {t("clarify.description")}
          </label>
          <textarea
            className="w-full rounded-lg border border-border bg-app text-text px-3 py-2 text-[13px] focus:outline-none focus:border-accent transition-colors resize-none min-h-[40px] leading-tight"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={t("clarify.descriptionPlaceholder")}
            rows={2}
          />
        </div>

        {/* Definitions upload area */}
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
              <span className="text-[11px] text-tertiary mr-1">
                {definitionsFileName}
              </span>
              <button
                type="button"
                className="glass-pill glass-pill--upload"
                onClick={() => definitionsInputRef.current?.click()}
                disabled={definitionsApplying}
              >
                <IconUpload size={12} />
                {t("clarify.reuploadDefs")}
              </button>
            </>
          ) : (
            <button
              type="button"
              data-tour="upload-defs"
              className="glass-pill glass-pill--upload"
              onClick={() => definitionsInputRef.current?.click()}
              disabled={definitionsApplying}
            >
              <IconUpload size={12} />
              {t("clarify.uploadDefs")}
            </button>
          )}
          {emptyCount > 0 && (
            <button
              type="button"
              data-tour="llm-fill"
              className={`glass-pill glass-pill--llm ${llmFilling ? "cursor-wait" : ""}`}
              onClick={handleLlmFillEmpty}
              disabled={llmFilling}
            >
              <span className="robot-glow">
                <IconRobot size={13} />
              </span>
              {llmFilling ? (
                <>
                  <span className="inline-block animate-spin"><IconChart size={11} /></span>
                  {t("clarify.llmFilling")}
                </>
              ) : (
                t("clarify.llmFillEmpty")
              )}
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
              className={`glass-pill glass-pill--template ${editedColumns !== null ? "template-notify" : ""}`}
              onClick={() => setShowTemplateInput(true)}
            >
              <span className={editedColumns !== null ? "template-glow" : ""}>
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

        <div ref={tableRef} className="rounded-xl border border-border mb-4 max-h-[60vh] overflow-y-auto">
          <table className="w-full text-[13px]">
            <colgroup>
              <col className="w-[28%]" />
              <col className="w-[72%]" />
            </colgroup>
            <thead>
              <tr className="bg-surface-2 text-[11px] uppercase tracking-wider text-muted sticky top-0 z-10">
                <th className="text-left px-3 py-2 font-medium">{t("clarify.column")}</th>
                <th className="text-left px-3 py-2 font-medium">{t("clarify.meaning")}</th>
              </tr>
            </thead>
            <tbody>
              {columns.map((col) => {
                const p = profiling[col.name];
                const isEmpty = !col.meaning.trim();
                const badges: string[] = [];
                if (p) {
                  badges.push(p.datatype);
                  if (p.is_constant) badges.push("constant");
                  if (p.zero_pct != null && p.zero_pct > 0) badges.push(`${p.zero_pct}% zeros`);
                  if (p.null_pct > 0) badges.push(`${p.null_pct}% null`);
                  if (p.distinct_count <= 10) badges.push(`${p.distinct_count} values`);
                  else badges.push(`${p.distinct_count} unique`);
                }
                return (
                  <tr key={col.name} className="border-t border-border/40">
                    <td className="px-3 py-2 align-top break-words whitespace-normal">
                      <div className="font-mono text-[12px] text-text">
                        {col.original_name && col.original_name !== col.name ? (
                          <span title={col.name}>{col.original_name}</span>
                        ) : (
                          col.name
                        )}
                      </div>
                      {badges.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {badges.map((b) => (
                            <span
                              key={b}
                              className="inline-block rounded px-1.5 py-[1px] text-[10px] font-medium leading-tight bg-surface-2 text-tertiary"
                            >
                              {b}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <textarea
                        className={`w-full rounded-lg border bg-app text-text px-2 py-1.5 text-[13px] focus:outline-none focus:border-accent transition-colors resize-none overflow-hidden leading-tight whitespace-normal ${
                          isEmpty ? "border-ic-amber/60" : "border-border"
                        }`}
                        value={col.meaning}
                        onChange={(e) => setMeaning(col.name, e.target.value)}
                        onInput={handleTextareaResize}
                        rows={1}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {emptyCount > 0 && (
          <div className="mb-3 text-[12px] text-ic-amber">
            {t("upload.columnsNeedMeaning", { count: emptyCount })}
          </div>
        )}

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
          {!isLast && (
            <button
              type="button"
              className={btnSecondary}
              onClick={handleAllSet}
              disabled={saving || !canProceed}
            >
              {t("clarify.skip")}
            </button>
          )}
          <button
            type="button"
            className={`${btnPrimary} inline-flex items-center gap-1.5`}
            onClick={handleAllSet}
            disabled={saving || !canProceed}
          >
            <IconCheck size={13} />
            {saving ? t("clarify.saving") : isLast ? t("clarify.allSet") : t("clarify.allSetNext")}
          </button>
        </div>
      </div>
    </div>
  );
}
