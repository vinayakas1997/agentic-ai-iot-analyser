import { useState, useEffect } from "react";
import { useT } from "../lib/i18n";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const COLORS = ["#3b82f6", "#f59e0b", "#22c55e", "#ef4444", "#8b5cf6"];

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export default function TourDemoCharts({ onNext }: { onNext: () => void }) {
  const t = useT();
  const [explanation, setExplanation] = useState("");

  const aiExplanation = t("tour.chartAiExplanation");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      for (let i = 0; i <= aiExplanation.length; i++) {
        if (cancelled) break;
        setExplanation(aiExplanation.slice(0, i));
        await sleep(12);
      }
    })();
    return () => { cancelled = true; };
  }, [aiExplanation]);

  const charts = [
    {
      title: t("tour.chartBarTitle"),
      description: t("tour.chartBarDesc"),
      ChartComp: BarChart,
      children: (
        <>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis dataKey="machine" stroke="#999" tick={{ fontSize: 11 }} />
          <YAxis stroke="#999" tick={{ fontSize: 11 }} />
          <Tooltip contentStyle={{ background: "#1a1a2e", border: "1px solid #333", borderRadius: 8, fontSize: 12 }} />
          <Bar dataKey="output" fill="#3b82f6" radius={[4, 4, 0, 0]} />
        </>
      ),
      data: [
        { machine: "CNC-001", output: 4500 },
        { machine: "CNC-002", output: 3800 },
        { machine: "CNC-003", output: 4200 },
        { machine: "CNC-004", output: 4100 },
        { machine: "CNC-005", output: 3900 },
      ],
    },
    {
      title: t("tour.chartLineTitle"),
      description: t("tour.chartLineDesc"),
      ChartComp: LineChart,
      children: (
        <>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis dataKey="week" stroke="#999" tick={{ fontSize: 11 }} />
          <YAxis stroke="#999" tick={{ fontSize: 11 }} />
          <Tooltip contentStyle={{ background: "#1a1a2e", border: "1px solid #333", borderRadius: 8, fontSize: 12 }} />
          <Line type="monotone" dataKey="output" stroke="#22c55e" strokeWidth={2} dot={{ r: 4 }} />
        </>
      ),
      data: [
        { week: "W1", output: 1200 },
        { week: "W2", output: 1900 },
        { week: "W3", output: 1500 },
        { week: "W4", output: 2200 },
        { week: "W5", output: 2800 },
        { week: "W6", output: 2500 },
      ],
    },
    {
      title: t("tour.chartPieTitle"),
      description: t("tour.chartPieDesc"),
      ChartComp: PieChart,
      children: (
        <>
          <Pie
            dataKey="defects"
            nameKey="machine"
            cx="50%"
            cy="50%"
            outerRadius={70}
            label={({ name, value }) => `${name} ${value}%`}
            labelLine
          >
            {[
              { machine: "CNC-001", defects: 35 },
              { machine: "CNC-002", defects: 25 },
              { machine: "CNC-003", defects: 20 },
              { machine: "CNC-004", defects: 12 },
              { machine: "CNC-005", defects: 8 },
            ].map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip contentStyle={{ background: "#1a1a2e", border: "1px solid #333", borderRadius: 8, fontSize: 12 }} />
        </>
      ),
      data: [
        { machine: "CNC-001", defects: 35 },
        { machine: "CNC-002", defects: 25 },
        { machine: "CNC-003", defects: 20 },
        { machine: "CNC-004", defects: 12 },
        { machine: "CNC-005", defects: 8 },
      ],
    },
  ];

  const progress = aiExplanation.length ? explanation.length / aiExplanation.length : 0;
  const revealed = Math.min(charts.length, Math.floor((charts.length + 1) * progress));

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm overflow-y-auto py-8">
      <div className="rounded-2xl border border-border bg-surface-1 p-6 shadow-2xl max-w-3xl w-full mx-4">
        <div className="flex items-center gap-2 mb-1">
          <span className="inline-flex items-center justify-center w-7 h-7 rounded-lg bg-ic-amber-soft text-ic-amber text-sm font-bold">
            6
          </span>
          <h2 className="text-lg font-semibold text-text">{t("tour.chartIntroHeading")}</h2>
        </div>
        <p className="text-sm text-muted mb-3">
          {t("tour.chartIntroText")}
        </p>

        <p className="text-xs font-bold text-white leading-relaxed mb-4 min-h-[2.5em]">
          {explanation}
          {explanation.length < aiExplanation.length && (
            <span className="inline-block w-1 h-3.5 bg-white/70 ml-0.5 animate-pulse" />
          )}
        </p>

        <div className="space-y-5">
          {charts.map((chart, ci) => (
            <div
              key={chart.title}
              className="rounded-xl border border-border bg-surface-2 overflow-hidden"
            >
              <div className="p-4 pb-0">
                <h3 className="text-sm font-semibold text-text mb-1">{chart.title}</h3>
                <p className="text-xs text-muted leading-relaxed mb-3">{chart.description}</p>
              </div>
              <div className="h-[200px] w-full">
                {ci < revealed ? (
                  <div className="chart-reveal h-full w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <chart.ChartComp data={chart.data as any[]}>{chart.children}</chart.ChartComp>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <div className="h-full w-full animate-pulse bg-white/[0.03] p-6 flex items-end justify-center gap-4">
                    {[40, 70, 55, 85, 60, 75].map((h, bi) => (
                      <div
                        key={bi}
                        className="w-8 max-w-[8%] rounded-t bg-white/[0.08]"
                        style={{ height: `${h}%` }}
                      />
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="flex justify-end mt-5">
          <button
            type="button"
            className="px-5 py-2 text-sm rounded-lg bg-accent text-white hover:bg-[#1d8cf0] transition-colors font-medium"
            onClick={onNext}
          >
            {t("tour.next")}
          </button>
        </div>
      </div>
    </div>
  );
}
