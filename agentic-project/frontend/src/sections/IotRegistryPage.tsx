import { useState, useEffect, useCallback, useRef } from "react";
import { useAuthStore } from "../stores/authStore";
import { useUiStore } from "../stores/uiStore";
import { useT } from "../lib/i18n";
import {
  IconDatabase,
  IconCheck,
  IconTrash,
  IconChevronRight,
  IconEye,
  IconUser,
  IconClock,
  IconUpload,
  IconRobot,
  IconSave,
  IconChart,
} from "../lib/icons";
import {
  createDbConnection,
  listDbConnections,
  deleteDbConnection,
  testDbConnection,
  listConnectionTables,
  introspectTable,
  registryLlmFill,
  registryDraftDescription,
  saveColumnTemplate,
  listColumnTemplates,
  matchColumnTemplates,
  createRegistryEntry,
  confirmRegistryEntry,
  listRegistryEntries,
  deleteRegistryEntry,
  type DbConnection,
  type ConnectionTestResult,
  type RegistryColumnDraft,
  type RegistryEntry,
  type IntrospectResult,
} from "../api/client";
import type { ColumnTemplate, TemplateMatch } from "../types";

// ── page-local design tokens ──
const inputCls =
  "w-full rounded-xl border border-border bg-app text-text px-3.5 py-2.5 text-[15px] focus:outline-none focus:border-accent/70 focus:shadow-[0_0_0_3px_rgba(124,111,239,0.15)] transition-colors placeholder:text-muted/60";
const fieldLabelCls = "text-xs font-semibold tracking-widest uppercase text-muted mb-1.5";
const btnPrimary =
  "inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-accent to-ic-blue text-white text-[15px] font-semibold px-5 py-2.5 shadow-[0_8px_24px_-8px_rgba(124,111,239,0.7)] hover:brightness-110 hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:scale-100 disabled:hover:brightness-100";
const btnSecondary =
  "inline-flex items-center justify-center gap-2 rounded-xl bg-white/[0.05] border border-border text-text text-[14px] font-medium px-4 py-2.5 hover:bg-white/[0.1] hover:border-white/25 hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0";
const panelCardCls =
  "relative rounded-2xl border border-border/70 bg-surface-1/90 backdrop-blur-sm p-5 shadow-[0_10px_40px_-24px_rgba(0,0,0,0.9)]";
const topAccent =
  "pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/70 to-transparent";

function SectionHeader({ icon, title, subtitle }: { icon: React.ReactNode; title: string; subtitle?: string }) {
  return (
    <div className="flex items-center gap-3 mb-4">
      <span className="inline-flex items-center justify-center w-9 h-9 rounded-[10px] bg-accent/15 border border-accent/30 text-accent shrink-0">
        {icon}
      </span>
      <div className="min-w-0">
        <div className="font-display text-[17px] font-semibold text-text leading-tight">{title}</div>
        {subtitle && <div className="text-[12.5px] text-muted mt-0.5 leading-snug">{subtitle}</div>}
      </div>
    </div>
  );
}

