import { useMemo } from "react";
import { cardClass } from "../lib/styles";
import { useSessionStore } from "../stores/sessionStore";
import { useUiStore } from "../stores/uiStore";
import {
  waitingCardClass, waitingMetaClass, lockedRowClass,
  resultCardClass, resultTagClass, resultBadgeClass,
  dividerLabelClass, previewFlagClass, outputGridClass,
  legendRowClass, legendItemClass, legendDotClass,
  miniTableClass, insightNoteClass,
} from "../lib/styles";
import { IconLock, IconCheckCircle, IconGrid } from "../lib/icons";

const outputPanelClass =
  "flex flex-col min-h-0 h-full overflow-hidden border-border p-4";

/* ── Divider label ── */
function DividerLabel({ children, first }: { children: React.ReactNode; first?: boolean }) {
  return (
    <div className={`${dividerLabelClass} ${first ? "mt-0" : "mt-5"}`}>
      {children}
      <span className="flex-1 h-px bg-border" />
    </div>
  );
}

/* ── Preview flag ── */
function PreviewFlag() {
  return (
    <div className={previewFlagClass}>
      <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 8v4M12 16h.01" />
      </svg>
      Illustrative only &mdash; not live data
    </div>
  );
}

/* ── Trend Lines Chart ── */
function TrendLinesChart() {
  return (
      <div className="rounded-xl border-2 border-stage-execution-line bg-surface-1 p-2.5 shadow-[0_0_22px_-12px_var(--stage-execution)]">
      <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-stage-execution mb-1.5">
        <span className={resultBadgeClass}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" width="10" height="10">
            <path d="M3 17l5-6 4 4 8-9" />
          </svg>
        </span>
        Execution &middot; Live indicators
      </div>
      <div className={legendRowClass}>
        <span className={legendItemClass}><span className={`${legendDotClass} bg-stage-execution`} />temp</span>
        <span className={legendItemClass}><span className={`${legendDotClass} bg-stage-planner`} />vibration</span>
        <span className={legendItemClass}><span className={`${legendDotClass} bg-stage-manager`} />pressure</span>
      </div>
      <svg viewBox="0 0 300 105" className="w-full h-auto block">
        <line x1="30" y1="10" x2="30" y2="85" stroke="rgba(255,255,255,0.09)" strokeWidth="1" />
        <line x1="30" y1="85" x2="290" y2="85" stroke="rgba(255,255,255,0.09)" strokeWidth="1" />

        <polyline fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" stroke="#3ddc97"
          points="30,40 65,46 100,36 135,50 170,42 205,54 240,44 275,48">
          <animate attributeName="points" dur="3.2s" repeatCount="indefinite"
            values="30,40 65,46 100,36 135,50 170,42 205,54 240,44 275,48;
                    30,44 65,36 100,48 135,40 170,52 205,42 240,54 275,42;
                    30,40 65,46 100,36 135,50 170,42 205,54 240,44 275,48" />
        </polyline>

        <polyline fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" stroke="#f0c419"
          points="30,56 65,50 100,60 135,44 170,58 205,40 240,52 275,36">
          <animate attributeName="points" dur="2.8s" repeatCount="indefinite"
            values="30,56 65,50 100,60 135,44 170,58 205,40 240,52 275,36;
                    30,50 65,58 100,42 135,56 170,38 205,54 240,34 275,50;
                    30,56 65,50 100,60 135,44 170,58 205,40 240,52 275,36" />
        </polyline>

        <polyline fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" stroke="#ff8a4c"
          points="30,32 65,54 100,28 135,60 170,30 205,48 240,24 275,56">
          <animate attributeName="points" dur="3.6s" repeatCount="indefinite"
            values="30,32 65,54 100,28 135,60 170,30 205,48 240,24 275,56;
                    30,54 65,28 100,58 135,26 170,50 205,28 240,56 275,26;
                    30,32 65,54 100,28 135,60 170,30 205,48 240,24 275,56" />
        </polyline>
      </svg>
    </div>
  );
}

