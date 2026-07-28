import { useState, useMemo } from "react";
import { monoClass } from "../lib/styles";
import { IconGrid, IconChart } from "../lib/icons";
import { useT, tCount } from "../lib/i18n";
import {
  BarChart, Bar, LineChart, Line, AreaChart, Area,
  PieChart, Pie, Cell, ComposedChart, ScatterChart, Scatter,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  ReferenceLine, Treemap, FunnelChart, Funnel,
  SunburstChart, RadialBarChart, RadialBar,
} from "recharts";

export interface ChartConfig {
  chartType: "composed" | "stackedArea" | "treemap" | "radialBar" | "funnel" | "sunburst" | "scatter" | "radar" | "bar" | "line" | "area" | "pie";
  xKey: string;
  yKeys: string[];
  reason?: string;
  xLabel?: string;
  yLabel?: string;
  howToRead?: string;
}

export interface ChartSuggestions {
  advanced: ChartConfig[];
  basic: ChartConfig[];
}

export interface QueryResultState {
  loading: boolean;
  sql?: string;
  columns?: string[];
  column_types?: string[];
  rows?: Record<string, unknown>[];
  row_count?: number;
  error?: string;
  chart_suggestions?: ChartSuggestions | null;
}

const CHART_COLORS = ["#06b6d4", "#f59e0b", "#8b5cf6", "#3b82f6", "#ef4444", "#ec4899", "#f97316", "#22c55e", "#14b8a6", "#a855f7"];
const VALID_CHART_TYPES = new Set(["composed", "stackedArea", "treemap", "radialBar", "funnel", "sunburst", "scatter", "radar", "bar", "line", "area", "pie"]);

function sanitizeSuggestions(raw: ChartSuggestions | undefined): { advanced: ChartConfig[]; basic: ChartConfig[] } {
  if (!raw) return { advanced: [], basic: [] };
  const isGood = (c: ChartConfig) => VALID_CHART_TYPES.has(c.chartType) && c.xKey && c.yKeys?.length;
  return {
    advanced: raw.advanced.filter(isGood),
    basic: raw.basic.filter(isGood),
  };
}

function axisLabelStyles() {
  return {
    tick: { fontSize: 10, fill: "#999" },
    axisLine: { stroke: "rgba(255,255,255,0.08)" },
    tickLine: false,
  };
}

function tooltipStyle() {
  return { contentStyle: { background: "#1a1a2e", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, fontSize: 12 } };
}

// ── Advanced chart renderers ──

function renderComposedChart(cfg: ChartConfig, rows: Record<string, unknown>[]) {
  const yKeys = cfg.yKeys;
  const singleY = yKeys.length === 1 ? yKeys[0] : null;
  let values: { max: number; min: number; avg: number } | null = null;
  if (singleY) {
    const nums = rows.map(r => Number(r[singleY])).filter(n => !isNaN(n));
    if (nums.length > 0) {
      values = {
        max: Math.max(...nums),
        min: Math.min(...nums),
        avg: nums.reduce((a, b) => a + b, 0) / nums.length,
      };
    }
  }

  return (
    <ComposedChart data={rows}>
      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
      <XAxis dataKey={cfg.xKey} {...axisLabelStyles()} label={cfg.xLabel ? { value: cfg.xLabel, position: "bottom", offset: -5, style: { fill: "#999", fontSize: 10 } } : undefined} />
      <YAxis {...axisLabelStyles()} label={cfg.yLabel ? { value: cfg.yLabel, angle: -90, position: "insideLeft", style: { fill: "#999", fontSize: 10 } } : undefined} />
      <Tooltip {...tooltipStyle()} />
      <Legend wrapperStyle={{ fontSize: 11 }} />
      {values && (
        <>
          <ReferenceLine y={values.max} stroke="#ef4444" strokeDasharray="3 3" label={{ value: `Max: ${values.max.toFixed(1)}`, position: "insideTopRight", fill: "#ef4444", fontSize: 10 }} />
          <ReferenceLine y={values.min} stroke="#22c55e" strokeDasharray="3 3" label={{ value: `Min: ${values.min.toFixed(1)}`, position: "insideBottomRight", fill: "#22c55e", fontSize: 10 }} />
          <ReferenceLine y={values.avg} stroke="#8b5cf6" strokeDasharray="3 3" label={{ value: `Avg: ${values.avg.toFixed(1)}`, position: "insideTopLeft", fill: "#8b5cf6", fontSize: 10 }} />
        </>
      )}
      {yKeys.map((k, i) => (
        i < yKeys.length - 1
          ? <Bar key={k} dataKey={k} stackId="stack" fill={CHART_COLORS[i % CHART_COLORS.length]} radius={[4, 4, 0, 0]} />
          : <Line key={k} type="monotone" dataKey={k} stroke="#fff" strokeWidth={2} dot={{ r: 2, fill: "#fff" }} />
      ))}
    </ComposedChart>
  );
}

