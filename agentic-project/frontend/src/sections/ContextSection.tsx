import { useState, useRef, useEffect, useMemo } from "react";
import { useSessionStore } from "../stores/sessionStore";
import { useDatasetStore } from "../stores/datasetStore";
import { useUploadStore } from "../stores/uploadStore";
import { useOutputStore } from "../stores/outputStore";
import type { SessionMeta } from "../types/manager";
import { panelClass, monoClass } from "../lib/styles";
import { IconDatabase, IconEdit, IconTrash } from "../lib/icons";
import { listDatasets, listUserDatasets, deleteUserDataset } from "../api/client";
import { DatasetColumns } from "../components/DatasetColumns";
import EditColumnsDialog from "../components/EditColumnsDialog";
import { useT } from "../lib/i18n";
import type { DatasetInfo, PersonalDataset } from "../types";

export default function ContextSection() {
  const t = useT();
  const sessionMeta = useSessionStore((s) => s.sessionMeta);
  const sessionId = useSessionStore((s) => s.sessionId);
  const isLocalSession = useSessionStore((s) => s.isLocalSession);
  const pendingTitle = useSessionStore((s) => s.pendingTitle);
  const turns = useSessionStore((s) => s.turns);
  const updateSessionTitle = useSessionStore((s) => s.updateSessionTitle);
  const setPendingTitle = useSessionStore((s) => s.setPendingTitle);

  const storeSelected = useDatasetStore((s) => s.selected);
  const storeRemove = useDatasetStore((s) => s.remove);
  const storeAttached = useDatasetStore((s) => s.attached);
  const storeAttach = useDatasetStore((s) => s.attach);
  const storeDetach = useDatasetStore((s) => s.detach);
  const lockedByAims = useDatasetStore((s) => s.lockedByAims);
  const storeRemoveWithAims = useDatasetStore((s) => s.removeWithAims);
  const selectedAims = useSessionStore((s) => s.selectedAims);
  const loading = useSessionStore((s) => s.loading);

  const [deletingDataset, setDeletingDataset] = useState<PersonalDataset | null>(null);

  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [personalDatasets, setPersonalDatasets] = useState<PersonalDataset[]>([]);
  const [expandedDataset, setExpandedDataset] = useState<string | null>(null);
  const [editingDataset, setEditingDataset] = useState<PersonalDataset | null>(null);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleInput, setTitleInput] = useState("");
  const titleInputRef = useRef<HTMLInputElement>(null);
  const personalDatasetsVersion = useUploadStore((s) => s.personalDatasetsVersion);

  useEffect(() => {
    listDatasets().then(setDatasets).catch((err) => console.error("Failed to load datasets:", err));
  }, []);

  useEffect(() => {
    listUserDatasets()
      .then((res) => setPersonalDatasets(res.datasets.filter((d) => d.status === "active")))
      .catch((err) => console.error("Failed to load personal datasets:", err));
  }, [personalDatasetsVersion]);

  const doDeletePersonalDataset = async (ds: PersonalDataset) => {
    try {
      await deleteUserDataset(ds.id);
      setPersonalDatasets((prev) => prev.filter((d) => d.id !== ds.id));
      storeRemoveWithAims(ds.dataset_name);
    } catch (err) {
      console.error("Failed to delete personal dataset:", err);
    }
  };

  const handleDeletePersonalDataset = (ds: PersonalDataset) => {
    const isInUse = storeAttached.includes(ds.dataset_name) ||
      selectedAims.some((a) => a.datasets?.includes(ds.dataset_name));
    if (isInUse) {
      setDeletingDataset(ds);
    } else {
      doDeletePersonalDataset(ds);
    }
  };

  const handleConfirmDeletePersonalDataset = async () => {
    if (!deletingDataset) return;
    const ds = deletingDataset;
    const dsName = ds.dataset_name;

    const aimsToRemove = selectedAims
      .filter((a) => a.datasets?.includes(dsName))
      .map((a) => a.aim);

    if (aimsToRemove.length > 0) {
      useSessionStore.setState((s) => ({
        selectedAims: s.selectedAims.filter((a) => !aimsToRemove.includes(a.aim)),
      }));
      useOutputStore.setState((s) => ({
        results: s.results.filter((r) => !aimsToRemove.includes(r.aim)),
      }));
    }

    await doDeletePersonalDataset(ds);
    setDeletingDataset(null);
  };

  const handleCancelDelete = () => setDeletingDataset(null);

  useEffect(() => {
    if (editingTitle && titleInputRef.current) {
      titleInputRef.current.focus();
      titleInputRef.current.select();
    }
  }, [editingTitle]);

  const handleTitleSave = () => {
    setEditingTitle(false);
    if (sessionMeta?.session_id && titleInput !== (sessionMeta.title || "")) {
      updateSessionTitle(sessionMeta.session_id, titleInput);
    } else if (isLocalSession && titleInput !== (pendingTitle || "")) {
      setPendingTitle(titleInput);
    }
  };

  const datasetLookup = useMemo(() => {
    const map = new Map<string, DatasetInfo>();
    for (const ds of datasets) {
      map.set(ds.dataset_name, ds);
    }
    return map;
  }, [datasets]);

  const selectedDatasetInfos = useMemo(
    () => storeSelected.map((name) => datasetLookup.get(name)).filter(Boolean) as DatasetInfo[],
    [storeSelected, datasetLookup]
  );

  const displaySession: SessionMeta | null = sessionMeta || (isLocalSession && pendingTitle ? { title: pendingTitle, session_id: sessionId || "", mode: "ask" as const, phase: "lines", status: "active" } : null);

  return (
    <section className={`${panelClass} order-1 lg:order-none overflow-y-auto text-sm`} data-tour="context-panel">
      <div className="flex items-center gap-2 text-xs font-semibold tracking-wider uppercase text-muted mb-3">
        <span className="inline-flex items-center justify-center w-[22px] h-[22px] rounded-[7px] bg-ic-violet-soft text-ic-violet">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="13" height="13" strokeWidth="2.2"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
        </span>
        {t("context.title")}
      </div>

      {displaySession && (
        <div className="rounded-xl border border-border bg-surface-1 p-4 mb-4 shadow-[0_1px_0_rgba(255,255,255,0.03)_inset,0_4px_6px_-4px_rgba(0,0,0,0.4),0_12px_32px_-16px_rgba(0,0,0,0.6)]">
          <div className="flex items-center gap-2 text-sm font-semibold text-text mb-3">
            <span className="inline-flex items-center justify-center w-[22px] h-[22px] rounded-[7px] bg-ic-blue-soft text-ic-blue">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="13" height="13" strokeWidth="2.2"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>
            </span>
            {t("context.session")}
          </div>
          <div className="flex items-center gap-1.5 mb-0.5">
            {editingTitle ? (
              <input
                ref={titleInputRef}
                type="text"
                className="flex-1 rounded-lg border border-accent bg-app text-text px-2 py-1 text-sm font-semibold"
                value={titleInput}
                onChange={(e) => setTitleInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleTitleSave();
                  if (e.key === "Escape") setEditingTitle(false);
                }}
                onBlur={handleTitleSave}
                maxLength={30}
              />
            ) : (
              <button
                type="button"
                className="flex items-center gap-1.5 text-sm font-semibold text-text group cursor-pointer"
                onClick={() => {
                  setTitleInput((sessionMeta && sessionMeta.title) || pendingTitle || "");
                  setEditingTitle(true);
                }}
              >
                <span>{displaySession.title || displaySession.session_id.slice(0, 8)}</span>
                <IconEdit size={11} className="opacity-50 text-muted" />
              </button>
            )}
          </div>
          <div className="text-[11.5px] text-tertiary mb-2">
            <span className={monoClass}>{displaySession.session_id}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[13px] text-muted">
              {t("context.turns")} <b className="text-text font-medium">{turns.length}</b>
            </span>
            <span className="text-muted">·</span>
            <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded border bg-ic-blue-soft text-ic-blue border-ic-blue/30">
              {displaySession.mode || "ask"}
            </span>
            {isLocalSession && (
              <span className="text-[10px] text-ic-amber font-semibold">{t("context.local")}</span>
            )}
          </div>
        </div>
      )}

      <div className="rounded-xl border border-border bg-surface-1 p-4 shadow-[0_1px_0_rgba(255,255,255,0.03)_inset,0_4px_6px_-4px_rgba(0,0,0,0.4),0_12px_32px_-16px_rgba(0,0,0,0.6)]">
        <div className="flex items-center gap-2 text-sm font-semibold text-text mb-3">
          <span className="inline-flex items-center justify-center w-[22px] h-[22px] rounded-[7px] bg-ic-amber-soft text-ic-amber">
            <IconDatabase size={13} />
          </span>
          {t("common.datasets")}
          {storeSelected.length > 0 && (
            <span className="text-tertiary font-normal text-xs">({storeSelected.length})</span>
          )}
        </div>
        {storeSelected.length === 0 ? (
          <p className="text-xs text-muted">{t("context.noDatasetsSelected")}</p>
        ) : (
          <div className="space-y-2">
            {selectedDatasetInfos.map((ds) => (
              <div key={ds.dataset_name} className="rounded-lg border border-border/40 bg-surface-2/50 shadow-[0_2px_6px_-3px_rgba(0,0,0,0.5),0_1px_0_rgba(255,255,255,0.03)_inset]">
                <div className="flex items-center gap-2 px-3 py-2">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-text truncate">{ds.dataset_name}</div>
                    <div className="text-[11px] text-tertiary truncate">
                      {ds.line_name}{ds.role ? ` · ${ds.role}` : ""}
                    </div>
                  </div>
                  <span className="text-[11px] text-muted shrink-0">{ds.column_definitions.length} cols</span>
                  <button
                    type="button"
                    className="text-[11px] font-medium px-2.5 py-1 rounded-full bg-white/5 text-muted hover:bg-white/10 hover:text-text border border-border/30 transition-all shrink-0"
                    onClick={() => setExpandedDataset(expandedDataset === ds.dataset_name ? null : ds.dataset_name)}
                  >
                    {expandedDataset === ds.dataset_name ? t("common.hide") : t("common.details")}
                  </button>
                  {storeAttached.includes(ds.dataset_name) ? (
                    lockedByAims.includes(ds.dataset_name) ? (
                      <span
                        className="text-[11px] font-medium px-2.5 py-1 rounded-full bg-ic-amber/15 text-ic-amber/60 border border-ic-amber/25 cursor-not-allowed shrink-0"
                        title={t("common.lockedByAim")}
                      >
                        {t("context.locked")}
                      </span>
                    ) : (
                      <button
                        type="button"
                        className="text-[11px] font-medium px-2.5 py-1 rounded-full bg-ic-teal/15 text-ic-teal border border-ic-teal/25 hover:bg-ic-teal/25 transition-all shrink-0"
                        onClick={() => storeDetach(ds.dataset_name)}
                      >
                        {t("common.inUse")}
                      </button>
                    )
                  ) : (
                    <button
                      type="button"
                      className="text-[11px] font-medium px-2.5 py-1 rounded-full bg-accent/15 text-accent border border-accent/25 hover:bg-accent/25 shadow-[0_1px_3px_-1px_rgba(0,0,0,0.3)] transition-all shrink-0"
                      onClick={() => storeAttach(ds.dataset_name)}
                    >
                      {t("common.use")}
                    </button>
                  )}
                  {!lockedByAims.includes(ds.dataset_name) && (
                    <button
                      type="button"
                      className="w-5 h-5 rounded-md bg-white/[0.04] hover:bg-red-500/15 hover:text-red-400 border border-border/20 transition-all shrink-0 flex items-center justify-center text-xs leading-none"
                      onClick={() => storeRemove(ds.dataset_name)}
                    >
                      ×
                    </button>
                  )}
                </div>
                {expandedDataset === ds.dataset_name && (
                  <div className="px-3 pb-3 space-y-2">
                    {ds.description && (
                      <div className="text-[11px] text-muted leading-relaxed bg-white/[0.02] rounded-lg px-3 py-2 border border-border/20 shadow-[inset_0_1px_1px_rgba(0,0,0,0.2)]">
                        {ds.description}
                      </div>
                    )}
                    <DatasetColumns columns={ds.column_definitions} />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-xl border border-border bg-surface-1 p-4 mt-4 shadow-[0_1px_0_rgba(255,255,255,0.03)_inset,0_4px_6px_-4px_rgba(0,0,0,0.4),0_12px_32px_-16px_rgba(0,0,0,0.6)]">
        <div className="flex items-center gap-2 text-sm font-semibold text-text mb-3">
          <span className="inline-flex items-center justify-center w-[22px] h-[22px] rounded-[7px] bg-ic-teal-soft text-ic-teal">
            <IconDatabase size={13} />
          </span>
          {t("context.personalDatasets")}
          {personalDatasets.length > 0 && (
            <span className="text-tertiary font-normal text-xs">({personalDatasets.length})</span>
          )}
        </div>
        {personalDatasets.length === 0 ? (
          <p className="text-xs text-muted">{t("context.noPersonalDatasets")}</p>
        ) : (
          <div className="space-y-2">
            {personalDatasets.map((ds) => (
              <div key={ds.id} className="rounded-lg border border-border/40 bg-surface-2/50 shadow-[0_2px_6px_-3px_rgba(0,0,0,0.5),0_1px_0_rgba(255,255,255,0.03)_inset]">
                <div className="flex items-center gap-2 px-3 py-2">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-text truncate">{ds.dataset_name}</div>
                    <div className="text-[11px] text-tertiary truncate">
                      {ds.original_filename} · {ds.row_count} rows
                    </div>
                  </div>
                  <span className="text-[11px] text-muted shrink-0">{ds.column_definitions.length} cols</span>
                  <button
                    type="button"
                    className="text-[11px] font-medium px-2.5 py-1 rounded-full bg-white/5 text-muted hover:bg-white/10 hover:text-text border border-border/30 transition-all shrink-0"
                    onClick={() => setExpandedDataset(expandedDataset === ds.dataset_name ? null : ds.dataset_name)}
                  >
                    {expandedDataset === ds.dataset_name ? t("common.hide") : t("common.details")}
                  </button>
                  {storeAttached.includes(ds.dataset_name) ? (
                    <button
                      type="button"
                      className="text-[11px] font-medium px-2.5 py-1 rounded-full bg-ic-teal/15 text-ic-teal border border-ic-teal/25 hover:bg-ic-teal/25 transition-all shrink-0"
                      onClick={() => storeDetach(ds.dataset_name)}
                    >
                      {t("common.inUse")}
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="text-[11px] font-medium px-2.5 py-1 rounded-full bg-accent/15 text-accent border border-accent/25 hover:bg-accent/25 shadow-[0_1px_3px_-1px_rgba(0,0,0,0.3)] transition-all shrink-0"
                      onClick={() => storeAttach(ds.dataset_name)}
                    >
                      {t("common.use")}
                    </button>
                  )}
                  <button
                    type="button"
                    className="w-5 h-5 rounded-md bg-white/[0.04] hover:bg-accent/15 hover:text-accent border border-border/20 transition-all shrink-0 flex items-center justify-center"
                    onClick={() => setEditingDataset(ds)}
                    title="Edit column meanings"
                  >
                    <IconEdit size={12} />
                  </button>
                  <button
                    type="button"
                    className={`w-5 h-5 rounded-md bg-white/[0.04] border border-border/20 transition-all shrink-0 flex items-center justify-center ${
                      loading && selectedAims.some((a) => a.datasets?.includes(ds.dataset_name))
                        ? "text-muted/30 cursor-not-allowed"
                        : "hover:bg-ic-amber/15 hover:text-ic-amber"
                    }`}
                    onClick={() => {
                      if (loading && selectedAims.some((a) => a.datasets?.includes(ds.dataset_name))) return;
                      handleDeletePersonalDataset(ds);
                    }}
                    title={
                      loading && selectedAims.some((a) => a.datasets?.includes(ds.dataset_name))
                        ? t("context.deleteWhileRunning")
                        : t("context.deleteDatasetTitle")
                    }
                  >
                    <IconTrash size={13} />
                  </button>
                </div>
                {expandedDataset === ds.dataset_name && (
                  <div className="px-3 pb-3 space-y-2">
                    {ds.description && (
                      <div className="text-[11px] text-muted leading-relaxed bg-white/[0.02] rounded-lg px-3 py-2 border border-border/20 shadow-[inset_0_1px_1px_rgba(0,0,0,0.2)]">
                        {ds.description}
                      </div>
                    )}
                    <DatasetColumns columns={ds.column_definitions} />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {editingDataset && (
        <EditColumnsDialog dataset={editingDataset} onClose={() => setEditingDataset(null)} />
      )}

      {deletingDataset && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="rounded-xl border border-border bg-surface-1 p-5 shadow-2xl max-w-sm w-full mx-4">
            <div className="flex items-center gap-3 mb-3">
              <span className="inline-flex items-center justify-center w-8 h-8 rounded-xl bg-ic-amber/15 text-ic-amber">
                <IconTrash size={16} />
              </span>
              <h3 className="text-sm font-semibold text-text">{t("context.deleteModalTitle")}</h3>
            </div>
            <p className="text-sm text-muted mb-5 whitespace-pre-line">
              {t("context.deleteWarning")}
            </p>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                className="px-3 py-1.5 text-sm rounded-lg border border-border text-muted hover:text-text transition-colors"
                onClick={handleCancelDelete}
              >
                {t("context.deleteCancelBtn")}
              </button>
              <button
                type="button"
                className="px-3 py-1.5 text-sm rounded-lg bg-ic-amber/15 text-ic-amber border border-ic-amber/25 hover:bg-ic-amber/25 transition-colors font-medium"
                onClick={handleConfirmDeletePersonalDataset}
              >
                {t("context.deleteConfirmBtn")}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
