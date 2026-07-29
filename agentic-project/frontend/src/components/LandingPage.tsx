import { useEffect, useRef } from "react";
import { useUiStore } from "../stores/uiStore";
import type { Language } from "../lib/translations";

interface Scenario {
  file: string;
  sub: string;
  question: string;
  color: string;
  num: number;
  unit: string;
  kind: "line" | "bar" | "scatter";
}

const SCENARIOS: Record<Language, Scenario[]> = {
  en: [
    {
      file: "line3_defects.csv",
      sub: "4,812 rows · uploaded",
      question: "What's the defect rate trend for Line 3 this month?",
      color: "var(--color-stage-execution)",
      num: 4.2,
      unit: "% defect rate",
      kind: "line",
    },
    {
      file: "machine_downtime.csv",
      sub: "1,340 rows · uploaded",
      question: "Which machine has the most downtime this week?",
      color: "var(--color-ic-amber)",
      num: 18.6,
      unit: "hrs · Press-04",
      kind: "bar",
    },
    {
      file: "shift_throughput.csv",
      sub: "9,027 rows · uploaded",
      question: "How does throughput compare to target by shift?",
      color: "var(--color-ic-blue)",
      num: 96.3,
      unit: "% of target",
      kind: "scatter",
    },
  ],
  ja: [
    {
      file: "line3_defects.csv",
      sub: "4,812件・アップロード済み",
      question: "今月のライン3の不良率の推移は?",
      color: "var(--color-stage-execution)",
      num: 4.2,
      unit: "% 不良率",
      kind: "line",
    },
    {
      file: "machine_downtime.csv",
      sub: "1,340件・アップロード済み",
      question: "今週、最もダウンタイムが多い設備は?",
      color: "var(--color-ic-amber)",
      num: 18.6,
      unit: "時間 · プレス機04",
      kind: "bar",
    },
    {
      file: "shift_throughput.csv",
      sub: "9,027件・アップロード済み",
      question: "シフト別の生産量は目標に対してどうか?",
      color: "var(--color-ic-blue)",
      num: 96.3,
      unit: "%（目標比）",
      kind: "scatter",
    },
  ],
};

const COPY: Record<
  Language,
  {
    brand: string;
    eyebrow: string;
    headline1: string;
    headline2: string;
    subhead: string;
    ctaPrimary: string;
    ctaSecondary: string;
    fineprint: string;
    flowSource: string;
    flowQuestion: string;
    flowResult: string;
    featuresEyebrow: string;
    featuresTitle: string;
    f1Title: string;
    f1Desc: string;
    f2Title: string;
    f2Desc: string;
    f3Title: string;
    f3Desc: string;
    closingTitle: string;
    creditName: string;
    creditDept: string;
  }
> = {
  en: {
    brand: "Agentic IoT Data Analyser",
    eyebrow: "Live on your factory data",
    headline1: "Ask your data a question.",
    headline2: "Watch the analysis build itself.",
    subhead:
      "Upload a CSV or connect a database from the shop floor. Ask what you want to know in plain language — the agent reads your data, reasons through it, and hands back the chart.",
    ctaPrimary: "Get Started",
    ctaSecondary: "See how it works",
    fineprint: "No setup required · works with the CSVs you already export",
    flowSource: "Your data",
    flowQuestion: "Your question",
    flowResult: "AI result",
    featuresEyebrow: "What it does",
    featuresTitle: "Everything between raw CSV and finished chart",
    f1Title: "Flexible data input",
    f1Desc:
      "Upload a CSV export or connect a database directly. No schema mapping, no pre-cleaning — point it at your data and start asking.",
    f2Title: "Built-in summarizer",
    f2Desc:
      "Every chart and finding you've pulled up gets rolled into one running summary, so you always know what you've already learned.",
    f3Title: "12+ chart types",
    f3Desc:
      "Line, bar, scatter, heatmap and more — the agent picks the chart that actually fits your question instead of defaulting to one format.",
    closingTitle: "Point it at your data. Ask the question.",
    creditName: "Name: Sajjanshetty Vinayaka",
    creditDept: "Dept: CPS",
  },
  ja: {
    brand: "Agentic IoT Data Analyser",
    eyebrow: "工場データにそのまま対応",
    headline1: "データに問いかける。",
    headline2: "分析が、その場で形になる。",
    subhead:
      "現場のCSVをアップロードするか、データベースに接続するだけ。知りたいことを日本語で聞くと、AIがデータを読み解き、グラフにして返します。",
    ctaPrimary: "はじめる",
    ctaSecondary: "使い方を見る",
    fineprint: "セットアップ不要・普段お使いのCSVでそのまま使えます",
    flowSource: "データ",
    flowQuestion: "質問",
    flowResult: "AI分析結果",
    featuresEyebrow: "できること",
    featuresTitle: "CSVからグラフ完成まで、すべてお任せ",
    f1Title: "柔軟なデータ入力",
    f1Desc:
      "CSVをアップロードするか、データベースに直接接続。スキーマ設定や事前整形は不要 — データを指定してすぐに質問できます。",
    f2Title: "自動サマライザー",
    f2Desc:
      "これまでに作成したグラフや発見はすべて自動で要約されるので、何を分析したか常に把握できます。",
    f3Title: "12種類以上のグラフ",
    f3Desc:
      "折れ線・棒・散布図・ヒートマップなど — 質問内容に最も適したグラフをAIが自動で選択します。",
    closingTitle: "データを指定して、質問するだけ。",
    creditName: "氏名: ビナヤカ・サジャンシェティ",
    creditDept: "部署: CPS",
  },
};

