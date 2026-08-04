import { useState, useEffect, useRef } from "react";
import { btnPrimary, btnSecondary } from "../lib/styles";
import { useT } from "../lib/i18n";
import { useAuthStore } from "../stores/authStore";
import { saveAnswerTemplate, listAnswerTemplates, deleteAnswerTemplate, updateAnswerTemplate } from "../api/client";
import type { AnswerTemplate } from "../types";

export function FormatTemplateModal({
  open,
  onClose,
  onApply,
}: {
  open: boolean;
  onClose: () => void;
  onApply: (template: AnswerTemplate) => void;
}) {
  const t = useT();
  const userId = useAuthStore((s) => s.userId);
  const [templates, setTemplates] = useState<AnswerTemplate[]>([]);
  const [name, setName] = useState("");
  const [spec, setSpec] = useState("");
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
      setSpec("");
      setEditingId(null);
      setStatus("");
      reload();
    }
  }, [open]);

  const handleSave = async () => {
    const trimmedName = name.trim();
    const trimmedSpec = spec.trim();
    if (!trimmedName || !trimmedSpec) {
      setStatus(t("templateModal.fillBoth"));
      return;
    }
    setSaving(true);
    setStatus("");
    try {
      if (editingId != null) {
        await updateAnswerTemplate(editingId, trimmedName, trimmedSpec, userId || undefined);
        setStatus(t("templateModal.updated"));
      } else {
        await saveAnswerTemplate(trimmedName, trimmedSpec, userId || undefined);
        setStatus(t("templateModal.saved"));
      }
      setName("");
      setSpec("");
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
    setEditingId(tmpl.id);
    setName(tmpl.template_name);
    setSpec(tmpl.format_spec);
    setStatus("");
    setTimeout(() => nameInputRef.current?.focus(), 0);
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setName("");
    setSpec("");
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
        className="bg-surface-1 rounded-2xl border-2 border-border shadow-2xl w-full max-w-lg mx-4 max-h-[85vh] overflow-y-auto"
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
            <div className="text-[10.5px] font-semibold tracking-wider uppercase text-tertiary mb-1.5">{t("templateModal.formatSpec")}</div>
            <textarea
              className="w-full rounded-xl border-2 border-border bg-surface-1 text-text text-sm px-3 py-2.5 min-h-[140px] resize-y focus:outline-none focus:border-accent transition-colors"
              placeholder={t("templateModal.specPlaceholder")}
              value={spec}
              onChange={(e) => setSpec(e.target.value)}
            />
            <p className="text-[11px] text-muted mt-1">{t("templateModal.specHint")}</p>
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
            {templates.length === 0 ? (
              <div className="text-sm text-muted text-center py-4 rounded-xl border border-border/40">
                {t("templateModal.noTemplates")}
              </div>
            ) : (
              <div className="space-y-1.5">
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
