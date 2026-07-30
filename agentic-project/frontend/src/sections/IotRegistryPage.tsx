import { useState, useEffect, useCallback } from "react";
import { useAuthStore } from "../stores/authStore";
import { useT } from "../lib/i18n";
import { btnPrimary, btnSecondary } from "../lib/styles";
import { IconDatabase, IconCheck, IconTrash } from "../lib/icons";
import {
  introspectTable,
  createRegistryEntry,
  confirmRegistryEntry,
  listRegistryEntries,
  deleteRegistryEntry,
  type RegistryColumnDraft,
  type RegistryEntry,
} from "../api/client";

export default function IotRegistryPage({ onViewDashboard }: { onViewDashboard: () => void }) {
  const t = useT();
  const userId = useAuthStore((s) => s.userId);
  const logout = useAuthStore((s) => s.logout);

  const [lineName, setLineName] = useState("");
  const [datasetName, setDatasetName] = useState("");
  const [tableName, setTableName] = useState("");
  const [description, setDescription] = useState("");
  const [role, setRole] = useState("");
  const [synonyms, setSynonyms] = useState("");
  const [columns, setColumns] = useState<RegistryColumnDraft[] | null>(null);
  const [loadingCols, setLoadingCols] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [entries, setEntries] = useState<RegistryEntry[]>([]);

  const refreshEntries = useCallback(() => {
    if (!userId) return;
    listRegistryEntries(userId).then((res) => setEntries(res.entries)).catch((err) => console.error("Failed to load registry entries:", err));
  }, [userId]);

  useEffect(() => {
    refreshEntries();
  }, [refreshEntries]);

  const handleLoadColumns = async () => {
    if (!tableName.trim()) return;
    setLoadingCols(true);
    setError("");
    setColumns(null);
    try {
      const res = await introspectTable(tableName.trim(), userId || undefined);
      setColumns(res.columns);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("registryAdmin.tableNotFound"));
    } finally {
      setLoadingCols(false);
    }
  };

  const setMeaning = (name: string, meaning: string) => {
    setColumns((cols) => cols?.map((c) => (c.name === name ? { ...c, meaning } : c)) ?? null);
  };

  const resetForm = () => {
    setLineName("");
    setDatasetName("");
    setTableName("");
    setDescription("");
    setRole("");
    setSynonyms("");
    setColumns(null);
  };

  const handleSave = async (activate: boolean) => {
    if (!userId || !columns || !lineName.trim() || !datasetName.trim() || !tableName.trim()) return;
    setSaving(true);
    setError("");
    try {
      const created = await createRegistryEntry({
        maintained_by: userId,
        user_id: userId,
        line_name: lineName.trim(),
        dataset_name: datasetName.trim(),
        table_name: tableName.trim(),
        description,
        column_definitions: columns,
        role: role.trim() || undefined,
        synonyms: synonyms.trim() ? synonyms.split(",").map((s) => s.trim()).filter(Boolean) : undefined,
      });
      if (activate) {
        await confirmRegistryEntry(created.id, columns, description, userId || undefined);
      }
      resetForm();
      refreshEntries();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("login.error"));
    } finally {
      setSaving(false);
    }
  };

  const handleActivate = async (entry: RegistryEntry) => {
    try {
      await confirmRegistryEntry(entry.id, entry.column_definitions, entry.description || "", userId || undefined);
      refreshEntries();
    } catch (e) {
      console.error("Failed to activate entry:", e);
    }
  };

  const handleDelete = async (entry: RegistryEntry) => {
    try {
      await deleteRegistryEntry(entry.id, userId || undefined);
      setEntries((prev) => prev.filter((e) => e.id !== entry.id));
    } catch (e) {
      console.error("Failed to delete entry:", e);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-bg-deep text-text">
      <header className="flex items-center justify-between px-5 py-3 border-b border-border bg-surface-1 shrink-0">
        <span className="text-lg font-semibold">AGI DATA ANALYSER</span>
        <div className="flex items-center gap-3">
          <button type="button" className={btnSecondary} onClick={onViewDashboard}>
            {t("registryAdmin.viewDashboard")}
          </button>
          <button type="button" className={btnSecondary} onClick={logout}>
            {t("registryAdmin.logout")}
          </button>
        </div>
      </header>

      <main className="flex-1 min-h-0 overflow-y-auto p-6 max-w-3xl mx-auto w-full">
        <div className="flex items-center gap-2 mb-1">
          <span className="inline-flex items-center justify-center w-[26px] h-[26px] rounded-[8px] bg-ic-amber-soft text-ic-amber">
            <IconDatabase size={14} />
          </span>
          <div className="text-base font-semibold text-text">{t("registryAdmin.title")}</div>
        </div>
        <div className="text-[12px] text-tertiary mb-4">{t("registryAdmin.subtitle")}</div>

        <div className="rounded-xl border border-border bg-surface-1 p-4 mb-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <input
              type="text" placeholder={t("registryAdmin.lineName")}
              className="rounded-lg border border-border bg-app text-text px-3 py-2 text-sm focus:outline-none focus:border-accent"
              value={lineName} onChange={(e) => setLineName(e.target.value)}
            />
            <input
              type="text" placeholder={t("registryAdmin.datasetName")}
              className="rounded-lg border border-border bg-app text-text px-3 py-2 text-sm focus:outline-none focus:border-accent"
              value={datasetName} onChange={(e) => setDatasetName(e.target.value)}
            />
          </div>
          <div className="flex gap-2">
            <input
              type="text" placeholder={t("registryAdmin.tableName")}
              className="flex-1 rounded-lg border border-border bg-app text-text px-3 py-2 text-sm focus:outline-none focus:border-accent"
              value={tableName} onChange={(e) => setTableName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleLoadColumns()}
            />
            <button type="button" className={btnSecondary} onClick={handleLoadColumns} disabled={loadingCols || !tableName.trim()}>
              {loadingCols ? t("registryAdmin.loading") : t("registryAdmin.loadColumns")}
            </button>
          </div>

          {error && <div className="text-[12px] text-ic-amber">{error}</div>}

          {columns && (
            <>
              <div className="rounded-xl border border-border overflow-hidden">
                <table className="w-full table-fixed text-[13px]">
                  <colgroup>
                    <col className="w-[18%]" /><col className="w-[12%]" /><col className="w-[70%]" />
                  </colgroup>
                  <thead>
                    <tr className="bg-surface-2 text-[11px] uppercase tracking-wider text-muted">
                      <th className="text-left px-3 py-2 font-medium">{t("common.name")}</th>
                      <th className="text-left px-3 py-2 font-medium">{t("common.type")}</th>
                      <th className="text-left px-3 py-2 font-medium">{t("clarify.meaning")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {columns.map((col) => (
                      <tr key={col.name} className="border-t border-border/40">
                        <td className="px-3 py-2 font-mono text-[12px] text-text align-top break-words">{col.name}</td>
                        <td className="px-3 py-2 text-[11px] text-muted align-top">{col.datatype}</td>
                        <td className="px-3 py-2">
                          <input
                            type="text"
                            className="w-full rounded-lg border border-border bg-app text-text px-2 py-1.5 text-[13px] focus:outline-none focus:border-accent"
                            value={col.meaning}
                            onChange={(e) => setMeaning(col.name, e.target.value)}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <textarea
                placeholder={t("registryAdmin.description")}
                className="w-full rounded-lg border border-border bg-app text-text px-3 py-2 text-sm resize-none focus:outline-none focus:border-accent"
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
              <div className="grid grid-cols-2 gap-3">
                <input
                  type="text" placeholder={t("registryAdmin.role")}
                  className="rounded-lg border border-border bg-app text-text px-3 py-2 text-sm focus:outline-none focus:border-accent"
                  value={role} onChange={(e) => setRole(e.target.value)}
                />
                <input
                  type="text" placeholder={t("registryAdmin.synonyms")}
                  className="rounded-lg border border-border bg-app text-text px-3 py-2 text-sm focus:outline-none focus:border-accent"
                  value={synonyms} onChange={(e) => setSynonyms(e.target.value)}
                />
              </div>

              <div className="flex items-center justify-end gap-2">
                <button type="button" className={btnSecondary} onClick={() => handleSave(false)} disabled={saving}>
                  {saving ? t("registryAdmin.saving") : t("registryAdmin.saveDraft")}
                </button>
                <button type="button" className={`${btnPrimary} inline-flex items-center gap-1.5`} onClick={() => handleSave(true)} disabled={saving}>
                  <IconCheck size={13} />
                  {saving ? t("registryAdmin.saving") : t("registryAdmin.saveActivate")}
                </button>
              </div>
            </>
          )}
        </div>

        <div className="rounded-xl border border-border bg-surface-1 p-4">
          <div className="text-sm font-semibold text-text mb-3">{t("registryAdmin.yourEntries")}</div>
          {entries.length === 0 ? (
            <p className="text-xs text-muted">{t("registryAdmin.noEntries")}</p>
          ) : (
            <div className="space-y-2">
              {entries.map((entry) => (
                <div key={entry.id} className="flex items-center gap-2 rounded-lg border border-border/40 bg-surface-2/50 px-3 py-2">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-text truncate">{entry.dataset_name}</div>
                    <div className="text-[11px] text-tertiary truncate">{entry.line_name} · {entry.table}</div>
                  </div>
                  <span className={`text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded border ${entry.status === "active" ? "bg-ic-teal-soft/40 text-ic-teal border-ic-teal/30" : "bg-ic-amber-soft/40 text-ic-amber border-ic-amber/30"}`}>
                    {entry.status === "active" ? t("registryAdmin.statusActive") : t("registryAdmin.statusDraft")}
                  </span>
                  {entry.status !== "active" && (
                    <button type="button" className="text-[11px] font-medium text-accent hover:text-accent/80 transition-colors shrink-0" onClick={() => handleActivate(entry)}>
                      {t("registryAdmin.activate")}
                    </button>
                  )}
                  <button type="button" className="text-muted hover:text-ic-amber transition-colors shrink-0" onClick={() => handleDelete(entry)}>
                    <IconTrash size={13} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
