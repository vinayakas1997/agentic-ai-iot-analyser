import { useState, useRef } from "react";
import { monoClass } from "../lib/styles";
import { IconGrid, IconChart } from "../lib/icons";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, Legend,
} from "recharts";

export interface QueryResultState {
  loading: boolean;
  sql?: string;
  columns?: string[];
  rows?: Record<string, unknown>[];
  row_count?: number;
  error?: string;
}

const CHART_COLORS = ["#06b6d4", "#f59e0b", "#8b5cf6", "#3b82f6", "#ef4444", "#ec4899", "#f97316", "#22c55e", "#14b8a6", "#a855f7"];

function ChartView({ columns, rows }: { columns: string[]; rows: Record<string, unknown>[] }) {
  const [chartType, setChartType] = useState<"bar" | "line" | "pie">("bar");
  const chartRef = useRef<HTMLDivElement>(null);

  const handleDownloadPng = () => {
    const container = chartRef.current;
    if (!container) return;
    const svg = container.querySelector("svg");
    if (!svg) return;
    const svgData = new XMLSerializer().serializeToString(svg);
    const svgBlob = new Blob([svgData], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(svgBlob);
    const canvas = document.createElement("canvas");
    canvas.width = svg.clientWidth * 2;
    canvas.height = svg.clientHeight * 2;
    const ctx = canvas.getContext("2d");
    const img = new window.Image();
    img.onload = () => {
      if (ctx) ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      const pngUrl = canvas.toDataURL("image/png");
      const a = document.createElement("a");
      a.href = pngUrl;
      a.download = "chart.png";
      a.click();
    };
    img.src = url;
  };

  const downloadBtn = (
    <button
      type="button"
      className="text-[10px] font-medium px-1.5 py-0.5 rounded-full border border-border/50 text-muted hover:text-text transition-colors flex items-center gap-1 ml-auto"
      onClick={handleDownloadPng}
      title="Download PNG"
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="9" height="9" strokeWidth="2.2">
        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
      </svg>
      PNG
    </button>
  );

  if (rows.length === 0) return null;

  const numericCols = columns.filter((c) => rows.some((r) => typeof r[c] === "number"));
  const categoryCols = columns.filter((c) => columns.indexOf(c) !== 0 && !numericCols.includes(c));
  const xKey = columns[0];
  const yKeys = numericCols.length > 0 ? numericCols : [columns[columns.length - 1]];

  if (chartType === "pie") {
    const pieData = rows.map((r, i) => ({ name: String(r[xKey] ?? `Item ${i}`), value: Number(r[yKeys[0]] || 0) }));
    return (
      <div ref={chartRef} className="mt-3 space-y-2">
        <div className="flex gap-2">
          {["bar", "line", "pie"].map((t) => (
            <button
              key={t}
              type="button"
              className={`text-[10px] font-medium px-2 py-0.5 rounded-full border transition-colors ${chartType === t ? "bg-accent text-white border-accent" : "text-muted border-border/50 hover:text-text"}`}
              onClick={() => setChartType(t as any)}
            >
              {t}
            </button>
          ))}
          {downloadBtn}
        </div>
        <div className="rounded-lg border border-border/50 bg-black/20 p-3">
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                {pieData.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }

  const Chart = chartType === "line" ? LineChart : BarChart;

  return (
    <div ref={chartRef} className="mt-3 space-y-2">
      <div className="flex gap-2">
        {["bar", "line", "pie"].map((t) => (
          <button
            key={t}
            type="button"
            className={`text-[10px] font-medium px-2 py-0.5 rounded-full border transition-colors ${chartType === t ? "bg-accent text-white border-accent" : "text-muted border-border/50 hover:text-text"}`}
            onClick={() => setChartType(t as any)}
          >
            {t}
          </button>
        ))}
        {downloadBtn}
      </div>
      <div className="rounded-lg border border-border/50 bg-black/20 p-3">
        <ResponsiveContainer width="100%" height={250}>
          <Chart data={rows}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
            <XAxis dataKey={xKey} tick={{ fontSize: 10, fill: "#999" }} axisLine={{ stroke: "rgba(255,255,255,0.08)" }} tickLine={false} />
            <YAxis tick={{ fontSize: 10, fill: "#999" }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={{ background: "#1a1a2e", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, fontSize: 12 }} />
            {yKeys.map((k, i) => (
              chartType === "line"
                ? <Line key={k} type="monotone" dataKey={k} stroke={CHART_COLORS[i % CHART_COLORS.length]} strokeWidth={2} dot={{ r: 3 }} />
                : <Bar key={k} dataKey={k} fill={CHART_COLORS[i % CHART_COLORS.length]} radius={[4, 4, 0, 0]} />
            ))}
          </Chart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function QueryActions({ queryResult }: { queryResult?: QueryResultState }) {
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
        Generating query...
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
            <summary className="text-muted cursor-pointer hover:text-text transition-colors bg-black/[0.08] px-2.5 py-1 rounded-lg">SQL query</summary>
            <div className="relative mt-1">
              <pre className={`${monoClass} p-2 rounded-lg bg-black/30 border border-border/50 text-text/80 text-[11px] overflow-x-auto`}>{queryResult.sql}</pre>
              <button
                type="button"
                className="absolute top-2 right-2 w-6 h-6 flex items-center justify-center rounded hover:bg-white/[0.08] text-muted hover:text-text transition-colors"
                onClick={() => navigator.clipboard.writeText(queryResult.sql || "")}
                title="Copy SQL"
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
          <div className="text-[11px] text-muted">{queryResult.row_count} row{queryResult.row_count !== 1 ? "s" : ""} returned</div>
          <button
            type="button"
            className="text-[11px] font-medium px-1.5 py-0.5 rounded-full border bg-ic-teal-soft/40 text-ic-teal border-ic-teal/30 hover:bg-ic-teal-soft/60 transition-colors flex items-center gap-1"
            onClick={handleDownloadCsv}
            title="Download CSV"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="10" height="10" strokeWidth="2.2">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            CSV
          </button>
          <div className="flex gap-1.5 ml-auto">
            <button
              type="button"
              className={`text-[11px] font-medium px-2 py-0.5 rounded-full border transition-colors flex items-center gap-1 ${!showChart ? "bg-accent text-white border-accent" : "text-muted border-border/50 hover:text-text"}`}
              onClick={() => setShowChart(false)}
            >
              <IconGrid size={10} className="inline-block" />
              Table
            </button>
            <button
              type="button"
              className={`text-[11px] font-medium px-2 py-0.5 rounded-full border transition-colors flex items-center gap-1 ${showChart ? "bg-accent text-white border-accent" : "text-muted border-border/50 hover:text-text"}`}
              onClick={() => setShowChart(true)}
            >
              <IconChart size={10} className="inline-block" />
              Chart
            </button>
          </div>
        </div>
        {showChart ? (
          <ChartView columns={queryResult.columns} rows={queryResult.rows} />
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
            {queryResult.row_count > 50 && (
              <div className="text-[11px] text-muted">Showing first 50 of {queryResult.row_count} rows</div>
            )}
          </>
        )}
      </div>
    );
  }

  return null;
}
