import { useState, useRef, useEffect, useMemo } from "react";
import { useSessionStore } from "../stores/sessionStore";
import { useDatasetStore } from "../stores/datasetStore";
import type { SessionMeta } from "../types/manager";
import { panelClass, monoClass } from "../lib/styles";
import { IconDatabase, IconEdit } from "../lib/icons";
import { listDatasets } from "../api/client";
import { DatasetColumns } from "../components/DatasetColumns";

interface DatasetInfo {
  line_name: string;
  dataset_name: string;
  description: string | null;
  table: string | null;
  column_definitions: { name: string; datatype: string; meaning?: string }[];
  role: string | null;
  join_hints: any;
  suggested_aims: any;
  synonyms: string[] | null;
}

export default function ContextSection() {
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

  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [expandedDataset, setExpandedDataset] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleInput, setTitleInput] = useState("");
  const titleInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    listDatasets().then(setDatasets).catch(() => {});
  }, []);

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
    <section className={`${panelClass} order-1 lg:order-none overflow-y-auto text-sm`}>
      <div className="flex items-center gap-2 text-xs font-semibold tracking-wider uppercase text-muted mb-3">
        <span className="inline-flex items-center justify-center w-[22px] h-[22px] rounded-[7px] bg-ic-violet-soft text-ic-violet">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="13" height="13" strokeWidth="2.2"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
        </span>
        Context
      </div>

      {displaySession && (
        <div className="rounded-xl border border-border bg-surface-1 p-4 mb-4 shadow-[0_1px_0_rgba(255,255,255,0.02)_inset,0_8px_24px_-12px_rgba(0,0,0,0.5)]">
          <div className="flex items-center gap-2 text-sm font-semibold text-text mb-3">
            <span className="inline-flex items-center justify-center w-[22px] h-[22px] rounded-[7px] bg-ic-blue-soft text-ic-blue">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="13" height="13" strokeWidth="2.2"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>
            </span>
            Session
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
              Turns: <b className="text-text font-medium">{turns.length}</b>
            </span>
            <span className="text-muted">·</span>
            <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded border bg-ic-blue-soft text-ic-blue border-ic-blue/30">
              {displaySession.mode || "ask"}
            </span>
            {isLocalSession && (
              <span className="text-[10px] text-ic-amber font-semibold">(local)</span>
            )}
          </div>
        </div>
      )}

      <div className="rounded-xl border border-border bg-surface-1 p-4 shadow-[0_1px_0_rgba(255,255,255,0.02)_inset,0_8px_24px_-12px_rgba(0,0,0,0.5)]">
        <div className="flex items-center gap-2 text-sm font-semibold text-text mb-3">
          <span className="inline-flex items-center justify-center w-[22px] h-[22px] rounded-[7px] bg-ic-amber-soft text-ic-amber">
            <IconDatabase size={13} />
          </span>
          Datasets
          {storeSelected.length > 0 && (
            <span className="text-tertiary font-normal text-xs">({storeSelected.length})</span>
          )}
        </div>
        {storeSelected.length === 0 ? (
          <p className="text-xs text-muted">No datasets selected. Search and select from the center panel.</p>
        ) : (
          <div className="space-y-2">
            {selectedDatasetInfos.map((ds) => (
              <div key={ds.dataset_name} className="rounded-lg border border-border/40 bg-surface-2/50">
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
                    className="text-[11px] font-medium text-accent hover:text-accent/80 transition-colors shrink-0"
                    onClick={() => setExpandedDataset(expandedDataset === ds.dataset_name ? null : ds.dataset_name)}
                  >
                    {expandedDataset === ds.dataset_name ? "Hide" : "Details"}
                  </button>
                  {storeAttached.includes(ds.dataset_name) ? (
                    lockedByAims.includes(ds.dataset_name) ? (
                      <span
                        className="text-[11px] font-medium text-ic-amber/60 cursor-not-allowed shrink-0"
                        title="Locked by a selected aim — remove the aim first"
                      >
                        Locked
                      </span>
                    ) : (
                      <button
                        type="button"
                        className="text-[11px] font-medium text-ic-teal hover:text-text transition-colors shrink-0"
                        onClick={() => storeDetach(ds.dataset_name)}
                      >
                        In-use
                      </button>
                    )
                  ) : (
                    <button
                      type="button"
                      className="text-[11px] font-medium text-accent hover:text-accent/80 transition-colors shrink-0"
                      onClick={() => storeAttach(ds.dataset_name)}
                    >
                      Use
                    </button>
                  )}
                  {!lockedByAims.includes(ds.dataset_name) && (
                    <button
                      type="button"
                      className="text-muted hover:text-text transition-colors shrink-0"
                      onClick={() => storeRemove(ds.dataset_name)}
                    >
                      ×
                    </button>
                  )}
                </div>
                {expandedDataset === ds.dataset_name && (
                  <div className="px-3 pb-3">
                    <DatasetColumns columns={ds.column_definitions} />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