function renderScatterChart(cfg: ChartConfig, rows: Record<string, unknown>[]) {
  return (
    <ScatterChart>
      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
      <XAxis dataKey={cfg.xKey} {...axisLabelStyles()} name={cfg.xKey} label={cfg.xLabel ? { value: cfg.xLabel, position: "bottom", offset: -5, style: { fill: "#999", fontSize: 10 } } : undefined} />
      <YAxis dataKey={cfg.yKeys[0] || ""} {...axisLabelStyles()} name={cfg.yKeys[0] || ""} label={cfg.yLabel ? { value: cfg.yLabel, angle: -90, position: "insideLeft", style: { fill: "#999", fontSize: 10 } } : undefined} />
      <Tooltip {...tooltipStyle()} cursor={{ strokeDasharray: "3 3" }} />
      <Scatter data={rows} fill={CHART_COLORS[0]} />
    </ScatterChart>
  );
}

function renderRadarChart(cfg: ChartConfig, rows: Record<string, unknown>[]) {
  return (
    <RadarChart data={rows}>
      <PolarGrid stroke="rgba(255,255,255,0.1)" />
      <PolarAngleAxis dataKey={cfg.xKey} tick={{ fontSize: 9, fill: "#999" }} />
      <PolarRadiusAxis tick={{ fontSize: 9, fill: "#999" }} />
      {cfg.yKeys.map((k, i) => (
        <Radar key={k} name={k} dataKey={k} stroke={CHART_COLORS[i % CHART_COLORS.length]} fill={CHART_COLORS[i % CHART_COLORS.length]} fillOpacity={0.2} />
      ))}
      <Legend wrapperStyle={{ fontSize: 11 }} />
    </RadarChart>
  );
}

function renderStackedAreaChart(cfg: ChartConfig, rows: Record<string, unknown>[]) {
  return (
    <AreaChart data={rows}>
      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
      <XAxis dataKey={cfg.xKey} {...axisLabelStyles()} label={cfg.xLabel ? { value: cfg.xLabel, position: "bottom", offset: -5, style: { fill: "#999", fontSize: 10 } } : undefined} />
      <YAxis {...axisLabelStyles()} label={cfg.yLabel ? { value: cfg.yLabel, angle: -90, position: "insideLeft", style: { fill: "#999", fontSize: 10 } } : undefined} />
      <Tooltip {...tooltipStyle()} />
      <Legend wrapperStyle={{ fontSize: 11 }} />
      {cfg.yKeys.map((k, i) => (
        <Area key={k} type="monotone" dataKey={k} stackId="stack" stroke={CHART_COLORS[i % CHART_COLORS.length]} fill={CHART_COLORS[i % CHART_COLORS.length]} fillOpacity={0.5} />
      ))}
    </AreaChart>
  );
}

function renderTreemapChart(cfg: ChartConfig, rows: Record<string, unknown>[]) {
  const data = rows.map((r, i) => ({
    name: String(r[cfg.xKey] ?? `Item ${i}`),
    value: Number(r[cfg.yKeys[0]] || 0),
    fill: CHART_COLORS[i % CHART_COLORS.length],
  }));
  return (
    <Treemap width={400} height={200} data={data} dataKey="value" nameKey="name" aspectRatio={4 / 3} stroke="rgba(0,0,0,0.3)" fill="#06b6d4" />
  );
}

function renderRadialBarChart(cfg: ChartConfig, rows: Record<string, unknown>[]) {
  const data = rows.map((r, i) => ({
    name: String(r[cfg.xKey] ?? `Item ${i}`),
    ...Object.fromEntries(cfg.yKeys.map(k => [k, Number(r[k] || 0)])),
    fill: CHART_COLORS[i % CHART_COLORS.length],
  }));
  return (
    <RadialBarChart innerRadius="20%" outerRadius="80%" barSize={12} data={data}>
      <RadialBar dataKey={cfg.yKeys[0] || ""} cornerRadius={6} label={{ position: "insideStart", fill: "#fff", fontSize: 9 }} />
      <Legend wrapperStyle={{ fontSize: 11 }} />
    </RadialBarChart>
  );
}