function StatusPill({ ok, error, latencyMs }: { ok: boolean; error?: string; latencyMs?: number }) {
  const t = useT();
  return (
    <span
      title={error}
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] font-medium border ${
        ok ? "bg-ic-teal-soft/50 border-ic-teal/30 text-ic-teal" : "bg-ic-red-soft/50 border-ic-red/30 text-ic-red"
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${ok ? "bg-ic-teal status-pulse" : "bg-ic-red"}`} />
      {ok ? `${t("conn.reachable")} · ${latencyMs ?? 0}ms` : `${t("conn.unreachable")} · ${(error || "").slice(0, 40)}`}
    </span>
  );
}

function ConnectionDetailsModal({ conn, onClose }: { conn: DbConnection; onClose: () => void }) {
  const t = useT();
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const fmtDate = (iso?: string | null) => (iso ? new Date(iso).toLocaleString() : "—");

  const rows: { label: string; icon?: React.ReactNode; value: React.ReactNode }[] = [
    { label: t("conn.host"), value: conn.host },
    { label: t("conn.port"), value: String(conn.port) },
    { label: t("conn.database"), value: conn.database_name },
    { label: t("conn.schema"), value: conn.schema_name ?? "—" },
    { label: t("conn.username"), value: conn.username },
    {
      label: t("conn.password"),
      value: (
        <span className="inline-flex items-center gap-2">
          <span className="font-mono">{showPassword ? conn.password ?? "" : "••••••••"}</span>
          <button
            type="button"
            onClick={() => setShowPassword((v) => !v)}
            className="text-muted hover:text-accent transition-colors"
            title={showPassword ? "Hide" : "Show"}
          >
            <IconEye size={15} />
          </button>
        </span>
      ),
    },
    { label: t("conn.createdAt"), icon: <IconClock size={12} />, value: fmtDate(conn.created_at) },
    { label: t("conn.createdBy"), icon: <IconUser size={12} />, value: conn.created_by ?? "—" },
  ];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm px-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md max-h-[85vh] overflow-y-auto rounded-2xl border border-border bg-surface-1 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-2 px-5 pt-5 pb-3 border-b border-border/50">
          <div className="flex items-center gap-2 min-w-0">
            <IconDatabase size={16} className="text-accent shrink-0" />
            <h3 className="font-display text-[16px] font-semibold text-text truncate">{conn.name}</h3>
            <span
              className={`shrink-0 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md ${
                conn.db_type === "mysql" ? "bg-ic-amber-soft/50 text-ic-amber" : "bg-ic-blue-soft/50 text-ic-blue"
              }`}
            >
              {conn.db_type}
            </span>
          </div>
          <button
            type="button"
            className="shrink-0 w-7 h-7 flex items-center justify-center rounded-lg hover:bg-white/[0.06] text-muted hover:text-text transition-colors"
            onClick={onClose}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="16" height="16" strokeWidth="2.5">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="px-5 py-4">
          <div className="rounded-xl border border-border/60 bg-app/60 divide-y divide-border/40">
            {rows.map((r) => (
              <div key={r.label} className="flex items-center justify-between gap-3 px-3.5 py-2.5">
                <span className="inline-flex items-center gap-1.5 text-[11.5px] font-semibold uppercase tracking-wider text-muted shrink-0">
                  {r.icon} {r.label}
                </span>
                <span className="text-[13.5px] text-text text-right min-w-0 truncate">{r.value}</span>
              </div>
            ))}
          </div>

          <div className="flex justify-end mt-4">
            <button type="button" className={btnSecondary} onClick={onClose}>
              {t("common.close")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function IotRegistryPage({ onViewDashboard }: { onViewDashboard: () => void }) {
  const t = useT();
  const userId = useAuthStore((s) => s.userId);
  const logout = useAuthStore((s) => s.logout);
  const language = useUiStore((s) => s.language);
  const setLanguage = useUiStore((s) => s.setLanguage);

  // ── connections state ──
  const [connections, setConnections] = useState<DbConnection[]>([]);
  const [connForm, setConnForm] = useState({
    name: "", dbType: "postgres", host: "", port: "5432", database: "", username: "", password: "", schema: "",
  });
  const [connSaving, setConnSaving] = useState(false);
  const [connError, setConnError] = useState("");
  const [testingId, setTestingId] = useState<number | null>(null);
  const [testResults, setTestResults] = useState<Record<number, ConnectionTestResult>>({});
  const [detailsConn, setDetailsConn] = useState<DbConnection | null>(null);

  // ── registration state ──
  const [connectionId, setConnectionId] = useState<number | null>(null);
  const [tables, setTables] = useState<string[]>([]);
  const [tablesLoading, setTablesLoading] = useState(false);
  const [tablesOpen, setTablesOpen] = useState(true);
  const [tableQuery, setTableQuery] = useState("");
  const [tableName, setTableName] = useState("");
  const [lineName, setLineName] = useState<string>(() => localStorage.getItem("iot-registry-last-linename") ?? "");
  const [datasetName, setDatasetName] = useState("");
  const [description, setDescription] = useState("");
  const [draftingDescription, setDraftingDescription] = useState(false);
  const [role, setRole] = useState("primary");
  const [synonyms, setSynonyms] = useState("");
  const [suggestedAims, setSuggestedAims] = useState<string[]>([]);
  const [aimInput, setAimInput] = useState("");
  const [editingAimIndex, setEditingAimIndex] = useState<number | null>(null);
  const [aimEditValue, setAimEditValue] = useState("");
  const [startDate, setStartDate] = useState("");
  const [startDateCol, setStartDateCol] = useState("");
  const [columns, setColumns] = useState<RegistryColumnDraft[] | null>(null);
  const [introspect, setIntrospect] = useState<IntrospectResult | null>(null);
  const [loadingCols, setLoadingCols] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [entries, setEntries] = useState<RegistryEntry[]>([]);

  // ── column toolbar state (mirrors CSV upload clarify view) ──
  const [columnQuery, setColumnQuery] = useState("");
  const [definitionsFileName, setDefinitionsFileName] = useState("");
  const [definitionsApplying, setDefinitionsApplying] = useState(false);
  const [definitionsError, setDefinitionsError] = useState("");
  const definitionsInputRef = useRef<HTMLInputElement>(null);
  const [llmFilling, setLlmFilling] = useState(false);
  const [meaningsEdited, setMeaningsEdited] = useState(false);
  const [templateList, setTemplateList] = useState<ColumnTemplate[]>([]);
  const [savingTemplate, setSavingTemplate] = useState(false);
  const [templateNameInput, setTemplateNameInput] = useState("");
  const [showTemplateInput, setShowTemplateInput] = useState(false);
  const [templateStatus, setTemplateStatus] = useState("");
  const [templateMatches, setTemplateMatches] = useState<TemplateMatch[]>([]);
  const [showMatchingBanner, setShowMatchingBanner] = useState(true);

  const refreshEntries = useCallback(() => {
    if (!userId) return;
    listRegistryEntries(userId).then((res) => setEntries(res.entries)).catch((err) => console.error("Failed to load registry entries:", err));
  }, [userId]);

  const refreshConnections = useCallback(() => {
    listDbConnections().then((res) => setConnections(res.connections)).catch((err) => console.error("Failed to load connections:", err));
  }, []);

  useEffect(() => {
    refreshEntries();
    refreshConnections();
  }, [refreshEntries, refreshConnections]);

  // ── connection handlers ──
  const handleAddConnection = async () => {
    const f = connForm;
    if (!f.name.trim() || !f.host.trim() || !f.database.trim() || !f.username.trim() || !f.password.trim()) {
      setConnError(t("conn.required"));
      return;
    }
    if (f.dbType !== "postgres" && f.dbType !== "mysql") {
      setConnError(t("conn.invalidType"));
      return;
    }
    setConnSaving(true);
    setConnError("");
    try {
      const created = await createDbConnection({
        name: f.name,
        db_type: f.dbType,
        host: f.host,
        port: parseInt(f.port || "0", 10) || (f.dbType === "mysql" ? 3306 : 5432),
        database_name: f.database,
        username: f.username,
        password: f.password,
        schema_name: f.schema || undefined,
        user_id: userId || undefined,
      });
      setConnForm({ name: "", dbType: "postgres", host: "", port: f.dbType === "mysql" ? "3306" : "5432", database: "", username: "", password: "", schema: "" });
      refreshConnections();
      const res = await testDbConnection(created.id, userId || undefined);
      setTestResults((prev) => ({ ...prev, [created.id]: res }));
    } catch (e) {
      setConnError(e instanceof Error ? e.message : t("conn.testFailed"));
    } finally {
      setConnSaving(false);
    }
  };

  const handleTestConnection = async (conn: DbConnection) => {
    setTestingId(conn.id);
    try {
      const res = await testDbConnection(conn.id, userId || undefined);
      setTestResults((prev) => ({ ...prev, [conn.id]: res }));
    } catch (e) {
      console.error("Test failed:", e);
    } finally {
      setTestingId(null);
    }
  };

  const handleDeleteConnection = async (conn: DbConnection) => {
    try {
      await deleteDbConnection(conn.id, userId || undefined);
      setConnections((prev) => prev.filter((c) => c.id !== conn.id));
      if (connectionId === conn.id) {
        setConnectionId(null);
        setTables([]);
        setTableName("");
        setColumns(null);
      }
    } catch (e) {
      console.error("Failed to delete connection:", e);
    }
  };

  // ── registration handlers ──
  const handleSelectConnection = async (id: number | null) => {
    setConnectionId(id);
    setTableName("");
    setTableQuery("");
    setTablesOpen(true);
    setColumns(null);
    setIntrospect(null);
    setStartDate("");
    setStartDateCol("");
    setTables([]);
    if (id == null) return;
    const conn = connections.find((c) => c.id === id);
    if (conn && !lineName.trim()) {
      setLineName(conn.name.toUpperCase());
      localStorage.setItem("iot-registry-last-linename", conn.name.toUpperCase());
    }
    setTablesLoading(true);
    try {
      const res = await listConnectionTables(id, userId || undefined);
      setTables(res.tables);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("registryAdmin.tableNotFound"));
    } finally {
      setTablesLoading(false);
    }
  };

  const draftDescription = async (tb: string, cols: RegistryColumnDraft[]) => {
    if (!cols.length) return;
    setDraftingDescription(true);
    try {
      const language = useUiStore.getState().language;
      const res = await registryDraftDescription(tb, cols, language, userId || undefined);
      if (res.description) setDescription(res.description);
    } catch (e) {
      console.error("Failed to draft description:", e);
    } finally {
      setDraftingDescription(false);
    }
  };

  const loadColumns = async (table: string): Promise<boolean> => {
    setLoadingCols(true);
    setError("");
    setColumns(null);
    setDescription("");
    setColumnQuery("");
    setDefinitionsFileName("");
    setDefinitionsError("");
    setTemplateNameInput("");
    setShowTemplateInput(false);
    setTemplateStatus("");
    setTemplateMatches([]);
    setShowMatchingBanner(true);
    setMeaningsEdited(false);
    try {
      const res = await introspectTable(table.trim(), userId || undefined, connectionId ?? undefined);
      setIntrospect(res);
      setColumns(res.columns);
      setDatasetName(table.trim());
      if (res.data_earliest_ts) {
        setStartDate(res.data_earliest_ts.slice(0, 10));
        setStartDateCol(res.data_earliest_col || "");
      } else {
        setStartDate("");
        setStartDateCol("");
      }
      void draftDescription(table.trim(), res.columns);
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : t("registryAdmin.tableNotFound"));
      return false;
    } finally {
      setLoadingCols(false);
    }
  };

  const handleSelectTable = async (tb: string) => {
    if (tb === tableName) return;
    setTableName(tb);
    const ok = await loadColumns(tb);
    if (ok) setTablesOpen(false);
  };

  // Load saved templates + auto-match when a table's columns load
  useEffect(() => {
    if (!columns || columns.length === 0) return;
    const columnNames = columns.map((c) => c.name);
    const uid = userId || undefined;
    setTemplateMatches([]);
    setShowMatchingBanner(true);
    listColumnTemplates(uid).then((res) => setTemplateList(res.templates)).catch(() => {});
    matchColumnTemplates(columnNames, uid).then((res) => {
      if (res.matches.length > 0) setTemplateMatches(res.matches);
    }).catch(() => {});
  }, [columns, userId]);

  const setMeaning = (name: string, meaning: string) => {
    setMeaningsEdited(true);
    setColumns((cols) => cols?.map((c) => (c.name === name ? { ...c, meaning } : c)) ?? null);
  };

  // ── column toolbar handlers (mirror CSV upload clarify view) ──

  const handleDefinitionsFileSelected = (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    const cols = columns;
    if (!cols) return;
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
      setColumns(cols.map((col, i) => ({
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
    if (!columns) return;
    const emptyNames = columns.filter((c) => !c.meaning.trim()).map((c) => c.name);
    if (emptyNames.length === 0) return;
    const cols = columns;
    setLlmFilling(true);
    setDefinitionsError("");
    try {
      const language = useUiStore.getState().language;
      const res = await registryLlmFill(
        tableName,
        emptyNames,
        introspect?.sample_rows ?? [],
        language,
        connectionId ?? undefined,
        userId || undefined,
      );
      const byName = new Map(res.columns.map((c) => [c.name, c.meaning]));
      setColumns(cols.map((col) => ({
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
    if (!name || !columns) return;
    setSavingTemplate(true);
    setTemplateStatus("");
    try {
      await saveColumnTemplate(name, columns, userId || undefined);
      setTemplateStatus(t("clarify.templateSaved"));
      setShowTemplateInput(false);
      setTemplateNameInput("");
      const res = await listColumnTemplates(userId || undefined);
      setTemplateList(res.templates);
    } catch {
      setTemplateStatus(t("upload.failedToSave"));
    } finally {
      setSavingTemplate(false);
    }
  };

  const applyTemplateColumns = (tmpl: ColumnTemplate | TemplateMatch) => {
    const cols = columns;
    if (!cols) return;
    const templateCols = "matched_columns" in tmpl ? tmpl.matched_columns : tmpl.column_definitions;
    const byName = new Map<string, string>();
    for (const tc of templateCols) {
      byName.set(tc.name.toLowerCase(), tc.meaning);
    }
    setColumns(cols.map((col) => {
      const match = byName.get(col.name.toLowerCase());
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

  const resetForm = () => {
    setDatasetName("");
    setTableName("");
    setDescription("");
    setRole("primary");
    setSynonyms("");
    setSuggestedAims([]);
    setAimInput("");
    setEditingAimIndex(null);
    setAimEditValue("");
    setStartDate("");
    setStartDateCol("");
    setColumns(null);
    setIntrospect(null);
  };

  const handleSave = async (activate: boolean) => {
    if (!userId || !columns || !lineName.trim() || !datasetName.trim() || !tableName.trim()) return;
    const dup = entries.find((e) => e.line_name === lineName.trim() && e.dataset_name === datasetName.trim());
    if (dup && !window.confirm(t("registryAdmin.duplicateEntry"))) return;
    const pendingAim = aimInput.trim();
    const aims = pendingAim
      ? suggestedAims.some((a) => a.toLowerCase() === pendingAim.toLowerCase())
        ? suggestedAims
        : [...suggestedAims, pendingAim]
      : suggestedAims;
    setSuggestedAims(aims);
    setAimInput("");
    setEditingAimIndex(null);
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
        suggested_aims: aims.length > 0 ? aims : undefined,
        connection_id: connectionId ?? undefined,
        data_earliest_ts: startDate.trim() ? startDate.trim() : undefined,
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

  const filteredTables = tableQuery.trim()
    ? tables.filter((tb) => tb.toLowerCase().includes(tableQuery.trim().toLowerCase()))
    : tables;

  const emptyCount = columns ? columns.filter((c) => !c.meaning.trim()).length : 0;
  const filteredColumns = columnQuery.trim() && columns
    ? columns.filter((c) => c.name.toLowerCase().includes(columnQuery.trim().toLowerCase()) || c.meaning.toLowerCase().includes(columnQuery.trim().toLowerCase()))
    : columns;

  return (
    <div className="flex flex-col h-screen bg-bg-deep text-text">
      <header className="shrink-0 z-30 flex items-center justify-between px-8 lg:px-10 py-3.5 border-b border-border bg-bg-deep/90 backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-ic-blue text-white shadow-[0_4px_16px_-4px_rgba(124,111,239,0.8)]">
            <IconDatabase size={15} />
          </span>
          <span className="font-display text-[15px] font-bold tracking-[0.08em] text-text">AGI DATA ANALYSER</span>
          <span className="hidden sm:inline-flex items-center gap-1 rounded-full bg-white/[0.05] border border-border px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-muted">
            <IconChevronRight size={10} /> {t("registryAdmin.title")}
          </span>
        </div>
        <div className="flex items-center gap-2.5">
          <div className="flex rounded-full border border-border bg-surface-1 overflow-hidden">
            <button
              type="button"
              className={`text-[11px] font-semibold px-2.5 py-1 transition-colors ${
                language === "en"
                  ? "bg-ic-amber text-black"
                  : "text-text hover:bg-white/[0.06]"
              }`}
              onClick={() => setLanguage("en")}
            >
              EN
            </button>
            <div className="w-px bg-border self-stretch" />
            <button
              type="button"
              className={`text-[11px] font-semibold px-2.5 py-1 transition-colors ${
                language === "ja"
                  ? "bg-ic-amber text-black"
                  : "text-text hover:bg-white/[0.06]"
              }`}
              onClick={() => setLanguage("ja")}
            >
              日本語
            </button>
          </div>
          <button type="button" className={btnSecondary} onClick={onViewDashboard}>
            {t("registryAdmin.viewDashboard")}
          </button>
          <button type="button" className={btnSecondary} onClick={logout}>
            {t("registryAdmin.logout")}
          </button>
        </div>
      </header>

      <main className="flex-1 min-h-0 overflow-y-auto w-full px-8 lg:px-10 py-7">
        <div className="flex items-center gap-3.5 mb-8">
          <span className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-gradient-to-br from-accent/25 to-ic-blue/15 border border-accent/30 text-accent shadow-[0_0_24px_-6px_rgba(124,111,239,0.6)]">
            <IconDatabase size={22} />
          </span>
          <div>
            <h1 className="font-display text-[26px] font-bold tracking-tight text-text leading-tight">{t("registryAdmin.title")}</h1>
            <p className="text-[13.5px] text-muted mt-0.5">{t("registryAdmin.subtitle")}</p>
          </div>
        </div>

        <div className="grid grid-cols-12 gap-6 items-start">
          {/* ── LEFT PANEL: database connections ── */}
          <div className={`${panelCardCls} col-span-12 lg:col-span-5 xl:col-span-4`}>
            <div className={topAccent} />
            <SectionHeader icon={<IconDatabase size={16} />} title={t("conn.title")} subtitle={t("conn.subtitle")} />

            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className={fieldLabelCls}>{t("conn.name")}</div>
                  <input type="text" className={inputCls} value={connForm.name} onChange={(e) => setConnForm({ ...connForm, name: e.target.value })} />
                </div>
                <div>
                  <div className={fieldLabelCls}>{t("conn.dbType")}</div>
                  <select
                    className={inputCls}
                    value={connForm.dbType}
                    onChange={(e) => setConnForm({ ...connForm, dbType: e.target.value, port: e.target.value === "mysql" ? "3306" : "5432" })}
                  >
                    <option value="postgres">PostgreSQL</option>
                    <option value="mysql">MySQL</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <div className={fieldLabelCls}>{t("conn.host")}</div>
                  <input type="text" className={inputCls} value={connForm.host} onChange={(e) => setConnForm({ ...connForm, host: e.target.value })} />
                </div>
                <div>
                  <div className={fieldLabelCls}>{t("conn.port")}</div>
                  <input type="text" className={inputCls} value={connForm.port} onChange={(e) => setConnForm({ ...connForm, port: e.target.value })} />
                </div>
              </div>
              <div>
                <div className={fieldLabelCls}>{t("conn.database")}</div>
                <input type="text" className={inputCls} value={connForm.database} onChange={(e) => setConnForm({ ...connForm, database: e.target.value })} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className={fieldLabelCls}>{t("conn.username")}</div>
                  <input type="text" className={inputCls} value={connForm.username} onChange={(e) => setConnForm({ ...connForm, username: e.target.value })} />
                </div>
                <div>
                  <div className={fieldLabelCls}>{t("conn.password")}</div>
                  <input type="password" className={inputCls} value={connForm.password} onChange={(e) => setConnForm({ ...connForm, password: e.target.value })} />
                </div>
              </div>
              <div>
                <div className={fieldLabelCls}>{t("conn.schema")}</div>
                <input type="text" className={inputCls} value={connForm.schema} onChange={(e) => setConnForm({ ...connForm, schema: e.target.value })} />
              </div>

              {connError && (
                <div className="flex items-center gap-2 rounded-xl border border-ic-amber/30 bg-ic-amber-soft/20 px-3.5 py-2.5 text-[13px] text-ic-amber">
                  {connError}
                </div>
              )}

              <button type="button" className={`${btnPrimary} w-full`} onClick={handleAddConnection} disabled={connSaving}>
                {connSaving ? (
                  <>
                    <span className="spinner" /> {t("conn.saving")}
                  </>
                ) : (
                  <>
                    <IconCheck size={16} /> {t("conn.addTest")}
                  </>
                )}
              </button>
            </div>

            <div className="pt-5 mt-5 border-t border-border/40">
              <div className="flex items-center justify-between mb-3">
                <div className="text-[14px] font-semibold text-text">{t("conn.savedConnections")}</div>
                {connections.length > 0 && (
                  <span className="inline-flex items-center justify-center min-w-[22px] h-[22px] px-1.5 rounded-full bg-accent/15 text-accent text-[11.5px] font-semibold">
                    {connections.length}
                  </span>
                )}
              </div>
              {connections.length === 0 ? (
                <div className="rounded-xl border border-dashed border-border/60 py-8 px-4 text-center">
                  <IconDatabase size={20} className="mx-auto mb-2 text-muted/50" />
                  <p className="text-[13px] text-muted">{t("conn.noConnections")}</p>
                </div>
              ) : (
                <div className="space-y-2.5">
                  {connections.map((conn) => {
                    const tr = testResults[conn.id];
                    return (
                      <div
                        key={conn.id}
                        className="group rounded-xl border border-border/60 bg-surface-2/60 hover:bg-surface-2 hover:border-white/20 transition-all px-4 py-3"
                      >
                        <div className="flex items-center gap-3">
                          <span
                            className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                              tr ? (tr.ok ? "bg-ic-teal shadow-[0_0_8px_rgba(79,216,196,0.9)] status-pulse" : "bg-ic-red shadow-[0_0_8px_rgba(255,107,107,0.9)]") : "bg-muted/40"
                            }`}
                          />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-[14.5px] font-semibold text-text truncate">{conn.name}</span>
                              <span
                                className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md ${
                                  conn.db_type === "mysql" ? "bg-ic-amber-soft/50 text-ic-amber" : "bg-ic-blue-soft/50 text-ic-blue"
                                }`}
                              >
                                {conn.db_type}
                              </span>
                            </div>
                            <div className="text-[12.5px] text-muted font-mono truncate mt-0.5">
                              {conn.host}:{conn.port}/{conn.database_name}
                            </div>
                          </div>
                          <button
                            type="button"
                            className="shrink-0 inline-flex items-center gap-1.5 rounded-lg bg-white/[0.05] hover:bg-accent/20 hover:text-accent border border-border/60 text-[12.5px] font-semibold px-3 py-1.5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            onClick={() => handleTestConnection(conn)}
                            disabled={testingId === conn.id}
                          >
                            {testingId === conn.id ? <span className="spinner" /> : <span className="w-1.5 h-1.5 rounded-full bg-accent" />}
                            {testingId === conn.id ? t("conn.testing") : t("conn.test")}
                          </button>
                          <button
                            type="button"
                            className="shrink-0 inline-flex items-center gap-1.5 rounded-lg bg-white/[0.05] hover:bg-accent/20 hover:text-accent border border-border/60 text-[12.5px] font-semibold px-3 py-1.5 transition-colors"
                            onClick={() => setDetailsConn(conn)}
                          >
                            <IconEye size={13} /> {t("conn.details")}
                          </button>
                          <button
                            type="button"
                            className="shrink-0 text-muted hover:text-ic-red hover:bg-ic-red/10 rounded-lg p-1.5 transition-colors"
                            onClick={() => handleDeleteConnection(conn)}
                            title="Delete connection"
                          >
                            <IconTrash size={15} />
                          </button>
                        </div>
                        {tr && (
                          <div className="mt-2.5 flex items-center gap-2">
                            <StatusPill ok={tr.ok} error={tr.error} latencyMs={tr.latency_ms} />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* ── RIGHT PANEL: dataset registration ── */}
          <div className={`${panelCardCls} col-span-12 lg:col-span-7 xl:col-span-8`}>
            <div className={topAccent} />
            <SectionHeader icon={<IconDatabase size={16} />} title={t("registryAdmin.connection")} />

            <select
              className={`${inputCls} mb-4`}
              value={connectionId ?? ""}
              onChange={(e) => handleSelectConnection(e.target.value ? parseInt(e.target.value, 10) : null)}
            >
              <option value="">{t("registryAdmin.mainDb")}</option>
              {connections.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.db_type})
                </option>
              ))}
            </select>

            <div className="flex items-center justify-between mb-1.5">
              <div className={fieldLabelCls}>{t("registryAdmin.tableName")}</div>
              {!tablesLoading && tables.length > 0 && (
                <span className="inline-flex items-center justify-center min-w-[22px] h-[22px] px-1.5 rounded-full bg-accent/15 text-accent text-[11.5px] font-semibold">
                  {tables.length}
                </span>
              )}
            </div>

            {tablesOpen ? (
              <>
                <input
                  type="text"
                  className={`${inputCls} disabled:opacity-50 disabled:cursor-not-allowed`}
                  value={tableQuery}
                  onChange={(e) => setTableQuery(e.target.value)}
                  placeholder={tablesLoading ? t("registryAdmin.loading") : t("registryAdmin.searchTables")}
                  disabled={connectionId == null || tablesLoading}
                />

                <div className="mt-2 max-h-64 overflow-y-auto rounded-xl border border-border/70 bg-app/60">
                  {connectionId == null ? (
                    <div className="px-3.5 py-8 text-center text-[13px] text-muted">
                      <IconDatabase size={18} className="mx-auto mb-2 text-muted/50" />
                      {t("registryAdmin.selectConnFirst")}
                    </div>
                  ) : tablesLoading ? (
                    <div className="flex items-center justify-center gap-2 px-3.5 py-8 text-[13px] text-muted">
                      <span className="spinner" /> {t("registryAdmin.loading")}
                    </div>
                  ) : filteredTables.length === 0 ? (
                    <div className="px-3.5 py-8 text-center text-[13px] text-muted">
                      {t("registryAdmin.noTables")}
                    </div>
                  ) : (
                    <div className="divide-y divide-border/40">
                      {filteredTables.map((tb) => (
                        <button
                          key={tb}
                          type="button"
                          onClick={() => handleSelectTable(tb)}
                          className={`w-full flex items-center justify-between gap-2 text-left px-3.5 py-2.5 text-[13.5px] transition-colors hover:bg-accent/15 ${
                            tableName === tb
                              ? "bg-accent/10 text-accent font-medium"
                              : loadingCols
                                ? "opacity-50"
                                : "text-text/90"
                          }`}
                        >
                          <span className="font-mono truncate">{tb}</span>
                          {tableName === tb && loadingCols ? (
                            <span className="spinner" />
                          ) : tableName === tb ? (
                            <IconCheck size={15} className="shrink-0" />
                          ) : null}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </>
            ) : (
              <button
                type="button"
                onClick={() => setTablesOpen(true)}
                className="w-full flex items-center gap-2 rounded-xl border border-border bg-app text-text px-3.5 py-2.5 text-[15px] transition-colors hover:border-accent/70"
              >
                <span className="flex-1 min-w-0 truncate font-mono text-left">{tableName}</span>
                <span className="shrink-0 inline-flex items-center gap-1 text-[12px] font-semibold text-accent">
                  <IconChevronRight size={13} className="rotate-90" /> {t("registryAdmin.changeTable")}
                </span>
              </button>
            )}

            {error && (
              <div className="mt-3 flex items-center gap-2 rounded-xl border border-ic-amber/30 bg-ic-amber-soft/20 px-3.5 py-2.5 text-[13px] text-ic-amber">
                {error}
              </div>
            )}

            {columns && (
              <div className="mt-5 space-y-4">
                {/* ── column toolbar ── */}
                <div className="space-y-3">
                  <input
                    type="text"
                    className={inputCls}
                    value={columnQuery}
                    onChange={(e) => setColumnQuery(e.target.value)}
                    placeholder={t("registryAdmin.searchColumns")}
                  />

                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      ref={definitionsInputRef}
                      type="file"
                      accept=".csv,.txt"
                      className="hidden"
                      onChange={(e) => handleDefinitionsFileSelected(e.target.files)}
                    />
                    {definitionsFileName ? (
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

                    <span className="relative inline-flex group">
                      <button
                        type="button"
                        data-tour="llm-fill"
                        className={`glass-pill glass-pill--llm ${llmFilling ? "cursor-wait" : ""}`}
                        onClick={handleLlmFillEmpty}
                        disabled={llmFilling || emptyCount === 0}
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
                      {emptyCount === 0 && (
                        <span className="pointer-events-none absolute bottom-full mb-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-lg border border-border/60 bg-surface-2 px-3 py-1.5 text-[22px] text-muted opacity-0 transition-opacity duration-150 group-hover:opacity-100 z-20 shadow-lg">
                          {t("clarify.noEmptyToFill")}
                        </span>
                      )}
                    </span>

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
                        className={`glass-pill glass-pill--template ${meaningsEdited ? "template-notify" : ""}`}
                        onClick={() => setShowTemplateInput(true)}
                      >
                        <span className={meaningsEdited ? "template-glow" : ""}>
                          <IconSave size={13} />
                        </span>
                        {t("clarify.saveTemplate")}
                      </button>
                    )}

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
                    <div className="text-[12px] text-[#3ddc97]">{templateStatus}</div>
                  )}
                  {definitionsError && (
                    <div className="text-[12px] text-ic-amber">{definitionsError}</div>
                  )}

                  {showMatchingBanner && templateMatches.length > 0 && (
                    <div className="rounded-xl bg-accent/10 border border-accent/30 px-3 py-2">
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
                </div>

                <div className="rounded-xl border border-border overflow-hidden">
                  <table className="w-full table-fixed text-[14px]">
                    <colgroup>
                      <col className="w-[18%]" /><col className="w-[12%]" /><col className="w-[70%]" />
                    </colgroup>
                    <thead>
                      <tr className="bg-surface-2/80 text-[11.5px] uppercase tracking-wider text-muted">
                        <th className="text-left px-3.5 py-3 font-semibold">{t("common.name")}</th>
                        <th className="text-left px-3.5 py-3 font-semibold">{t("common.type")}</th>
                        <th className="text-left px-3.5 py-3 font-semibold">{t("clarify.meaning")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(filteredColumns ?? []).map((col) => (
                        <tr key={col.name} className="border-t border-border/40 hover:bg-white/[0.02] transition-colors">
                          <td className="px-3.5 py-2.5 font-mono text-[13px] text-text align-top break-words">{col.name}</td>
                          <td className="px-3.5 py-2.5 align-top">
                            <span className="inline-flex rounded-md bg-white/[0.06] border border-border/60 px-2 py-0.5 text-[11.5px] font-mono text-muted">
                              {col.datatype}
                            </span>
                          </td>
                          <td className="px-3.5 py-2.5">
                            <input
                              type="text"
                              className={`w-full rounded-lg border bg-app text-text px-3 py-2 text-[13.5px] focus:outline-none focus:border-accent/70 transition-colors placeholder:text-muted/50 ${
                                col.meaning.trim() === "" ? "border-ic-amber/60" : "border-border/60"
                              }`}
                              value={col.meaning}
                              onChange={(e) => setMeaning(col.name, e.target.value)}
                              placeholder="Meaning…"
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <div className={fieldLabelCls}>{t("registryAdmin.lineName")}</div>
                    <input
                      type="text"
                      className={inputCls}
                      value={lineName}
                      onChange={(e) => {
                        setLineName(e.target.value);
                        localStorage.setItem("iot-registry-last-linename", e.target.value.toUpperCase());
                      }}
                    />
                  </div>
                  <div>
                    <div className={fieldLabelCls}>{t("registryAdmin.datasetName")}</div>
                    <div className="w-full rounded-xl border border-border bg-app text-text px-3.5 py-2.5 text-[15px] font-mono text-muted truncate">
                      {datasetName || "—"}
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <div className={fieldLabelCls}>{t("registryAdmin.startDate")}</div>
                    <div className="w-full rounded-xl border border-border bg-app text-text px-3.5 py-2.5 text-[15px] font-mono text-muted truncate">
                      {startDate || "—"}
                    </div>
                    {introspect?.data_earliest_ts ? (
                      <div className="text-[12px] text-ic-teal mt-1.5">
                        {t("registryAdmin.autoDetected", { col: introspect.data_earliest_col || "?" })}
                      </div>
                    ) : (
                      <div className="text-[12px] text-muted mt-1.5">{t("registryAdmin.noEarliestData")}</div>
                    )}
                  </div>
                  <div>
                    <div className={fieldLabelCls}>{t("registryAdmin.tableName")}</div>
                    <div className="w-full rounded-xl border border-border bg-app text-text px-3.5 py-2.5 text-[15px] font-mono text-muted truncate">
                      {tableName}
                    </div>
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between">
                    <div className={fieldLabelCls}>{t("registryAdmin.description")}</div>
                    <button
                      type="button"
                      className="text-[11px] font-semibold text-accent hover:text-ic-blue transition-colors"
                      onClick={() => columns && draftDescription(tableName, columns)}
                      disabled={!columns || draftingDescription}
                    >
                      {draftingDescription ? t("registryAdmin.draftingDescription") : t("registryAdmin.regenerate")}
                    </button>
                  </div>
                  <textarea
                    className={`${inputCls} resize-none`}
                    rows={2}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                  />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <div className={fieldLabelCls}>{t("registryAdmin.role")}</div>
                    <select className={inputCls} value={role} onChange={(e) => setRole(e.target.value)}>
                      <option value="primary">primary</option>
                      <option value="secondary">secondary</option>
                    </select>
                  </div>
                  <div>
                    <div className={fieldLabelCls}>{t("registryAdmin.synonyms")}</div>
                    <input type="text" className={inputCls} value={synonyms} onChange={(e) => setSynonyms(e.target.value)} />
                  </div>
                </div>

                <div>
                  <div className={fieldLabelCls}>{t("registryAdmin.suggestedAims")}</div>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      className={inputCls}
                      value={aimInput}
                      onChange={(e) => setAimInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          const v = aimInput.trim();
                          if (v && !suggestedAims.some((a) => a.toLowerCase() === v.toLowerCase())) {
                            setSuggestedAims([...suggestedAims, v]);
                          }
                          setAimInput("");
                        }
                      }}
                      placeholder={t("registryAdmin.aimPlaceholder")}
                    />
                    <button
                      type="button"
                      className={btnSecondary}
                      onClick={() => {
                        const v = aimInput.trim();
                        if (v && !suggestedAims.some((a) => a.toLowerCase() === v.toLowerCase())) {
                          setSuggestedAims([...suggestedAims, v]);
                        }
                        setAimInput("");
                      }}
                    >
                      <span className="text-[15px] leading-none mr-1">+</span>
                      {t("registryAdmin.addAim")}
                    </button>
                  </div>
                  {suggestedAims.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {suggestedAims.map((a, i) =>
                        editingAimIndex === i ? (
                          <span
                            key={i}
                            className="inline-flex items-center gap-1.5 rounded-md bg-surface-2 border border-accent/50 text-text text-[11.5px] px-1.5 py-1"
                          >
                            <input
                              type="text"
                              className="w-[180px] rounded-md border border-border bg-app text-text text-[11.5px] px-1.5 py-0.5 focus:outline-none focus:border-accent/70"
                              value={aimEditValue}
                              autoFocus
                              onChange={(e) => setAimEditValue(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") {
                                  const v = aimEditValue.trim();
                                  if (v) {
                                    setSuggestedAims(
                                      v.toLowerCase() === a.toLowerCase()
                                        ? suggestedAims
                                        : suggestedAims.some((x) => x.toLowerCase() === v.toLowerCase())
                                          ? suggestedAims.filter((_, j) => j !== i)
                                          : suggestedAims.map((x, j) => (j === i ? v : x))
                                    );
                                  }
                                  setEditingAimIndex(null);
                                } else if (e.key === "Escape") {
                                  setEditingAimIndex(null);
                                }
                              }}
                            />
                            <button
                              type="button"
                              className="text-ic-teal hover:text-text transition-colors"
                              onClick={() => {
                                const v = aimEditValue.trim();
                                if (v) {
                                  setSuggestedAims(
                                    v.toLowerCase() === a.toLowerCase()
                                      ? suggestedAims
                                      : suggestedAims.some((x) => x.toLowerCase() === v.toLowerCase())
                                        ? suggestedAims.filter((_, j) => j !== i)
                                        : suggestedAims.map((x, j) => (j === i ? v : x))
                                  );
                                }
                                setEditingAimIndex(null);
                              }}
                              title={t("registryAdmin.saveAim")}
                            >
                              ✓
                            </button>
                            <button
                              type="button"
                              className="text-muted hover:text-text transition-colors"
                              onClick={() => setEditingAimIndex(null)}
                              title={t("common.cancel")}
                            >
                              ✕
                            </button>
                          </span>
                        ) : (
                          <span
                            key={i}
                            className="inline-flex items-center gap-1.5 rounded-md bg-surface-2 border border-border/40 text-text text-[11.5px] px-2 py-1"
                          >
                            {a}
                            <button
                              type="button"
                              className="text-muted hover:text-ic-teal transition-colors"
                              onClick={() => {
                                setAimEditValue(a);
                                setEditingAimIndex(i);
                              }}
                              title={t("registryAdmin.editAim")}
                            >
                              ✓
                            </button>
                            <button
                              type="button"
                              className="text-muted hover:text-ic-amber transition-colors"
                              onClick={() => setSuggestedAims(suggestedAims.filter((_, j) => j !== i))}
                              title={t("common.cancel")}
                            >
                              ✕
                            </button>
                          </span>
                        )
                      )}
                    </div>
                  )}
                  <div className="text-[11.5px] text-muted mt-1.5">{t("registryAdmin.aimsHint")}</div>
                </div>

                <div className="flex items-center justify-end gap-3 pt-2 border-t border-border/40">
                  <button type="button" className={btnSecondary} onClick={() => handleSave(false)} disabled={saving}>
                    {saving ? (
                      <>
                        <span className="spinner" /> {t("registryAdmin.saving")}
                      </>
                    ) : (
                      t("registryAdmin.saveDraft")
                    )}
                  </button>
                  <button type="button" className={btnPrimary} onClick={() => handleSave(true)} disabled={saving}>
                    {saving ? (
                      <>
                        <span className="spinner" /> {t("registryAdmin.saving")}
                      </>
                    ) : (
                      <>
                        <IconCheck size={16} /> {t("registryAdmin.saveActivate")}
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── ENTRIES ── */}
        <div className={`${panelCardCls} mt-6`}>
          <div className={topAccent} />
          <div className="flex items-center justify-between mb-4">
            <div className="text-[16px] font-semibold text-text">{t("registryAdmin.yourEntries")}</div>
            {entries.length > 0 && (
              <span className="inline-flex items-center justify-center min-w-[22px] h-[22px] px-1.5 rounded-full bg-accent/15 text-accent text-[11.5px] font-semibold">
                {entries.length}
              </span>
            )}
          </div>
          {entries.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border/60 py-10 px-4 text-center">
              <IconDatabase size={22} className="mx-auto mb-2.5 text-muted/50" />
              <p className="text-[13.5px] text-muted">{t("registryAdmin.noEntries")}</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 2xl:grid-cols-3 gap-3">
              {entries.map((entry) => (
                <div
                  key={entry.id}
                  className="flex items-center gap-3 rounded-xl border border-border/60 bg-surface-2/60 hover:bg-surface-2 hover:border-white/20 transition-all px-4 py-3"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[14.5px] font-semibold text-text truncate">{entry.dataset_name}</span>
                      {entry.db_type && (
                        <span
                          className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md ${
                            entry.db_type === "mysql" ? "bg-ic-amber-soft/50 text-ic-amber" : "bg-ic-blue-soft/50 text-ic-blue"
                          }`}
                        >
                          {entry.db_type}
                        </span>
                      )}
                    </div>
                    <div className="text-[12.5px] text-muted font-mono truncate mt-0.5">
                      {entry.line_name} · {entry.table}
                      {entry.data_earliest_ts ? ` · since ${entry.data_earliest_ts.slice(0, 10)}` : ""}
                    </div>
                  </div>
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide border shrink-0 ${
                      entry.status === "active"
                        ? "bg-ic-teal-soft/50 text-ic-teal border-ic-teal/30"
                        : "bg-ic-amber-soft/50 text-ic-amber border-ic-amber/30"
                    }`}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${entry.status === "active" ? "bg-ic-teal" : "bg-ic-amber"}`} />
                    {entry.status === "active" ? t("registryAdmin.statusActive") : t("registryAdmin.statusDraft")}
                  </span>
                  {entry.status !== "active" && (
                    <button
                      type="button"
                      className="shrink-0 inline-flex items-center rounded-lg bg-accent/15 hover:bg-accent/25 text-accent text-[12.5px] font-semibold px-3 py-1.5 transition-colors"
                      onClick={() => handleActivate(entry)}
                    >
                      {t("registryAdmin.activate")}
                    </button>
                  )}
                  <button
                    type="button"
                    className="shrink-0 text-muted hover:text-ic-red hover:bg-ic-red/10 rounded-lg p-1.5 transition-colors"
                    onClick={() => handleDelete(entry)}
                    title="Delete entry"
                  >
                    <IconTrash size={15} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>

      {detailsConn && <ConnectionDetailsModal conn={detailsConn} onClose={() => setDetailsConn(null)} />}
    </div>
  );
}