/* ── Histogram Chart ── */
function HistogramChart() {
  const bars = [
    { x: 38, y: 65, h: 14, delay: "0s", dur: "2.6s", bd: "0.7s", a: 0.5, b: 2.0, c: 0.8 },
    { x: 76, y: 40, h: 39, delay: "0.06s", dur: "2.9s", bd: "0.9s", a: 0.6, b: 1.3, c: 0.85 },
    { x: 114, y: 13, h: 66, delay: "0.12s", dur: "2.3s", bd: "0.6s", a: 0.65, b: 0.95, c: 0.8 },
    { x: 152, y: 32, h: 47, delay: "0.18s", dur: "3.1s", bd: "1.1s", a: 0.55, b: 1.2, c: 0.8 },
    { x: 190, y: 57, h: 22, delay: "0.24s", dur: "2.5s", bd: "0.8s", a: 0.5, b: 1.7, c: 0.75 },
    { x: 228, y: 72, h: 7, delay: "0.3s", dur: "2.7s", bd: "1.0s", a: 0.6, b: 2.3, c: 0.8 },
  ];

  return (
    <div className="rounded-xl border-2 border-stage-execution-line bg-surface-1 p-2.5 shadow-[0_0_22px_-12px_var(--stage-execution)]">
      <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-stage-execution mb-1.5">
        <span className={resultBadgeClass}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" width="10" height="10">
            <rect x="3" y="12" width="4" height="9" />
            <rect x="10" y="7" width="4" height="14" />
            <rect x="17" y="3" width="4" height="18" />
          </svg>
        </span>
        Execution &middot; Reading distribution
      </div>
      <svg viewBox="0 0 300 105" className="w-full h-auto block">
        <line x1="30" y1="10" x2="30" y2="85" stroke="rgba(255,255,255,0.09)" strokeWidth="1" />
        <line x1="30" y1="85" x2="290" y2="85" stroke="rgba(255,255,255,0.09)" strokeWidth="1" />

        {bars.map((bar, i) => (
          <rect
            key={i}
            className="chart-bar"
            x={bar.x}
            y={bar.y}
            width="34"
            height={bar.h}
            fill="#3ddc97"
            opacity="0.85"
            style={{
              transformBox: "fill-box",
              transformOrigin: "bottom",
              animation: `growBar 0.55s cubic-bezier(.34,1.56,.64,1) ${bar.delay} backwards, bobBar ${bar.dur} ease-in-out ${bar.bd} infinite`,
              ["--bob-a" as string]: bar.a,
              ["--bob-b" as string]: bar.b,
              ["--bob-c" as string]: bar.c,
            }}
          />
        ))}

        <text x="55" y="96" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="7.5" fill="#64646f">18-20</text>
        <text x="93" y="96" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="7.5" fill="#64646f">20-22</text>
        <text x="131" y="96" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="7.5" fill="#64646f">22-24</text>
        <text x="169" y="96" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="7.5" fill="#64646f">24-26</text>
        <text x="207" y="96" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="7.5" fill="#64646f">26-28</text>
        <text x="245" y="96" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="7.5" fill="#64646f">28-30</text>
        <text x="150" y="104" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="7.5" fill="#64646f">temperature (&deg;C)</text>

        <text x="24" y="13" textAnchor="end" fontFamily="var(--font-mono)" fontSize="7.5" fill="#64646f">58</text>
        <text x="24" y="46" textAnchor="end" fontFamily="var(--font-mono)" fontSize="7.5" fill="#64646f">29</text>
        <text x="24" y="88" textAnchor="end" fontFamily="var(--font-mono)" fontSize="7.5" fill="#64646f">0</text>
      </svg>
      <div className={insightNoteClass}>
        Readings cluster around 22&ndash;24&deg;C; the 28&ndash;30&deg;C tail is worth flagging if it recurs.
      </div>
    </div>
  );
}