function renderFunnelChart(cfg: ChartConfig, rows: Record<string, unknown>[]) {
  const data = rows.map((r, i) => ({
    name: String(r[cfg.xKey] ?? `Stage ${i}`),
    value: Number(r[cfg.yKeys[0]] || 0),
    fill: CHART_COLORS[i % CHART_COLORS.length],
  }));
  return (
    <FunnelChart width={400} height={250}>
      <Tooltip {...tooltipStyle()} />
      <Funnel dataKey="value" nameKey="name" data={data} isAnimationActive />
    </FunnelChart>
  );
}

function renderSunburstChart(cfg: ChartConfig, rows: Record<string, unknown>[]) {
  const yKey = cfg.yKeys[0] || cfg.yKeys[0];
  const data = rows.map((r, i) => ({
    name: String(r[cfg.xKey] ?? `Root ${i}`),
    children: cfg.yKeys.length > 1 ? cfg.yKeys.slice(1).map(sk => ({
      name: String(r[sk] ?? ""),
      value: Number(r[yKey] || 0),
      fill: CHART_COLORS[(i + 1) % CHART_COLORS.length],
    })) : [],
    fill: CHART_COLORS[i % CHART_COLORS.length],
  }));
  return (
    <SunburstChart width={400} height={200} data={{ name: "root", children: data }}>
      <Tooltip {...tooltipStyle()} />
    </SunburstChart>
  );
}

// ── Unified chart dispatch ──

function renderChartByType(cfg: ChartConfig, rows: Record<string, unknown>[]) {
  switch (cfg.chartType) {
    case "composed": return renderComposedChart(cfg, rows);
    case "stackedArea": return renderStackedAreaChart(cfg, rows);
    case "treemap": return renderTreemapChart(cfg, rows);
    case "radialBar": return renderRadialBarChart(cfg, rows);
    case "funnel": return renderFunnelChart(cfg, rows);
    case "sunburst": return renderSunburstChart(cfg, rows);
    case "scatter": return renderScatterChart(cfg, rows);
    case "radar": return renderRadarChart(cfg, rows);
    case "bar": return renderBarChart(cfg, rows);
    case "line": return renderLineChart(cfg, rows);
    case "area": return renderAreaChart(cfg, rows);
    case "pie": return renderPieChart(cfg, rows);
    default: return null;
  }
}

function renderBarChart(cfg: ChartConfig, rows: Record<string, unknown>[]) {
  return (
    <BarChart data={rows}>
      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
      <XAxis dataKey={cfg.xKey} {...axisLabelStyles()} label={cfg.xLabel ? { value: cfg.xLabel, position: "bottom", offset: -5, style: { fill: "#999", fontSize: 10 } } : undefined} />
      <YAxis {...axisLabelStyles()} label={cfg.yLabel ? { value: cfg.yLabel, angle: -90, position: "insideLeft", style: { fill: "#999", fontSize: 10 } } : undefined} />
      <Tooltip {...tooltipStyle()} />
      <Legend wrapperStyle={{ fontSize: 11 }} />
      {cfg.yKeys.map((k, i) => (
        <Bar key={k} dataKey={k} fill={CHART_COLORS[i % CHART_COLORS.length]} radius={[4, 4, 0, 0]} />
      ))}
    </BarChart>
  );
}

function renderLineChart(cfg: ChartConfig, rows: Record<string, unknown>[]) {
  return (
    <LineChart data={rows}>
      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
      <XAxis dataKey={cfg.xKey} {...axisLabelStyles()} label={cfg.xLabel ? { value: cfg.xLabel, position: "bottom", offset: -5, style: { fill: "#999", fontSize: 10 } } : undefined} />
      <YAxis {...axisLabelStyles()} label={cfg.yLabel ? { value: cfg.yLabel, angle: -90, position: "insideLeft", style: { fill: "#999", fontSize: 10 } } : undefined} />
      <Tooltip {...tooltipStyle()} />
      <Legend wrapperStyle={{ fontSize: 11 }} />
      {cfg.yKeys.map((k, i) => (
        <Line key={k} type="monotone" dataKey={k} stroke={CHART_COLORS[i % CHART_COLORS.length]} strokeWidth={2} dot={{ r: 3 }} />
      ))}
    </LineChart>
  );
}

