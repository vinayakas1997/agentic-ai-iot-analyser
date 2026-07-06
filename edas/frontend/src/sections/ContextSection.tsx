import { useSessionStore, useSelectedTurn } from "../stores/sessionStore";
import { cardClass, panelClass } from "../lib/styles";

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

export default function ContextSection() {
  const sessionMeta = useSessionStore((s) => s.sessionMeta);
  const turns = useSessionStore((s) => s.turns);
  const turn = useSelectedTurn();
  const schema = turn?.schema;

  return (
    <section className={`${panelClass} order-1 lg:order-none overflow-y-auto text-sm`}>
      <h2 className="text-base font-semibold mb-3">Context</h2>

      {sessionMeta && (
        <div className={cardClass}>
          <p className="font-semibold text-sm">Session</p>
          <p className="text-muted text-xs mt-1">{sessionMeta.session_id?.slice(0, 8)}…</p>
          <p className="text-xs mt-1">Turns: {turns.length}</p>
          <p className="text-xs">Phase: {sessionMeta.phase}</p>
        </div>
      )}

      {!schema ? (
        <p className="text-muted text-sm">No schema snapshot.</p>
      ) : (
        <>
          {schema.line_match && (
            <div className={cardClass}>
              <p className="font-semibold text-sm">Line match</p>
              <p className="text-xs mt-1">{formatLineMatch(schema.line_match)}</p>
            </div>
          )}

          <div className={cardClass}>
            <p className="font-semibold text-sm">Line</p>
            <p className="mt-1">{schema.line || "—"}</p>
          </div>

          {schema.datasets && schema.datasets.length > 0 && (
            <div className={cardClass}>
              <p className="font-semibold text-sm">Datasets</p>
              {schema.datasets.map((ds) => (
                <div key={ds.name} className="mt-2 text-xs">
                  <p>
                    <span className="font-medium">{ds.name}</span>
                    {ds.table ? ` → ${ds.table}` : ""}
                    {ds.role ? ` (${ds.role})` : ""}
                  </p>
                  {ds.description && <p className="text-muted">{ds.description}</p>}
                </div>
              ))}
            </div>
          )}

          {schema.datasets_in_scope && schema.datasets_in_scope.length > 0 && (
            <div className={cardClass}>
              <p className="font-semibold text-sm">In scope</p>
              <p className="text-xs mt-1">{schema.datasets_in_scope.join(", ")}</p>
            </div>
          )}

          {schema.datasets_excluded && schema.datasets_excluded.length > 0 && (
            <div className={cardClass}>
              <p className="font-semibold text-sm">Excluded</p>
              <p className="text-xs mt-1">{schema.datasets_excluded.join(", ")}</p>
            </div>
          )}

          {schema.time && (
            <div className={cardClass}>
              <p className="font-semibold text-sm">Time</p>
              <p className="text-xs mt-1">
                {schema.time.start} → {schema.time.end}
              </p>
            </div>
          )}

          {schema.no_time_filter && (
            <div className={cardClass}>
              <p className="text-xs text-muted">No time filter</p>
            </div>
          )}

          {schema.suggested_aims && schema.suggested_aims.length > 0 && (
            <div className={cardClass}>
              <p className="font-semibold text-sm">Suggested aims</p>
              <ul className="list-disc pl-4 mt-2 text-xs space-y-1">
                {schema.suggested_aims.map((aim) => (
                  <li key={aim}>{aim}</li>
                ))}
              </ul>
            </div>
          )}

          {schema.columns && schema.columns.length > 0 && (
            <div className={`${cardClass} overflow-x-auto`}>
              <p className="font-semibold text-sm mb-2">Columns</p>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-muted border-b border-border">
                    <th className="py-1 pr-2">Dataset</th>
                    <th className="py-1 pr-2">Name</th>
                    <th className="py-1 pr-2">Type</th>
                    <th className="py-1">Meaning</th>
                  </tr>
                </thead>
                <tbody>
                  {schema.columns.map((c, i) => (
                    <tr key={`${c.dataset}-${c.name}-${i}`} className="border-b border-border/50">
                      <td className="py-1 pr-2">{c.dataset}</td>
                      <td className="py-1 pr-2">{c.name}</td>
                      <td className="py-1 pr-2">{c.datatype}</td>
                      <td className="py-1">{c.meaning || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {schema.joins && schema.joins.length > 0 && (
            <div className={cardClass}>
              <p className="font-semibold text-sm">Joins</p>
              {schema.joins.map((j, i) => (
                <p key={i} className="text-xs mt-1">
                  {j.left_dataset || j.from} → {j.right_dataset || j.to} on {(j.on || []).join(", ")}
                </p>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}
