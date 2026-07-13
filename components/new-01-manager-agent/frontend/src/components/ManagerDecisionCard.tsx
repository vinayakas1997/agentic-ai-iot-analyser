import { useState } from "react";
import type { Turn, TurnUi, SchemaSnapshot } from "../types/manager";
import { decisionCardClass, raisedCardClass, sectionHeaderClass, fieldLabelClass, monoClass } from "../lib/styles";
import { IconCheckCircle, IconMapPin, IconDatabase, IconClock, IconTarget, IconStar } from "../lib/icons";

const SOURCE_LABELS: Record<string, string> = {
  line_name: "exact line name",
  synonym: "synonym",
  task_alias: "previous analysis alias",
};

function formatLineMatch(match: { mention?: string; canonical?: string; source?: string }) {
  if (!match?.canonical) return null;
  const mention = match.mention || match.canonical;
  const source = SOURCE_LABELS[match.source || ""] || match.source || "match";
  if (mention === match.canonical) return `${match.canonical} (${source})`;
  return `${mention} → ${match.canonical} (${source})`;
}

interface Props {
  turn: Turn;
  isLive: boolean;
  onSendMessage: (msg: string) => void;
  showHandoff?: boolean;
  variant?: "detail" | "summary";
}

function InlineEdit({
  currentValue,
  placeholder,
  prefix,
  onSave,
  onCancel,
}: {
  currentValue: string;
  placeholder?: string;
  prefix: string;
  onSave: (val: string) => void;
  onCancel: () => void;
}) {
  const [val, setVal] = useState(currentValue);
  return (
    <div className="flex items-center gap-1.5 mt-2">
      <input
        type="text"
        className="flex-1 rounded-lg border-2 border-border bg-bg-deep text-text px-3 py-1.5 text-xs font-mono"
        value={val}
        placeholder={placeholder}
        onChange={(e) => setVal(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && val.trim() && onSave(`${prefix}${val.trim()}`)}
        autoFocus
      />
      <button
        type="button"
        className="text-xs px-2.5 py-1.5 rounded-lg bg-stage-execution text-[#0a1a12] font-semibold disabled:opacity-50"
        disabled={!val.trim()}
        onClick={() => onSave(`${prefix}${val.trim()}`)}
      >
        OK
      </button>
      <button
        type="button"
        className="text-xs px-2.5 py-1.5 rounded-lg bg-surface-2 text-muted hover:text-text"
        onClick={onCancel}
      >
        Cancel
      </button>
    </div>
  );
}

export default function ManagerDecisionCard({ turn, isLive, onSendMessage, showHandoff, variant = "detail" }: Props) {
  const [editingField, setEditingField] = useState<string | null>(null);
  const [showBenefits, setShowBenefits] = useState(false);
  const schema: SchemaSnapshot | null = turn.schema;
  const ui: TurnUi | null = turn.ui;

  const provenance = ui?.proposal_provenance || [];

  const hasDecision = schema?.line_match || schema?.line || schema?.datasets_in_scope?.length;

  if (!hasDecision && !ui?.done) return null;

  const lineMatchStr = schema?.line_match ? formatLineMatch(schema.line_match) : null;

  const handleEditSave = (field: string, message: string) => {
    onSendMessage(message);
    setEditingField(null);
  };

  /* ── Summary variant (compact read-only) ── */
  if (variant === "summary") {
    return (
      <div className={raisedCardClass}>
        <h3 className={sectionHeaderClass}>
          <span className="inline-flex items-center justify-center w-[18px] h-[18px] rounded-[6px] bg-stage-manager-soft text-stage-manager">
            <IconCheckCircle size={10.5} />
          </span>
          Manager Decision
        </h3>
        <div className="text-xs text-muted leading-relaxed space-y-0.5">
          {schema?.line && (
            <p>
              Line:{" "}
              <span className={`${monoClass} font-semibold text-text`}>
                {lineMatchStr || schema.line}
              </span>
            </p>
          )}
          {(schema?.datasets_in_scope?.length ?? 0) > 0 && (
            <p>
              Datasets:{" "}
              {schema.datasets_in_scope.map((ds, i) => (
                <span key={ds} className={`${monoClass} font-medium text-text`}>
                  {i > 0 && <span className="text-tertiary">, </span>}
                  {ds}
                </span>
              ))}
            </p>
          )}
          <p>
            Time:{" "}
            <span className="font-medium text-text">
              {schema?.time
                ? `${schema.time.start} → ${schema.time.end}`
                : schema?.no_time_filter
                  ? "No time filter"
                  : "—"}
            </span>
          </p>
          {(ui?.plan?.aims?.length ?? 0) > 0 && (
            <p>
              Aims:{" "}
              <span className="font-medium text-text">{ui.plan.aims.join(" · ")}</span>
            </p>
          )}
        </div>
      </div>
    );
  }

  /* ── Detail variant (elevated, editable, with provenance) ── */
  return (
    <div className={decisionCardClass}>
      {/* Eyebrow */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-1.5 font-display text-[11.5px] font-semibold tracking-widest uppercase text-stage-manager">
          <span className="inline-flex items-center justify-center w-[22px] h-[22px] rounded-[7px] bg-stage-manager-soft text-stage-manager">
            <IconCheckCircle size={13} />
          </span>
          Manager Decision
        </div>
      </div>

      {/* ── Resolved Line ── */}
      {(schema?.line_match || schema?.line || lineMatchStr) && (
        <div className="mb-4 last:mb-0">
          <div className={fieldLabelClass}>
            <span className="inline-flex items-center justify-center w-[18px] h-[18px] rounded-[6px] bg-ic-violet-soft text-ic-violet">
              <IconMapPin size={10.5} />
            </span>
            Line
            {isLive && !ui?.done && (
              <button
                type="button"
                className="ml-auto text-tertiary hover:text-text"
                title="Edit line"
                onClick={() => setEditingField(editingField === "line" ? null : "line")}
              >
                ✎
              </button>
            )}
          </div>
          {editingField === "line" ? (
            <InlineEdit
              currentValue={schema?.line || ""}
              placeholder="Enter line name..."
              prefix="change line to "
              onSave={(msg) => handleEditSave("line", msg)}
              onCancel={() => setEditingField(null)}
            />
          ) : (
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`${monoClass} text-[14.5px] font-medium text-text`}>
                {schema?.line_match?.mention || schema?.line || ""}
                {(schema?.line_match?.mention && schema?.line_match?.canonical && schema.line_match.mention !== schema.line_match.canonical) && (
                  <>
                    <span className="text-tertiary font-normal mx-1">→</span>
                    <span className={monoClass}>{schema.line_match.canonical}</span>
                  </>
                )}
              </span>
              {schema?.line_match?.source && (
                <span className="inline-flex items-center gap-1 text-[10.5px] font-semibold text-stage-manager bg-stage-manager-soft border border-stage-manager-line px-2 py-0.5 rounded-full">
                  <IconStar size={10} />
                  {SOURCE_LABELS[schema.line_match.source] || schema.line_match.source}
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Datasets in Scope ── */}
      {(schema?.datasets_in_scope?.length ?? 0) > 0 && (
        <div className="mb-4 last:mb-0">
          <div className={fieldLabelClass}>
            <span className="inline-flex items-center justify-center w-[18px] h-[18px] rounded-[6px] bg-ic-amber-soft text-ic-amber">
              <IconDatabase size={10.5} />
            </span>
            Datasets
            {isLive && !ui?.done && (
              <button
                type="button"
                className="ml-auto text-tertiary hover:text-text"
                title="Edit scope"
                onClick={() => setEditingField(editingField === "datasets" ? null : "datasets")}
              >
                ✎
              </button>
            )}
          </div>
          {editingField === "datasets" ? (
            <InlineEdit
              currentValue={schema?.datasets_in_scope?.join(", ") || ""}
              placeholder="dataset1, dataset2"
              prefix="change scope to "
              onSave={(msg) => handleEditSave("datasets", msg)}
              onCancel={() => setEditingField(null)}
            />
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {schema?.datasets_in_scope?.map((ds) => (
                <span
                  key={ds}
                  className={`${monoClass} text-xs text-ic-blue bg-ic-blue-soft/60 backdrop-blur-md border border-ic-blue/20 px-2.5 py-1 rounded-[7px]`}
                >
                  {ds}
                </span>
              ))}
            </div>
          )}
          {schema?.joins && schema.joins.length > 0 && (
            <div className="mt-2 text-xs text-tertiary space-y-0.5">
              {schema.joins.map((j, i) => {
                const from = j.from_dataset || j.from || "";
                const to = j.to_dataset || j.to || "";
                const keys = (j.on || []).join(", ");
                if (schema.datasets_in_scope?.includes(from) && schema.datasets_in_scope?.includes(to)) {
                  return <p key={i} className="font-mono">{from} ↔ {to} on {keys}</p>;
                }
                return null;
              })}
            </div>
          )}
          {schema?.datasets_excluded && schema.datasets_excluded.length > 0 && (
            <p className="text-xs text-tertiary mt-1">Excluded: {schema.datasets_excluded.join(", ")}</p>
          )}
        </div>
      )}

      {/* ── Time Filter ── */}
      {(schema?.time || schema?.no_time_filter) && (
        <div className="mb-4 last:mb-0">
          <div className={fieldLabelClass}>
            <span className="inline-flex items-center justify-center w-[18px] h-[18px] rounded-[6px] bg-ic-blue-soft text-ic-blue">
              <IconClock size={10.5} />
            </span>
            Time
            {isLive && !ui?.done && (
              <button
                type="button"
                className="ml-auto text-tertiary hover:text-text"
                title="Edit time"
                onClick={() => setEditingField(editingField === "time" ? null : "time")}
              >
                ✎
              </button>
            )}
          </div>
          {editingField === "time" ? (
            <InlineEdit
              currentValue={schema?.time ? `${schema.time.start} → ${schema.time.end}` : "no filter"}
              placeholder="2024-01-01 to 2024-12-31"
              prefix="change time to "
              onSave={(msg) => handleEditSave("time", msg)}
              onCancel={() => setEditingField(null)}
            />
          ) : (
            <span className={`${monoClass} text-xs text-text bg-white/[0.05] border border-border-2 px-2.5 py-1 rounded-[7px] inline-block`}>
              {schema?.time ? `${schema.time.start} → ${schema.time.end}` : "No time filter"}
            </span>
          )}
        </div>
      )}

      {/* ── Aims ── */}
      {((ui?.plan?.aims?.length ?? 0) > 0 || (schema?.suggested_aims?.length ?? 0) > 0) && (
        <div className="mb-4 last:mb-0">
          <div className={fieldLabelClass}>
            <span className="inline-flex items-center justify-center w-[18px] h-[18px] rounded-[6px] bg-ic-coral-soft text-ic-coral">
              <IconTarget size={10.5} />
            </span>
            Aims
          </div>
          {ui?.plan?.aims && ui.plan.aims.length > 0 && (
            <div className="space-y-2">
              {ui.plan.aims.map((aim) => {
                const provider = provenance.find((p) =>
                  aim.toLowerCase().includes(p.suggestedAim.toLowerCase()) ||
                  p.suggestedAim.toLowerCase().includes(aim.toLowerCase())
                );
                return (
                  <div key={aim} className="flex gap-2 text-[13.5px] leading-relaxed text-text">
                    <span className="w-[5px] h-[5px] rounded-full bg-stage-manager shrink-0 mt-[7px] shadow-[0_0_8px_1px_var(--stage-manager-soft)]" />
                    <span>
                      {aim}
                      {provider && provider.fulfilledByProposalIds.length > 0 && (
                        <span className="text-xs text-tertiary ml-1">
                          (from suggestion: {provider.suggestedAim})
                        </span>
                      )}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
          {ui?.plan?.benefits && (
            <div className="mt-3">
              <button
                type="button"
                onClick={() => setShowBenefits((v) => !v)}
                className="flex items-center gap-1.5 text-xs text-muted italic hover:text-text transition-colors cursor-pointer"
              >
                <span className={`transition-transform ${showBenefits ? "rotate-90" : ""}`}>▶</span>
                Benefits explanation
              </button>
              {showBenefits && (
                <div className="mt-2 pl-[13px] border-l-2 border-stage-manager-line bg-stage-manager-soft/30 rounded-r-lg py-2 px-3 text-xs text-muted italic leading-relaxed">
                  {ui.plan.benefits.split("\n").filter(Boolean).map((b, bi) => (
                    <p key={bi} className="m-0">{b}</p>
                  ))}
                </div>
              )}
            </div>
          )}
          {!ui?.plan?.aims?.length && schema?.suggested_aims && schema.suggested_aims.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-1">
              {schema.suggested_aims.map((aim) => {
                const provider = provenance.find((p) => p.suggestedAim === aim);
                const propIds = provider?.fulfilledByProposalIds?.filter(Boolean) || [];
                return (
                  <span
                    key={aim}
                    className="text-xs px-2.5 py-1 rounded-[7px] bg-ic-violet-soft text-ic-violet"
                    title={propIds.length > 0 ? `Fulfilled by proposal(s): ${propIds.join(", ")}` : "Suggested only"}
                  >
                    {aim}
                    {propIds.length > 0 && (
                      <span className="ml-1">→ P{propIds.join(",")}</span>
                    )}
                  </span>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ── Full handoff payload ── */}
      {showHandoff && ui?.planner_payload && (
        <div className="mt-4 pt-4 border-t-2 border-stage-manager-line/30">
          <span className="text-[10.5px] font-semibold tracking-widest uppercase text-tertiary">
            Handoff to Planner
          </span>
          <div className="mt-2 space-y-1 text-xs text-tertiary">
            {ui.planner_payload.line_name && <p>Line: {ui.planner_payload.line_name}</p>}
            {ui.planner_payload.task_definition?.aims && (
              <p>Aims: {ui.planner_payload.task_definition.aims.join(", ")}</p>
            )}
            {ui.planner_payload.datasets_in_scope && ui.planner_payload.datasets_in_scope.length > 0 && (
              <p>Datasets: {ui.planner_payload.datasets_in_scope.join(", ")}</p>
            )}
            {ui.planner_payload.join_catalog && ui.planner_payload.join_catalog.length > 0 && (
              <div>
                <p>Joins:</p>
                <ul className="list-disc pl-4 mt-0.5">
                  {ui.planner_payload.join_catalog.map((j, i) => {
                    const from = j.from_dataset || "";
                    const to = j.to_dataset || "";
                    const keys = (j.on || []).join(", ");
                    return <li key={i}>{from} ↔ {to} on {keys || "—"}</li>;
                  })}
                </ul>
              </div>
            )}
            {ui.planner_payload.time_range && (
              <p>Time: {ui.planner_payload.time_range.start} → {ui.planner_payload.time_range.end}</p>
            )}
            {ui.planner_payload.datasets_excluded && ui.planner_payload.datasets_excluded.length > 0 && (
              <p>Excluded: {ui.planner_payload.datasets_excluded.join(", ")}</p>
            )}
            {ui.planner_payload.task_definition?.alias_name && (
              <p>Alias: {ui.planner_payload.task_definition.alias_name}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