function renderAreaChart(cfg: ChartConfig, rows: Record<string, unknown>[]) {
  return (
    <AreaChart data={rows}>
      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
      <XAxis dataKey={cfg.xKey} {...axisLabelStyles()} label={cfg.xLabel ? { value: cfg.xLabel, position: "bottom", offset: -5, style: { fill: "#999", fontSize: 10 } } : undefined} />
      <YAxis {...axisLabelStyles()} label={cfg.yLabel ? { value: cfg.yLabel, angle: -90, position: "insideLeft", style: { fill: "#999", fontSize: 10 } } : undefined} />
      <Tooltip {...tooltipStyle()} />
      <Legend wrapperStyle={{ fontSize: 11 }} />
      {cfg.yKeys.map((k, i) => (
        <Area key={k} type="monotone" dataKey={k} stroke={CHART_COLORS[i % CHART_COLORS.length]} fill={CHART_COLORS[i % CHART_COLORS.length]} fillOpacity={0.15} />
      ))}
    </AreaChart>
  );
}

function renderPieChart(cfg: ChartConfig, rows: Record<string, unknown>[]) {
  const pieData = rows.map((r, i) => ({
    name: String(r[cfg.xKey] ?? `Item ${i}`),
    value: Number(r[cfg.yKeys[0]] || 0),
  }));
  return (
    <PieChart>
      <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80}
        label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}>
        {pieData.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
      </Pie>
      <Tooltip {...tooltipStyle()} />
    </PieChart>
  );
}

// ── ChartView main component (advanced gallery + basic toggle) ──

