import { useState, useEffect, useRef } from "react";
import { btnPrimary, btnSecondary } from "../lib/styles";
import { useT } from "../lib/i18n";
import { useAuthStore } from "../stores/authStore";
import { saveAnswerTemplate, listAnswerTemplates, deleteAnswerTemplate, updateAnswerTemplate } from "../api/client";
import type { AnswerTemplate } from "../types";

const MAX_ANALYSES = 3;

interface AnalysisItem {
  analysis: string;
  explanation: string;
}

/** Split a stored format_spec back into its structured parts: numbered
 *  analysis lines (max MAX_ANALYSES) each with an optional per-analysis
 *  Explanation, plus the trailing Notes block. Legacy free-text templates
 *  (single shared Explanation) are converted here on edit. */
function parseSpec(spec: string): { analyses: AnalysisItem[]; explanation: string; notes: string } {
  const analyses: AnalysisItem[] = [];
  let sharedExplanation = "";
  const rest: string[] = [];
  let current: AnalysisItem | null = null;
  for (const line of spec.split("\n")) {
    const m = line.match(/^\s*\d+\s*[).\s]\s*(.+)$/);
    if (!m) {
      const trimmed = line.trim();
      if (current && /^Explanation:\s*(.+)$/i.test(trimmed)) {
        current.explanation = trimmed.replace(/^Explanation:\s*/i, "").trim();
        continue;
      }
      rest.push(line);
      continue;
    }
    const text = m[1].trim();
    const em = text.match(/^Explanation:\s*(.+)$/i);
    if (em) sharedExplanation = em[1].trim();
    else {
      current = { analysis: text, explanation: "" };
      analyses.push(current);
    }
  }
  const items = analyses.slice(0, MAX_ANALYSES);
  if (sharedExplanation) {
    if (items.length > 0) items[items.length - 1].explanation = sharedExplanation;
    else items.push({ analysis: "", explanation: sharedExplanation });
  }
  return {
    analyses: items.length > 0 ? items : [{ analysis: "", explanation: "" }],
    explanation: sharedExplanation,
    notes: rest.map((l) => l.trim()).filter(Boolean).join("\n"),
  };
}

/** Compose a stored format_spec from the structured editor state. */
function composeSpec(analyses: AnalysisItem[], notes: string): string {
  const clean = analyses.map((a) => ({ analysis: a.analysis.trim(), explanation: a.explanation.trim() })).filter((a) => a.analysis);
  const parts: string[] = [];
  for (const [i, a] of clean.entries()) {
    const block = `${i + 1}) ${a.analysis}`;
    parts.push(a.explanation ? `${block}\n   Explanation: ${a.explanation}` : block);
  }
  let spec = parts.join("\n");
  const n = notes.trim();
  if (n) spec += `\n\nNotes:\n${n}`;
  return spec;
}