/* ── Scatter Plot Chart ── */
function ScatterPlotChart() {
  const dots: { cx: number; cy: number; delay: string; dur: string; dd: string; outlier?: boolean; variant?: string; style?: Record<string, string> }[] = [
    { cx: 52, cy: 66, delay: "0s", dur: "3.1s", dd: "0.4s" },
    { cx: 67, cy: 60, delay: "0.03s", dur: "2.7s", dd: "0.6s" },
    { cx: 79, cy: 64, delay: "0.06s", dur: "3.4s", dd: "0.5s" },
    { cx: 95, cy: 52, delay: "0.09s", dur: "2.9s", dd: "0.8s", outlier: true, variant: "converge", style: { "--conv-x": "25px", "--conv-y": "-11px", "--dx1": "2px", "--dy1": "-2px", "--dx3": "-2px", "--dy3": "2px" } },
    { cx: 108, cy: 49, delay: "0.12s", dur: "3.2s", dd: "0.3s" },
    { cx: 120, cy: 41, delay: "0.15s", dur: "2.6s", dd: "0.7s" },
    { cx: 145, cy: 36, delay: "0.18s", dur: "2.9s", dd: "0.8s", outlier: true, variant: "converge", style: { "--conv-x": "-25px", "--conv-y": "11px", "--dx1": "-2px", "--dy1": "2px", "--dx3": "2px", "--dy3": "-2px" } },
    { cx: 132, cy: 44, delay: "0.21s", dur: "2.8s", dd: "0.9s" },
    { cx: 160, cy: 39, delay: "0.24s", dur: "3.0s", dd: "0.4s" },
    { cx: 172, cy: 30, delay: "0.27s", dur: "3.3s", dd: "0.6s" },
    { cx: 185, cy: 33, delay: "0.3s", dur: "2.7s", dd: "0.3s" },
    { cx: 198, cy: 26, delay: "0.33s", dur: "3.1s", dd: "0.8s", outlier: true, variant: "wander", style: { "--dx1": "4px", "--dy1": "-5px", "--dx2": "-5px", "--dy2": "4px", "--dx3": "5px", "--dy3": "3px" } },
    { cx: 212, cy: 22, delay: "0.36s", dur: "2.9s", dd: "0.5s" },
    { cx: 225, cy: 20, delay: "0.39s", dur: "3.4s", dd: "0.7s" },
    { cx: 238, cy: 60, delay: "0.42s", dur: "2.6s", dd: "0.4s", outlier: true, variant: "wander", style: { "--dx1": "-4px", "--dy1": "4px", "--dx2": "5px", "--dy2": "-3px", "--dx3": "-3px", "--dy3": "5px" } },
    { cx: 250, cy: 16, delay: "0.45s", dur: "3.2s", dd: "0.6s" },
  ];

  return (
    <div className="rounded-xl border-2 border-stage-execution-line bg-surface-1 p-2.5 shadow-[0_0_22px_-12px_var(--stage-execution)]">
      <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-stage-execution mb-1.5">
        <span className={resultBadgeClass}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" width="10" height="10">
            <circle cx="6" cy="18" r="1.6" />
            <circle cx="10" cy="10" r="1.6" />
            <circle cx="14" cy="14" r="1.6" />
            <circle cx="18" cy="6" r="1.6" />
            <circle cx="9" cy="17" r="1.6" />
          </svg>
        </span>
        Execution &middot; Temp vs vibration
      </div>
      <svg viewBox="0 0 300 105" className="w-full h-auto block">
        <line x1="30" y1="10" x2="30" y2="85" stroke="rgba(255,255,255,0.09)" strokeWidth="1" />
        <line x1="30" y1="85" x2="290" y2="85" stroke="rgba(255,255,255,0.09)" strokeWidth="1" />

        {dots.map((dot, i) => (
          <circle
            key={i}
            className={`chart-dot ${dot.outlier ? "wander" : ""} ${dot.variant === "converge" ? "converge" : ""}`}
            cx={dot.cx}
            cy={dot.cy}
            r="3.5"
            fill={dot.outlier ? "#f0c419" : "#3ddc97"}
            opacity="0.8"
            style={{
              transformBox: "fill-box",
              transformOrigin: "center",
              animation: `popIn 0.4s cubic-bezier(.34,1.56,.64,1) ${dot.delay} backwards, ${dot.variant === "converge" ? "driftConverge" : dot.variant === "wander" ? "driftWide" : "driftDot"} ${dot.dur} ease-in-out ${dot.dd} infinite`,
              ...dot.style,
            }}
          />
        ))}

        <text x="150" y="104" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="7.5" fill="#64646f">temperature (&deg;C)</text>
        <text x="10" y="22" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="7.5" fill="#64646f" transform="rotate(-90 10 47)">vibration (mm/s)</text>
      </svg>
    </div>
  );
}