function ChartView({ rows, chart_suggestions }: {
  rows: Record<string, unknown>[];
  chart_suggestions?: ChartSuggestions | null;
}) {
  const t = useT();
  const [expandedSet, setExpandedSet] = useState<Set<number>>(new Set());
  const [activeBasic, setActiveBasic] = useState<string>("bar");

  const suggestions = useMemo(() => sanitizeSuggestions(chart_suggestions ?? undefined), [chart_suggestions]);
  const advanced = suggestions.advanced;
  const basicCfg = useMemo(() => suggestions.basic.find(c => c.chartType === activeBasic), [suggestions.basic, activeBasic]);

  const toggleExpand = (i: number) => {
    setExpandedSet(prev => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  };

  if (rows.length === 0 || (advanced.length === 0 && !basicCfg)) return null;

  return (
    <div className="mt-3 space-y-3">
      {/* Advanced gallery */}
      {advanced.length > 0 && (
        <div className="space-y-2">
          {advanced.map((cfg, i) => {
            const expanded = expandedSet.has(i);
            return (
              <div key={i} className="rounded-lg border border-border/50 bg-black/20 overflow-hidden transition-all duration-200">
                <div
                  className="flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-white/[0.03] transition-colors"
                  onClick={() => toggleExpand(i)}
                >
                  <div className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-ic-violet-soft/20 text-ic-violet shrink-0">{cfg.chartType}</div>
                  <div className="text-xs text-text/70 flex-1 truncate">{cfg.reason}</div>
                  <svg className={`w-3 h-3 text-muted transition-transform shrink-0 ${expanded ? 'rotate-180' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </div>
                {expanded && (
                  <div className="px-3 pb-3 space-y-2">
                    <ResponsiveContainer width="100%" height={280}>
                      {renderChartByType(cfg, rows)}
                    </ResponsiveContainer>
                    {cfg.howToRead && (
                      <div className="text-[10px] italic text-amber-400/80">{cfg.howToRead}</div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Basic toggle */}
      {suggestions.basic.length > 0 && (
        <div>
          <div className="flex gap-1.5 mb-2">
            {(["bar", "line", "area", "pie"] as const).map(t => (
              <button
                key={t}
                type="button"
                className={`text-[10px] font-medium px-2 py-0.5 rounded-full border transition-colors ${
                  activeBasic === t ? "bg-ic-violet-soft/20 text-ic-violet border-ic-violet/30" : "text-muted border-border/50 hover:text-text"
                }`}
                onClick={() => setActiveBasic(t)}
              >
                {t}
              </button>
            ))}
          </div>
          {basicCfg && (
            <div className="rounded-lg border border-border/50 bg-black/20 p-3">
              <ResponsiveContainer width="100%" height={250}>
                {renderChartByType(basicCfg, rows)}
              </ResponsiveContainer>
              {basicCfg.howToRead && (
                <div className="text-[10px] italic text-amber-400/80 mt-1">{basicCfg.howToRead}</div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── QueryActions (outer wrapper) ──

export function QueryActions({ queryResult }: { queryResult?: QueryResultState }) {
  const t = useT();
  const [showChart, setShowChart] = useState(false);

  const handleDownloadCsv = () => {
    if (!queryResult?.columns || !queryResult?.rows) return;
    const headers = queryResult.columns.join(",");
    const rows = queryResult.rows.map((r) => queryResult.columns!.map((c) => String(r[c] ?? "")).join(","));
    const csv = [headers, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "query-results.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  if (queryResult?.loading) {
    return (
      <div className="flex items-center gap-2 mt-3 text-xs text-muted">
        <span className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
        {t("query.generating")}
      </div>
    );
  }

  if (queryResult?.error) {
    return (
      <div className="mt-3 text-xs text-ic-red bg-ic-red/5 border border-ic-red/10 rounded-lg px-3 py-2">
        {queryResult.error}
      </div>
    );
  }

  if (queryResult?.columns && queryResult?.rows) {
    return (
      <div className="mt-3 space-y-2">
        {queryResult.sql && (
          <details className="text-xs">
            <summary className="text-muted cursor-pointer hover:text-text transition-colors bg-black/[0.08] px-2.5 py-1 rounded-lg">{t("query.sqlQuery")}</summary>
            <div className="relative mt-1">
              <pre className={`${monoClass} p-2 rounded-lg bg-black/30 border border-border/50 text-text/80 text-[11px] overflow-x-auto`}>{queryResult.sql}</pre>
              <button
                type="button"
                className="absolute top-2 right-2 w-6 h-6 flex items-center justify-center rounded hover:bg-white/[0.08] text-muted hover:text-text transition-colors"
                onClick={() => navigator.clipboard.writeText(queryResult.sql || "")}
                title={t("query.copySql")}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="12" height="12" strokeWidth="2.2">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                  <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                </svg>
              </button>
            </div>
          </details>
        )}
        <div className="flex items-center gap-2">
          <div className="text-[11px] text-muted">{tCount(t, "query.rowsReturned", queryResult.row_count ?? 0)}</div>
          <button
            type="button"
            className="text-[11px] font-medium px-1.5 py-0.5 rounded-full border bg-ic-teal-soft/40 text-ic-teal border-ic-teal/30 hover:bg-ic-teal-soft/60 transition-colors flex items-center gap-1"
            onClick={handleDownloadCsv}
            title={t("query.downloadCsv")}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="10" height="10" strokeWidth="2.2">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            {t("query.csv")}
          </button>
          <div className="flex gap-1.5">
            <button
              type="button"
              className={`text-[11px] font-medium px-2 py-0.5 rounded-full border transition-colors flex items-center gap-1 ${!showChart ? "bg-accent text-white border-accent" : "text-muted border-border/50 hover:text-text"}`}
              onClick={() => setShowChart(false)}
            >
              <IconGrid size={10} className="inline-block" />
              {t("query.table")}
            </button>
            <button
              type="button"
              className={`text-[11px] font-medium px-2 py-0.5 rounded-full border transition-colors flex items-center gap-1 ${showChart ? "bg-accent text-white border-accent" : "text-muted border-border/50 hover:text-text"}`}
              onClick={() => setShowChart(true)}
            >
              <IconChart size={10} className="inline-block" />
              {t("query.chart")}
            </button>
          </div>
        </div>
        {showChart ? (
          <ChartView rows={queryResult.rows} chart_suggestions={queryResult.chart_suggestions} />
        ) : (
          <>
            <div className="overflow-x-auto rounded-lg border border-border/50">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-[10px] font-semibold tracking-wider uppercase text-tertiary bg-black/[0.08]">
                    {queryResult.columns.map((col) => (
                      <th key={col} className="text-left py-1.5 px-2.5 whitespace-nowrap">{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {queryResult.rows.slice(0, 50).map((row, ri) => (
                    <tr key={ri} className="border-t border-border/20 hover:bg-white/[0.02]">
                      {queryResult.columns!.map((col) => (
                        <td key={col} className="py-1 px-2.5 text-text/80 whitespace-nowrap">{String(row[col] ?? "")}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {(queryResult.row_count ?? 0) > 50 && (
              <div className="text-[11px] text-muted">{t("query.showingFirst50", { count: queryResult.row_count ?? 0 })}</div>
            )}
          </>
        )}
      </div>
    );
  }

  return null;
}