export function FormatTemplateModal({
  open,
  onClose,
  onApply,
  demoTemplate,
}: {
  open: boolean;
  onClose: () => void;
  onApply: (template: AnswerTemplate) => void;
  demoTemplate?: AnswerTemplate | null;
}) {
  const t = useT();
  const userId = useAuthStore((s) => s.userId);
  const [templates, setTemplates] = useState<AnswerTemplate[]>([]);
  const [name, setName] = useState("");
  const [analyses, setAnalyses] = useState<AnalysisItem[]>([{ analysis: "", explanation: "" }]);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [status, setStatus] = useState<string>("");
  const nameInputRef = useRef<HTMLInputElement>(null);

  const reload = async () => {
    try {
      const res = await listAnswerTemplates(userId || undefined);
      setTemplates(res.templates || []);
    } catch (e) {
      console.error("Failed to load templates:", e);
    }
  };

  useEffect(() => {
    if (open) {
      setName("");
      setAnalyses([{ analysis: "", explanation: "" }]);
      setNotes("");
      setEditingId(null);
      setStatus("");
      reload();
    }
  }, [open]);

  const addAnalysis = () => {
    setAnalyses((a) => (a.length >= MAX_ANALYSES ? a : [...a, { analysis: "", explanation: "" }]));
  };

  const removeAnalysis = (idx: number) => {
    setAnalyses((a) => (a.length <= 1 ? a : a.filter((_, i) => i !== idx)));
  };

  const setAnalysis = (idx: number, field: keyof AnalysisItem, value: string) => {
    setAnalyses((a) => a.map((v, i) => (i === idx ? { ...v, [field]: value } : v)));
  };

  const handleSave = async () => {
    const trimmedName = name.trim();
    const spec = composeSpec(analyses, notes);
    if (!trimmedName || !spec) {
      setStatus(t("templateModal.fillBoth"));
      return;
    }
    setSaving(true);
    setStatus("");
    try {
      if (editingId != null) {
        await updateAnswerTemplate(editingId, trimmedName, spec, userId || undefined);
        setStatus(t("templateModal.updated"));
      } else {
        await saveAnswerTemplate(trimmedName, spec, userId || undefined);
        setStatus(t("templateModal.saved"));
      }
      setName("");
      setAnalyses([{ analysis: "", explanation: "" }]);
      setNotes("");
      setEditingId(null);
      await reload();
    } catch (e) {
      console.error("Failed to save template:", e);
      setStatus(t("templateModal.updateFailed"));
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (tmpl: AnswerTemplate) => {
    const parsed = parseSpec(tmpl.format_spec || "");
    setEditingId(tmpl.id);
    setName(tmpl.template_name);
    setAnalyses(parsed.analyses);
    setNotes(parsed.notes);
    setStatus("");
    setTimeout(() => nameInputRef.current?.focus(), 0);
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setName("");
    setAnalyses([{ analysis: "", explanation: "" }]);
    setNotes("");
    setStatus("");
  };

  const handleDelete = async (templateId: number) => {
    if (!window.confirm(t("templateModal.deleteConfirm"))) return;
    setDeletingId(templateId);
    try {
      await deleteAnswerTemplate(templateId, userId || undefined);
      await reload();
    } catch (e) {
      console.error("Failed to delete template:", e);
    } finally {
      setDeletingId(null);
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-surface-1 rounded-2xl border-2 border-border shadow-2xl w-full max-w-2xl mx-4 max-h-[85vh] overflow-y-auto"
        data-tour="template-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-border/50">
          <h3 className="text-base font-semibold text-text leading-tight pr-2">{t("templateModal.title")}</h3>
          <button
            type="button"
            className="shrink-0 w-7 h-7 flex items-center justify-center rounded-lg hover:bg-white/[0.06] text-muted hover:text-text transition-colors"
            onClick={onClose}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="16" height="16" strokeWidth="2.5"><path d="M18 6L6 18M6 6l12 12" /></svg>
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          <div>
            <div className="text-[10.5px] font-semibold tracking-wider uppercase text-tertiary mb-1.5">{t("templateModal.templateName")}</div>
            <input
              ref={nameInputRef}
              type="text"
              className="w-full rounded-xl border-2 border-border bg-surface-1 text-text text-sm px-3 py-2.5 focus:outline-none focus:border-accent transition-colors"
              placeholder={t("templateModal.namePlaceholder")}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <div className="text-[10.5px] font-semibold tracking-wider uppercase text-tertiary">{t("templateModal.analyses")}</div>
              <button
                type="button"
                className="text-[11px] font-medium text-accent hover:text-accent/80 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                disabled={analyses.length >= MAX_ANALYSES}
                onClick={addAnalysis}
              >
                {t("templateModal.addAnalysis")}
              </button>
            </div>
            {analyses.length === 0 ? (
              <div className="text-sm text-muted text-center py-3 rounded-xl border-2 border-dashed border-border/60">
                {t("templateModal.noAnalyses")}
              </div>
            ) : (
              <div className="space-y-3">
                {analyses.map((a, i) => (
                  <div key={i} className="rounded-xl border-2 border-border/60 bg-surface-2 p-3">
                    <div className="flex items-center justify-between mb-2">
                      <div className="w-5 shrink-0 text-right text-[12px] font-semibold text-tertiary">{i + 1})</div>
                      <button
                        type="button"
                        className="shrink-0 w-7 h-7 flex items-center justify-center rounded-lg text-muted hover:text-red-400 transition-colors"
                        title={t("templateModal.removeAnalysis")}
                        disabled={analyses.length <= 1}
                        onClick={() => removeAnalysis(i)}
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="14" height="14" strokeWidth="2">
                          <path d="M18 6L6 18M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                    <input
                      type="text"
                      className="w-full rounded-xl border-2 border-border bg-surface-1 text-text text-sm px-3 py-2.5 focus:outline-none focus:border-accent transition-colors"
                      placeholder={t("templateModal.analysisPlaceholder")}
                      value={a.analysis}
                      onChange={(e) => setAnalysis(i, "analysis", e.target.value)}
                    />
                    <div className="text-[10.5px] font-semibold tracking-wider uppercase text-ic-violet mt-3 mb-1.5">
                      {t("templateModal.explanationFor", { index: i + 1 })}
                    </div>
                    <textarea
                      className="w-full rounded-xl border-2 border-border bg-surface-1 text-text text-sm px-3 py-2.5 min-h-[56px] resize-y focus:outline-none focus:border-accent transition-colors"
                      placeholder={t("templateModal.explanationPlaceholder")}
                      value={a.explanation}
                      onChange={(e) => setAnalysis(i, "explanation", e.target.value)}
                    />
                    <p className="text-[11px] text-muted mt-1">{t("templateModal.explanationHint")}</p>
                  </div>
                ))}
              </div>
            )}
            <p className="text-[11px] text-muted mt-1">{t("templateModal.analysisHint")}</p>
          </div>

          <div>
            <div className="text-[10.5px] font-semibold tracking-wider uppercase text-tertiary mb-1.5">{t("templateModal.notes")}</div>
            <textarea
              className="w-full rounded-xl border-2 border-border bg-surface-1 text-text text-sm px-3 py-2.5 min-h-[72px] resize-y focus:outline-none focus:border-accent transition-colors"
              placeholder={t("templateModal.notesPlaceholder")}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
            <p className="text-[11px] text-muted mt-1">{t("templateModal.notesHint")}</p>
          </div>

          <div className="flex items-center justify-end gap-2">
            {editingId != null && (
              <button type="button" className={btnSecondary} onClick={handleCancelEdit} disabled={saving}>
                {t("templateModal.cancelEdit")}
              </button>
            )}
            <button type="button" className={btnPrimary} onClick={handleSave} disabled={saving}>
              {saving
                ? t("templateModal.saving")
                : editingId != null
                ? t("templateModal.update")
                : t("templateModal.save")}
            </button>
          </div>
          {status && <div className="text-[12px] text-accent">{status}</div>}

          <div>
            <div className="text-[10.5px] font-semibold tracking-wider uppercase text-tertiary mb-1.5">{t("templateModal.savedTemplates")}</div>
            {templates.length === 0 && !demoTemplate ? (
              <div className="text-sm text-muted text-center py-4 rounded-xl border border-border/40">
                {t("templateModal.noTemplates")}
              </div>
            ) : (
              <div className="space-y-1.5">
                {demoTemplate && (
                  <div
                    key="demo"
                    data-tour="template-row"
                    className="flex items-center gap-2 rounded-xl border-2 border-accent/50 bg-accent/5 px-3 py-2"
                  >
                    <button
                      type="button"
                      className="flex-1 min-w-0 text-left"
                      onClick={() => onApply(demoTemplate)}
                    >
                      <div className="text-sm font-medium text-text truncate">{demoTemplate.template_name}</div>
                      <div className="text-[11px] text-muted truncate whitespace-pre-line line-clamp-1">{demoTemplate.format_spec}</div>
                    </button>
                    <span className="shrink-0 text-[10px] font-semibold text-accent">DEMO</span>
                  </div>
                )}
                {templates.map((tmpl) => (
                  <div
                    key={tmpl.id}
                    className="flex items-center gap-2 rounded-xl border-2 border-border bg-surface-1 px-3 py-2 hover:border-accent/50 transition-colors"
                  >
                    <button
                      type="button"
                      className="flex-1 min-w-0 text-left"
                      onClick={() => onApply(tmpl)}
                    >
                      <div className="text-sm font-medium text-text truncate">{tmpl.template_name}</div>
                      <div className="text-[11px] text-muted truncate whitespace-pre-line line-clamp-1">{tmpl.format_spec}</div>
                    </button>
                      <button
                        type="button"
                        className="shrink-0 text-muted hover:text-accent transition-colors"
                        title={t("templateModal.edit")}
                        disabled={deletingId === tmpl.id || saving}
                        onClick={() => handleEdit(tmpl)}
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="15" height="15" strokeWidth="2">
                          <path d="M12 20h9M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z" />
                        </svg>
                      </button>
                      <button
                        type="button"
                        className="shrink-0 text-muted hover:text-red-400 transition-colors"
                        title={t("templateModal.delete")}
                        disabled={deletingId === tmpl.id}
                        onClick={() => handleDelete(tmpl.id)}
                      >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="15" height="15" strokeWidth="2">
                        <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6M10 11v6M14 11v6" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 px-5 pb-5 pt-2 border-t border-border/50">
          <button type="button" className={btnSecondary} onClick={onClose}>
            {t("common.close")}
          </button>
        </div>
      </div>
    </div>
  );
}