/* ── Preview Data Table ── */
function PreviewDataTable() {
  const rows = [
    { name: "TRITON-02", reading: "22.3\u00B0C", vibration: "1.4 mm/s" },
    { name: "TRITON-04", reading: "24.8\u00B0C", vibration: "1.1 mm/s" },
    { name: "TRITON-07", reading: "28.9\u00B0C", vibration: "3.6 mm/s" },
  ];

  return (
    <div className="rounded-xl border-2 border-stage-execution-line bg-surface-1 p-2.5 shadow-[0_0_22px_-12px_var(--stage-execution)]">
      <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-stage-execution mb-1.5">
        <span className={resultBadgeClass}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" width="10" height="10">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <path d="M3 9h18M3 15h18M9 3v18" />
          </svg>
        </span>
        Execution &middot; Detail table
      </div>
      <table className={miniTableClass}>
        <thead>
          <tr>
            <th className="text-left text-[9px] font-semibold uppercase tracking-wider text-tertiary py-1 px-1.5 border-b-2 border-border">Sensor</th>
            <th className="text-right text-[9px] font-semibold uppercase tracking-wider text-tertiary py-1 px-1.5 border-b-2 border-border">Reading</th>
            <th className="text-right text-[9px] font-semibold uppercase tracking-wider text-tertiary py-1 px-1.5 border-b-2 border-border">Vibration</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.name}>
              <td className="py-1 px-1.5 text-muted border-b-2 border-white/[0.03] font-mono text-[10.5px] text-text">{row.name}</td>
              <td className="py-1 px-1.5 text-muted border-b-2 border-white/[0.03] font-mono text-[10.5px] text-right text-stage-execution">{row.reading}</td>
              <td className="py-1 px-1.5 text-muted border-b-2 border-white/[0.03] font-mono text-[10.5px] text-right text-stage-execution">{row.vibration}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ── Preview Charts (dimmed) ── */
function PreviewCharts() {
  return (
    <div className="opacity-40">
      <PreviewFlag />
      <div className={outputGridClass}>
        <TrendLinesChart />
        <HistogramChart />
        <ScatterPlotChart />
        <PreviewDataTable />
      </div>
    </div>
  );
}

/* ── Waiting on Planner ── */
function WaitingOnPlanner() {
  return (
    <div className={waitingCardClass}>
      <div className="w-9 h-9 rounded-xl bg-stage-planner-soft text-stage-planner flex items-center justify-center mx-auto mb-2">
        <IconCheckCircle size={18} />
      </div>
      <h3 className="font-display text-[13px] font-semibold text-text mb-1">
        Waiting on Planner
      </h3>
      <p className="text-[11.5px] text-muted leading-relaxed max-w-[260px] mx-auto mb-2.5">
        Manager has scoped the aim. Once Planner builds a query plan, it'll
        appear here — followed by Execution's results.
      </p>
      <div className={waitingMetaClass}>
        <span className="w-1.5 h-1.5 rounded-full bg-stage-planner animate-[pulse_1.6s_ease-in-out_infinite]" />
        Planner not yet started
      </div>
      <div className={lockedRowClass}>
        <IconLock size={13} />
        <span>Execution results will appear once Planner completes</span>
      </div>
    </div>
  );
}

/* ── Execution progress & results ── */
function ExecutionProgress() {
  const executionEvents = useSessionStore((s) => s.executionEvents);
  const lastEvent = useMemo(() => {
    return executionEvents.length > 0 ? executionEvents[executionEvents.length - 1] : null;
  }, [executionEvents]);

  // Waiting on Planner
  if (!executionEvents.length) {
    return <WaitingOnPlanner />;
  }

  const statusFromEvent = (topic: string) => {
    switch (topic) {
      case "planner.start":
        return { label: "Planning queries\u2026", color: "text-stage-planner" };
      case "executor.run":
        return { label: "Running query\u2026", color: "text-stage-execution" };
      case "planner.result":
        return { label: "Planner complete", color: "text-stage-planner" };
      case "planner.retry":
        return { label: "Retrying query\u2026", color: "text-stage-planner" };
      case "task.complete":
        return { label: "Task complete", color: "text-stage-execution" };
      case "task.failed":
        return { label: "Task failed", color: "text-red-400" };
      default:
        return { label: topic, color: "text-muted" };
    }
  };

  const status = statusFromEvent(lastEvent?.topic || "");

  // Complete → show structured results
  if (lastEvent?.topic === "task.complete") {
    const payload = lastEvent.payload as Record<string, unknown>;
    const data = payload?.data as Record<string, unknown> | undefined;
    const results = data?.results as Record<string, unknown>[] | undefined;

    return (
      <>
        {results && results.length > 0 ? (
          results.map((r, i) => (
            <div key={i} className={resultCardClass}>
              <div className={resultTagClass}>
                <span className={resultBadgeClass}>
                  <IconGrid size={12} />
                </span>
                Execution &middot; {r.title ? String(r.title) : `Query ${i + 1}`}
              </div>
              <pre className="bg-black/30 p-2.5 rounded-lg overflow-x-auto whitespace-pre-wrap text-[12px] text-muted leading-relaxed">
                {JSON.stringify(r, null, 2)}
              </pre>
            </div>
          ))
        ) : (
          <div className={resultCardClass}>
            <div className={resultTagClass}>
              <span className={resultBadgeClass}>
                <IconCheckCircle size={12} />
              </span>
              Execution &middot; Complete
            </div>
            <p className="text-sm text-stage-execution">{status.label}</p>
          </div>
        )}
      </>
    );
  }

  // Running / intermediate state
  return (
    <div className={cardClass}>
      <div className="flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-stage-planner animate-pulse" />
        <p className={`text-sm ${status.color}`}>{status.label}</p>
      </div>
    </div>
  );
}

export default function OutputSection() {
  const turns = useSessionStore((s) => s.turns);
  const selectedTurnIndex = useUiStore((s) => s.selectedTurnIndex);
  const executionEvents = useSessionStore((s) => s.executionEvents);

  const hasRealResults = lastEventTopic(executionEvents) === "task.complete";

  return (
    <section className={`${outputPanelClass} order-3 lg:order-none`}>
      <div className="flex items-center justify-between mb-3 shrink-0">
        <h2 className="text-base font-semibold font-display">Outputs</h2>
        <p className="text-xs text-muted">
          Step {turns.length > 0 ? selectedTurnIndex + 1 : 0} of {turns.length}
        </p>
      </div>

      <div className="flex-1 overflow-hidden min-h-0">
        <DividerLabel first>Current state</DividerLabel>

        <ExecutionProgress />

        {!hasRealResults && <PreviewCharts />}
      </div>
    </section>
  );
}

function lastEventTopic(events: { topic: string }[]): string {
  return events.length ? events[events.length - 1].topic : "";
}