const SVG_NS = "http://www.w3.org/2000/svg";

export default function LandingPage({ onGetStarted }: { onGetStarted: () => void }) {
  const language = useUiStore((s) => s.language);
  const setLanguage = useUiStore((s) => s.setLanguage);
  const copy = COPY[language];

  const fileIconRef = useRef<HTMLDivElement>(null);
  const fileNameRef = useRef<HTMLDivElement>(null);
  const fileSubRef = useRef<HTMLDivElement>(null);
  const conn1Ref = useRef<HTMLDivElement>(null);
  const conn2Ref = useRef<HTMLDivElement>(null);
  const chatTextRef = useRef<HTMLDivElement>(null);
  const chartSvgRef = useRef<SVGSVGElement>(null);
  const chartNumRef = useRef<HTMLSpanElement>(null);
  const chartUnitRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const scenarios = SCENARIOS[language];
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const timeouts: number[] = [];
    let cancelled = false;

    const wait = (ms: number) =>
      new Promise<void>((resolve) => {
        const id = window.setTimeout(resolve, reduced ? 0 : ms);
        timeouts.push(id);
      });

    function setConn(el: HTMLDivElement | null, mode: "active" | "pulse" | null, color: string) {
      if (!el) return;
      el.classList.remove("active", "pulse");
      el.style.setProperty("--flow-color", color);
      if (mode) el.classList.add(mode);
    }

    function buildChart(kind: Scenario["kind"], color: string) {
      const svg = chartSvgRef.current;
      if (!svg) return;
      svg.innerHTML = "";

      if (kind === "line") {
        const pts: [number, number][] = [
          [4, 58], [38, 44], [72, 50], [106, 24], [140, 32], [174, 14], [216, 20],
        ];
        const d = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p[0]} ${p[1]}`).join(" ");
        const path = document.createElementNS(SVG_NS, "path");
        path.setAttribute("d", d);
        path.setAttribute("fill", "none");
        path.setAttribute("stroke", color);
        path.setAttribute("stroke-width", "2.5");
        path.setAttribute("stroke-linecap", "round");
        path.setAttribute("stroke-linejoin", "round");
        path.setAttribute("stroke-dasharray", "260");
        path.setAttribute("stroke-dashoffset", "260");
        path.style.filter = `drop-shadow(0 0 5px ${color})`;
        path.style.transition = reduced ? "none" : "stroke-dashoffset 1.5s cubic-bezier(.4,0,.2,1)";
        svg.appendChild(path);
        pts.forEach((p, i) => {
          const c = document.createElementNS(SVG_NS, "circle");
          c.setAttribute("cx", String(p[0]));
          c.setAttribute("cy", String(p[1]));
          c.setAttribute("r", "3");
          c.setAttribute("fill", color);
          c.style.opacity = "0";
          c.style.transition = reduced ? "none" : "opacity 0.3s ease";
          c.style.transitionDelay = `${i * 0.19}s`;
          svg.appendChild(c);
        });
        requestAnimationFrame(() =>
          requestAnimationFrame(() => {
            path.setAttribute("stroke-dashoffset", "0");
            svg.querySelectorAll("circle").forEach((c) => ((c as SVGElement).style.opacity = "1"));
          })
        );
      }

      if (kind === "bar") {
        const vals = [30, 52, 24, 66, 40];
        vals.forEach((v, i) => {
          const x = 8 + i * 44;
          const r = document.createElementNS(SVG_NS, "rect");
          r.setAttribute("x", String(x));
          r.setAttribute("width", "26");
          r.setAttribute("y", "74");
          r.setAttribute("height", "0");
          r.setAttribute("rx", "3");
          r.setAttribute("fill", color);
          r.style.opacity = "0.9";
          r.style.filter = `drop-shadow(0 0 5px ${color})`;
          r.style.transition = reduced
            ? "none"
            : "y 0.6s cubic-bezier(.34,1.4,.64,1), height 0.6s cubic-bezier(.34,1.4,.64,1)";
          r.style.transitionDelay = `${i * 0.12}s`;
          svg.appendChild(r);
          requestAnimationFrame(() =>
            requestAnimationFrame(() => {
              r.setAttribute("y", String(74 - v));
              r.setAttribute("height", String(v));
            })
          );
        });
      }

      if (kind === "scatter") {
        const dots: [number, number][] = [
          [10, 40], [34, 58], [52, 20], [70, 46], [92, 30], [112, 60],
          [134, 16], [152, 38], [172, 50], [192, 26], [210, 44],
        ];
        dots.forEach((p, i) => {
          const c = document.createElementNS(SVG_NS, "circle");
          c.setAttribute("cx", String(p[0]));
          c.setAttribute("cy", String(p[1]));
          c.setAttribute("r", "3.4");
          c.setAttribute("fill", color);
          c.style.opacity = "0";
          c.style.filter = `drop-shadow(0 0 4px ${color})`;
          c.style.transformOrigin = `${p[0]}px ${p[1]}px`;
          c.style.transform = "scale(0.3)";
          c.style.transition = reduced ? "none" : "opacity 0.35s ease, transform 0.35s cubic-bezier(.34,1.6,.64,1)";
          c.style.transitionDelay = `${i * 0.06}s`;
          svg.appendChild(c);
          requestAnimationFrame(() =>
            requestAnimationFrame(() => {
              c.style.opacity = "1";
              c.style.transform = "scale(1)";
            })
          );
        });
        const trend = document.createElementNS(SVG_NS, "line");
        trend.setAttribute("x1", "4");
        trend.setAttribute("y1", "52");
        trend.setAttribute("x2", "216");
        trend.setAttribute("y2", "22");
        trend.setAttribute("stroke", color);
        trend.setAttribute("stroke-width", "1.5");
        trend.setAttribute("stroke-dasharray", "3 4");
        trend.style.opacity = "0";
        trend.style.transition = reduced ? "none" : "opacity 0.5s ease";
        trend.style.transitionDelay = "0.7s";
        svg.appendChild(trend);
        requestAnimationFrame(() => requestAnimationFrame(() => (trend.style.opacity = "0.6")));
      }
    }

    function animateNum(target: number, unitText: string, color: string) {
      const numEl = chartNumRef.current;
      const unitEl = chartUnitRef.current;
      if (!numEl || !unitEl) return;
      numEl.style.color = color;
      unitEl.textContent = unitText;
      let startT: number | null = null;
      const dur = reduced ? 1 : 900;
      function step(ts: number) {
        if (cancelled) return;
        if (startT === null) startT = ts;
        const p = Math.min(1, (ts - startT) / dur);
        const eased = 1 - Math.pow(1 - p, 3);
        numEl!.textContent = (target * eased).toFixed(1);
        if (p < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    }

    function typeText(text: string): Promise<void> {
      return new Promise((resolve) => {
        const container = chatTextRef.current;
        if (!container) return resolve();
        container.innerHTML = "";
        const span = document.createElement("span");
        container.appendChild(span);
        const cursor = document.createElement("span");
        cursor.className = "landing-cursor";
        container.appendChild(cursor);
        let i = 0;
        const speed = reduced ? 0 : 34;
        function tick() {
          if (cancelled) return;
          if (i <= text.length) {
            span.textContent = text.slice(0, i);
            i++;
            if (speed) {
              const id = window.setTimeout(tick, speed);
              timeouts.push(id);
            } else {
              tick();
            }
          } else {
            resolve();
          }
        }
        tick();
      });
    }

    async function runCycle(idx: number) {
      if (cancelled) return;
      const s = scenarios[idx];

      fileIconRef.current?.classList.remove("active");
      if (chatTextRef.current) chatTextRef.current.innerHTML = '<span class="landing-cursor"></span>';
      if (chartSvgRef.current) chartSvgRef.current.innerHTML = "";
      if (chartNumRef.current) chartNumRef.current.textContent = "0";
      setConn(conn1Ref.current, null, s.color);
      setConn(conn2Ref.current, null, s.color);

      if (fileNameRef.current) fileNameRef.current.textContent = s.file;
      if (fileSubRef.current) fileSubRef.current.textContent = s.sub;

      fileIconRef.current?.classList.add("active");

      await wait(500);
      if (cancelled) return;
      setConn(conn1Ref.current, "active", "var(--color-accent)");
      await wait(900);
      if (cancelled) return;
      setConn(conn1Ref.current, null, s.color);
      fileIconRef.current?.classList.remove("active");

      await typeText(s.question);
      if (cancelled) return;

      setConn(conn2Ref.current, "pulse", "var(--color-accent)");
      await wait(750);
      if (cancelled) return;

      setConn(conn2Ref.current, "active", s.color);
      buildChart(s.kind, s.color);
      animateNum(s.num, s.unit, s.color);
      await wait(1500);
      if (cancelled) return;

      setConn(conn2Ref.current, null, s.color);
      await wait(reduced ? 0 : 2600);
      if (cancelled) return;

      if (!reduced) runCycle((idx + 1) % scenarios.length);
    }

    runCycle(0);

    return () => {
      cancelled = true;
      timeouts.forEach((id) => window.clearTimeout(id));
    };
  }, [language]);

  return (
    <div className="relative h-screen overflow-y-auto bg-bg-deep text-text">
      <div className="landing-grid-bg" />
      <div
        className="fixed top-[14%] left-[8%] w-[5px] h-[5px] rounded-full bg-stage-execution shadow-[0_0_10px_2px_rgba(61,220,151,0.65)] animate-sensor-blink"
        style={{ animationDelay: "0s" }}
      />
      <div
        className="fixed top-[22%] left-[88%] w-[5px] h-[5px] rounded-full bg-stage-execution shadow-[0_0_10px_2px_rgba(61,220,151,0.65)] animate-sensor-blink"
        style={{ animationDelay: "1.1s" }}
      />
      <div
        className="fixed top-[6%] left-[52%] w-[5px] h-[5px] rounded-full bg-stage-execution shadow-[0_0_10px_2px_rgba(61,220,151,0.65)] animate-sensor-blink"
        style={{ animationDelay: "2s" }}
      />

      <main className="relative z-10 max-w-[1180px] mx-auto px-7 pb-24">
        {/* Topbar */}
        <div className="flex items-center justify-between gap-2.5 pt-7">
          <div className="flex items-center gap-2.5 font-display font-semibold text-[15px]">
            <span className="w-[22px] h-[22px] rounded-md bg-gradient-to-br from-accent to-stage-execution grid place-items-center shadow-[0_0_18px_-4px_rgba(124,111,239,0.7)] shrink-0">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#08080b" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 17l5-6 4 4 8-9" />
              </svg>
            </span>
            {copy.brand}
          </div>
          <div className="flex rounded-full border border-border bg-surface-1 overflow-hidden shrink-0">
            <button
              type="button"
              className={`text-[11px] font-semibold px-2.5 py-1 transition-colors ${
                language === "en" ? "bg-ic-amber text-black" : "text-text hover:bg-white/[0.06]"
              }`}
              onClick={() => setLanguage("en")}
            >
              EN
            </button>
            <div className="w-px bg-border self-stretch" />
            <button
              type="button"
              className={`text-[11px] font-semibold px-2.5 py-1 transition-colors ${
                language === "ja" ? "bg-ic-amber text-black" : "text-text hover:bg-white/[0.06]"
              }`}
              onClick={() => setLanguage("ja")}
            >
              日本語
            </button>
          </div>
        </div>
        <div className="text-right text-[10.5px] text-tertiary mt-1.5">
          {copy.creditName} &middot; {copy.creditDept}
        </div>

        {/* Hero */}
        <section className="pt-20 pb-2 text-center">
          <span className="inline-flex items-center gap-1.5 font-mono text-[11px] tracking-[0.14em] uppercase text-stage-execution bg-stage-execution-soft border border-stage-execution-line rounded-full pl-2.5 pr-3.5 py-1.5 mb-6">
            <span className="w-1.5 h-1.5 rounded-full bg-stage-execution shadow-[0_0_8px_1px_var(--color-stage-execution)] animate-sensor-blink" />
            {copy.eyebrow}
          </span>
          <h1 className="font-display font-bold text-[34px] sm:text-[46px] lg:text-[62px] leading-[1.06] tracking-[-0.015em] mb-5" style={{ textWrap: "balance" }}>
            {copy.headline1}
            <br />
            <span className="bg-gradient-to-r from-accent via-ic-blue to-stage-execution bg-clip-text text-transparent">
              {copy.headline2}
            </span>
          </h1>
          <p className="text-[15px] sm:text-[18px] leading-relaxed text-muted max-w-[620px] mx-auto mb-9" style={{ textWrap: "balance" }}>
            {copy.subhead}
          </p>
          <div className="flex items-center justify-center gap-3.5 flex-wrap mb-4">
            <button
              type="button"
              onClick={onGetStarted}
              className="font-body font-semibold text-[14.5px] text-[#0a0a0f] bg-gradient-to-r from-stage-execution to-[#6be8b3] rounded-[11px] px-6.5 py-3.5 shadow-[0_0_0_1px_rgba(61,220,151,0.3),0_8px_30px_-8px_rgba(61,220,151,0.55)] hover:-translate-y-px transition-transform focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2"
            >
              {copy.ctaPrimary}
            </button>
            <a
              href="#features"
              className="font-body font-medium text-[14.5px] text-text bg-white/[0.04] border border-border rounded-[11px] px-5.5 py-3.5 hover:border-white/25 hover:bg-white/[0.07] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2"
            >
              {copy.ctaSecondary}
            </a>
          </div>
          <p className="text-[12.5px] text-tertiary mb-16">{copy.fineprint}</p>
        </section>

        {/* Flow diagram */}
        <div className="mb-24">
          <div className="flex items-stretch max-[820px]:flex-col">
            {/* Source panel */}
            <div className="flex-1 min-w-0 bg-gradient-to-b from-surface-1 to-surface-2 border border-border rounded-2xl p-4.5 flex flex-col">
              <div className="flex items-center gap-1.5 font-mono text-[10px] tracking-[0.11em] uppercase text-tertiary mb-3.5" style={{ color: "var(--color-accent)" }}>
                <span className="w-1.5 h-1.5 rounded-full bg-current" />
                {copy.flowSource}
              </div>
              <div className="flex items-center gap-3 flex-1">
                <div
                  ref={fileIconRef}
                  className="w-10 h-10 rounded-[10px] bg-[rgba(124,111,239,0.14)] border border-[rgba(124,111,239,0.35)] grid place-items-center text-accent shrink-0 transition-all duration-300 [&.active]:shadow-[0_0_22px_-2px_rgba(124,111,239,0.6)] [&.active]:scale-[1.06]"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <path d="M14 2v6h6" />
                  </svg>
                </div>
                <div>
                  <div ref={fileNameRef} className="font-mono text-[13px] text-text">line3_defects.csv</div>
                  <div ref={fileSubRef} className="text-[11.5px] text-tertiary mt-0.5">4,812 rows · uploaded</div>
                </div>
              </div>
            </div>

            <div ref={conn1Ref} className="landing-connector">
              <div className="base-line" />
              <div className="flow-line" />
            </div>

            {/* Chat panel */}
            <div className="flex-1 min-w-0 bg-gradient-to-b from-surface-1 to-surface-2 border border-border rounded-2xl p-4.5 flex flex-col">
              <div className="flex items-center gap-1.5 font-mono text-[10px] tracking-[0.11em] uppercase mb-3.5" style={{ color: "var(--color-ic-blue)" }}>
                <span className="w-1.5 h-1.5 rounded-full bg-current" />
                {copy.flowQuestion}
              </div>
              <div className="flex-1 flex flex-col justify-center min-h-[74px]">
                <div className="flex items-start gap-2">
                  <div className="w-[22px] h-[22px] rounded-full bg-surface-2 border border-border shrink-0 mt-px grid place-items-center text-muted">
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round">
                      <circle cx="12" cy="8" r="4" />
                      <path d="M4 20c0-4 4-6 8-6s8 2 8 6" />
                    </svg>
                  </div>
                  <div ref={chatTextRef} className="font-mono text-[13.5px] leading-[1.55] text-text min-h-[42px]">
                    <span className="landing-cursor" />
                  </div>
                </div>
              </div>
            </div>

            <div ref={conn2Ref} className="landing-connector">
              <div className="base-line" />
              <div className="flow-line" />
            </div>

            {/* Chart panel */}
            <div className="flex-1 min-w-0 bg-gradient-to-b from-surface-1 to-surface-2 border border-border rounded-2xl p-4.5 flex flex-col">
              <div className="flex items-center gap-1.5 font-mono text-[10px] tracking-[0.11em] uppercase text-stage-execution mb-3.5">
                <span className="w-1.5 h-1.5 rounded-full bg-current" />
                {copy.flowResult}
              </div>
              <div className="flex-1 flex flex-col">
                <div className="flex items-baseline gap-1.5 mb-1.5">
                  <span ref={chartNumRef} className="font-mono tabular-nums text-[20px] font-semibold text-stage-execution">0</span>
                  <span ref={chartUnitRef} className="text-[11.5px] text-tertiary">%</span>
                </div>
                <svg ref={chartSvgRef} className="w-full h-[78px] overflow-visible" viewBox="0 0 220 78" preserveAspectRatio="none" />
              </div>
            </div>
          </div>
        </div>

        {/* Feature row */}
        <section id="features">
          <div className="text-center font-mono text-[11px] tracking-[0.14em] uppercase text-tertiary mb-3">{copy.featuresEyebrow}</div>
          <h2 className="font-display font-semibold text-[22px] sm:text-[30px] text-center mb-11 tracking-[-0.01em]" style={{ textWrap: "balance" }}>
            {copy.featuresTitle}
          </h2>
          <div className="grid grid-cols-1 min-[860px]:grid-cols-3 gap-4.5 mb-28">
            {/* Feature 1 */}
            <div className="bg-surface-1 border border-border rounded-[18px] p-6 flex flex-col">
              <div className="w-9.5 h-9.5 rounded-[10px] grid place-items-center mb-4.5 bg-[rgba(124,111,239,0.14)] text-accent">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <ellipse cx="12" cy="5" rx="8" ry="3" />
                  <path d="M4 5v14c0 1.66 3.58 3 8 3s8-1.34 8-3V5" />
                  <path d="M4 12c0 1.66 3.58 3 8 3s8-1.34 8-3" />
                </svg>
              </div>
              <h3 className="font-display font-semibold text-[16.5px] mb-2">{copy.f1Title}</h3>
              <p className="text-[13.5px] leading-relaxed text-muted mb-5">{copy.f1Desc}</p>
              <div className="mt-auto h-16 flex items-center gap-2">
                <div className="landing-chip flex-1 h-[30px] rounded-lg border border-[rgba(124,111,239,0.3)] bg-[rgba(124,111,239,0.14)] grid place-items-center font-mono text-[10px] text-accent">.csv</div>
                <div className="landing-chip flex-1 h-[30px] rounded-lg border border-[rgba(124,111,239,0.3)] bg-[rgba(124,111,239,0.14)] grid place-items-center font-mono text-[10px] text-accent">SQL</div>
              </div>
            </div>

            {/* Feature 2 */}
            <div className="bg-surface-1 border border-border rounded-[18px] p-6 flex flex-col">
              <div className="w-9.5 h-9.5 rounded-[10px] grid place-items-center mb-4.5" style={{ background: "rgba(94,168,255,0.13)", color: "var(--color-ic-blue)" }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
                </svg>
              </div>
              <h3 className="font-display font-semibold text-[16.5px] mb-2">{copy.f2Title}</h3>
              <p className="text-[13.5px] leading-relaxed text-muted mb-5">{copy.f2Desc}</p>
              <div className="mt-auto h-16 flex items-center gap-2.5">
                <div className="flex flex-col gap-1 w-[34%]">
                  <div className="landing-thumb h-3 rounded-[3px] border border-border" style={{ background: "rgba(94,168,255,0.25)" }} />
                  <div className="landing-thumb h-3 rounded-[3px] border border-border" style={{ background: "rgba(255,207,92,0.25)" }} />
                  <div className="landing-thumb h-3 rounded-[3px] border border-border" style={{ background: "rgba(61,220,151,0.25)" }} />
                </div>
                <div className="text-tertiary shrink-0">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M5 12h14M13 6l6 6-6 6" />
                  </svg>
                </div>
                <div className="flex-1 rounded-lg p-2.5 flex flex-col gap-1" style={{ border: "1px solid rgba(94,168,255,0.32)", background: "rgba(94,168,255,0.08)" }}>
                  <div className="landing-sline h-[5px] rounded-[3px] w-[90%]" style={{ background: "rgba(94,168,255,0.4)" }} />
                  <div className="landing-sline h-[5px] rounded-[3px] w-[65%]" style={{ background: "rgba(94,168,255,0.4)" }} />
                  <div className="landing-sline h-[5px] rounded-[3px] w-[78%]" style={{ background: "rgba(94,168,255,0.4)" }} />
                </div>
              </div>
            </div>

            {/* Feature 3 */}
            <div className="bg-surface-1 border border-border rounded-[18px] p-6 flex flex-col">
              <div className="w-9.5 h-9.5 rounded-[10px] grid place-items-center mb-4.5 bg-stage-execution-soft text-stage-execution">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 3v18h18" />
                  <path d="M7 16l4-6 3 3 5-8" />
                </svg>
              </div>
              <h3 className="font-display font-semibold text-[16.5px] mb-2">{copy.f3Title}</h3>
              <p className="text-[13.5px] leading-relaxed text-muted mb-5">{copy.f3Desc}</p>
              <div className="mt-auto h-16 flex items-center justify-between px-0.5">
                <div className="landing-glyph w-[30px] h-[30px] rounded-lg grid place-items-center">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 17l5-6 4 4 8-9" /></svg>
                </div>
                <div className="landing-glyph w-[30px] h-[30px] rounded-lg grid place-items-center">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 20V10M12 20V4M20 20v-7" /></svg>
                </div>
                <div className="landing-glyph w-[30px] h-[30px] rounded-lg grid place-items-center">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="6" cy="17" r="1.6" /><circle cx="12" cy="8" r="1.6" /><circle cx="17" cy="14" r="1.6" /><circle cx="20" cy="6" r="1.6" /></svg>
                </div>
                <div className="landing-glyph w-[30px] h-[30px] rounded-lg grid place-items-center">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="9" /><path d="M12 3v9l7 4" /></svg>
                </div>
                <div className="landing-glyph w-[30px] h-[30px] rounded-lg grid place-items-center">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 20 L9 20 L9 11 L15 11 L15 6 L21 6 L21 20" strokeLinejoin="round" /></svg>
                </div>
                <div className="landing-glyph w-[30px] h-[30px] rounded-lg grid place-items-center">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2v4M12 18v4M2 12h4M18 12h4" /><circle cx="12" cy="12" r="5" /></svg>
                </div>
                <div className="landing-glyph w-[30px] h-[30px] rounded-lg grid place-items-center">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /></svg>
                </div>
                <div className="landing-glyph w-[30px] h-[30px] rounded-lg grid place-items-center">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="6" y="4" width="12" height="7" rx="1" /><path d="M9 11v6M15 11v6M6 17h12" /></svg>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Closing CTA */}
        <section className="text-center border-t border-border-2 pt-16">
          <h2 className="font-display font-semibold text-[21px] sm:text-[27px] mb-7" style={{ textWrap: "balance" }}>
            {copy.closingTitle}
          </h2>
          <button
            type="button"
            onClick={onGetStarted}
            className="font-body font-semibold text-[14.5px] text-[#0a0a0f] bg-gradient-to-r from-stage-execution to-[#6be8b3] rounded-[11px] px-6.5 py-3.5 shadow-[0_0_0_1px_rgba(61,220,151,0.3),0_8px_30px_-8px_rgba(61,220,151,0.55)] hover:-translate-y-px transition-transform focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2"
          >
            {copy.ctaPrimary}
          </button>
          <p className="text-[12.5px] text-tertiary mt-5">{copy.brand}</p>
          <p className="text-[11.5px] text-tertiary/70 mt-1.5">
            {copy.creditName} &middot; {copy.creditDept}
          </p>
        </section>
      </main>
    </div>
  );
}
