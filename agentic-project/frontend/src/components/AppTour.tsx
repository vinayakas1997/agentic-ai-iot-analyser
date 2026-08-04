import { useState, useEffect, useRef, useCallback } from "react";
import { useT } from "../lib/i18n";
import { useDatasetStore } from "../stores/datasetStore";
import { useSessionStore } from "../stores/sessionStore";
import { useOutputStore } from "../stores/outputStore";
import { useUploadStore } from "../stores/uploadStore";
import { useUiStore } from "../stores/uiStore";
import {
  TOUR_DATASET_NAME,
  TOUR_AIM_NAME,
  TOUR_SAMPLE_RESULT,
  TOUR_DEMO_TEMPLATE,
  TOUR_QUESTIONS,
  CSV_PREVIEW_LINES,
  DEFS_PREVIEW_LINES,
  mockDraft,
  LLM_TYPING_COLUMNS,
  FAKE_SEARCH_RESULTS,
  FAKE_AIM,
} from "../lib/tourSampleData";
import TourDemoCharts from "./TourDemoCharts";
import { IconRobot } from "../lib/icons";

interface Step {
  target?: string;
  titleKey: string;
  descKey: string;
  side?: "bottom" | "top" | "left" | "right";
}

const STEPS: Step[] = [
  { titleKey: "tour.step0Title", descKey: "tour.step0Desc" },
  { target: "[data-tour='upload-csv']", titleKey: "tour.step1Title", descKey: "tour.step1Desc", side: "bottom" },
  { target: "[data-tour='upload-defs']", titleKey: "tour.step2aTitle", descKey: "tour.step2aDesc", side: "bottom" },
  { target: "[data-tour='llm-fill']", titleKey: "tour.step3aTitle", descKey: "tour.step3aDesc", side: "right" },
  { target: "[data-tour='dataset-section']", titleKey: "tour.step2Title", descKey: "tour.step2Desc", side: "bottom" },
  { target: "[data-tour='context-panel']", titleKey: "tour.step3Title", descKey: "tour.step3Desc", side: "right" },
  { target: "[data-tour='aim-bar']", titleKey: "tour.step4Title", descKey: "tour.step4Desc", side: "top" },
  { target: "[data-tour='composer']", titleKey: "tour.step5Title", descKey: "tour.step5Desc", side: "top" },
  { target: "[data-tour='output-panel']", titleKey: "tour.step6Title", descKey: "tour.step6Desc", side: "left" },
  { titleKey: "tour.step6Title", descKey: "tour.step6Desc" },
  { target: "[data-tour='template-button']", titleKey: "tour.tpl1Title", descKey: "tour.tpl1Desc", side: "top" },
  { target: "[data-tour='template-modal']", titleKey: "tour.tpl2Title", descKey: "tour.tpl2Desc", side: "right" },
  { target: "[data-tour='template-banner']", titleKey: "tour.tpl3Title", descKey: "tour.tpl3Desc", side: "top" },
  { target: "[data-tour='template-result']", titleKey: "tour.tpl4Title", descKey: "tour.tpl4Desc", side: "left" },
  { titleKey: "tour.step7Title", descKey: "tour.step7Desc" },
];

const COMPOSER_SELECTOR = "[data-tour='composer']";

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

export default function AppTour({ active, onClose }: { active: boolean; onClose: () => void }) {
  const t = useT();
  const [step, setStep] = useState(0);
  const [cursorPos, setCursorPos] = useState({ x: 0, y: 0 });
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null);
  const [csvText, setCsvText] = useState("");
  const [defsText, setDefsText] = useState("");
  const [llmTyping, setLlmTyping] = useState(false);
  const [searchQueryText, setSearchQueryText] = useState("");
  const [showSearchResults, setShowSearchResults] = useState(false);
  const [showSuggestedAims, setShowSuggestedAims] = useState(false);
  const [aimSelected, setAimSelected] = useState(false);
  const animFrameRef = useRef<number>(0);
  const cursorRef = useRef({ x: 0, y: 0 });
  const typewriterRef = useRef(false);

  useEffect(() => {
    if (!active) return;
    setStep(0);
    setCsvText("");
    setDefsText("");
    setLlmTyping(false);
    setSearchQueryText("");
    setShowSearchResults(false);
    setShowSuggestedAims(false);
    setAimSelected(false);
    useUiStore.setState({ tourTemplateOpen: false, tourTemplateApplied: false });
    typewriterRef.current = false;
    const center = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    setCursorPos(center);
    cursorRef.current = center;
    injectStepData(0);
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      typewriterRef.current = true;
    };
  }, [active]);

  useEffect(() => {
    if (!active) return;
    const s = STEPS[step];
    if (!s.target) {
      setTargetRect(null);
      return;
    }
    setTimeout(() => locateTarget(s.target!), 100);
  }, [step, active]);

  useEffect(() => {
    if (!active || step !== 7) return;
    if (typewriterRef.current) return;
    runTypewriter();
  }, [active, step]);

  useEffect(() => {
    if (!active || step !== 1) return;
    setCsvText("");
    runCsvPreview();
  }, [active, step]);

  useEffect(() => {
    if (!active || step !== 2) return;
    setDefsText("");
    runDefsPreview();
  }, [active, step]);

  useEffect(() => {
    if (!active || step !== 3) return;
    runLlmTypewriter();
  }, [active, step]);

  useEffect(() => {
    if (!active || step !== 4) return;
    runDatasetSearch();
  }, [active, step]);

  const runCsvPreview = async () => {
    const full = CSV_PREVIEW_LINES.join("\n");
    for (let i = 0; i <= full.length; i++) {
      if (typewriterRef.current) break;
      setCsvText(full.slice(0, i));
      await sleep(15);
    }
  };

  const runDefsPreview = async () => {
    const full = DEFS_PREVIEW_LINES.join("\n");
    for (let i = 0; i <= full.length; i++) {
      if (typewriterRef.current) break;
      setDefsText(full.slice(0, i));
      await sleep(15);
    }
  };

  const runLlmTypewriter = async () => {
    setLlmTyping(true);
    const entries = Object.entries(LLM_TYPING_COLUMNS);
    const maxLen = Math.max(...entries.map(([, text]) => text.length));
    for (let i = 0; i <= maxLen; i++) {
      if (typewriterRef.current) break;
      const merged: Record<string, string> = {};
      for (const [col, text] of entries) {
        merged[col] = text.slice(0, Math.min(i, text.length));
      }
      useUploadStore.getState().openClarify([mockDraft(merged)], []);
      await sleep(40);
    }
    setLlmTyping(false);
  };

  const runDatasetSearch = async () => {
    const target = "pro";
    for (let i = 0; i <= target.length; i++) {
      if (typewriterRef.current) break;
      setSearchQueryText(target.slice(0, i));
      await sleep(60);
    }
    if (typewriterRef.current) return;
    setShowSearchResults(true);
    await sleep(600);
    if (typewriterRef.current) return;
    setShowSuggestedAims(true);
    await sleep(500);
    if (typewriterRef.current) return;
    useSessionStore.setState((s) => ({
      selectedAims: s.selectedAims.some((a) => a.aim === FAKE_AIM.aim)
        ? s.selectedAims
        : [...s.selectedAims, { aim: FAKE_AIM.aim, description: t(FAKE_AIM.descriptionKey) }],
    }));
    setAimSelected(true);
  };

  const runTypewriter = async () => {
    typewriterRef.current = true;
    const el = document.querySelector(COMPOSER_SELECTOR) as HTMLTextAreaElement | null;
    if (!el) {
      typewriterRef.current = false;
      return;
    }
    el.value = "";
    el.focus();

    for (let q = 0; q < TOUR_QUESTIONS.length; q++) {
      const question = t(TOUR_QUESTIONS[q].key);
      for (let i = 0; i <= question.length; i++) {
        if (!typewriterRef.current) break;
        el.value = question.slice(0, i);
        el.dispatchEvent(new Event("input", { bubbles: true }));
        await sleep(30);
      }
      if (!typewriterRef.current) break;
      await sleep(1200);
      for (let i = question.length; i >= 0; i--) {
        if (!typewriterRef.current) break;
        el.value = question.slice(0, i);
        el.dispatchEvent(new Event("input", { bubbles: true }));
        await sleep(15);
      }
      await sleep(400);
    }
    typewriterRef.current = false;
  };

  const locateTarget = useCallback((selector: string) => {
    const el = document.querySelector(selector);
    if (!el) {
      setTargetRect(null);
      return;
    }
    const rect = el.getBoundingClientRect();
    setTargetRect(rect);
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;

    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    const startX = cursorRef.current.x || cx;
    const startY = cursorRef.current.y || cy;
    const startTime = performance.now();
    const duration = 600;

    function animate(now: number) {
      const elapsed = now - startTime;
      const p = Math.min(elapsed / duration, 1);
      const ease = 1 - Math.pow(1 - p, 3);
      const nx = startX + (cx - startX) * ease;
      const ny = startY + (cy - startY) * ease;
      cursorRef.current = { x: nx, y: ny };
      setCursorPos({ x: nx, y: ny });
      if (p < 1) animFrameRef.current = requestAnimationFrame(animate);
    }
    animFrameRef.current = requestAnimationFrame(animate);
  }, []);

  const openClarifyModal = useCallback((filled: Record<string, string>) => {
    useUploadStore.getState().openClarify([mockDraft(filled)], []);
  }, []);

  const closeClarifyModal = useCallback(() => {
    useUploadStore.getState().closeClarify();
  }, []);

  const injectStepData = useCallback((s: number) => {
    if (s === 2) {
      openClarifyModal({});
    }
    if (s >= 4) {
      closeClarifyModal();
      useDatasetStore.getState().addMultiple([TOUR_DATASET_NAME]);
    }
    if (s >= 6) {
      useDatasetStore.getState().addMultiple([TOUR_DATASET_NAME]);
      const aims = useSessionStore.getState().selectedAims;
      if (!aims.some((a) => a.aim === TOUR_AIM_NAME)) {
        useSessionStore.setState((state) => ({
          selectedAims: [...state.selectedAims, { aim: TOUR_AIM_NAME, description: t("tour.fakeAimDesc") }],
        }));
      }
    }
    if (s >= 8) {
      closeClarifyModal();
      useOutputStore.getState().addResult({
        aim: TOUR_AIM_NAME,
        description: t("tour.fakeAimDesc"),
        result: TOUR_SAMPLE_RESULT,
      });
    }
    if (s === 10) {
      useUiStore.setState({ tourTemplateOpen: false, tourTemplateApplied: false });
    }
    if (s === 11) {
      useUiStore.setState({ tourTemplateOpen: true });
    }
    if (s === 12) {
      useUiStore.setState({ tourTemplateOpen: false, tourTemplateApplied: true });
    }
    if (s === 13) {
      useUiStore.setState({ tourTemplateOpen: false, tourTemplateApplied: true });
      useOutputStore.getState().addResult({
        aim: "01 · " + TOUR_DEMO_TEMPLATE.template_name,
        description: TOUR_DEMO_TEMPLATE.template_name,
        datasets: [TOUR_DATASET_NAME],
        result: TOUR_SAMPLE_RESULT,
        kind: "template",
        template_name: TOUR_DEMO_TEMPLATE.template_name,
        report:
          "### Daily Output Report\n\n1. **CNC-001** leads total output at 4,500 units — but also tops the defect count.\n2. Defect rates stay below 4% across all five machines.\n3. Weekly output grows steadily through week 5, with a small dip in week 6.\n\n**Recommendation:** investigate CNC-001's defect spike, then check what changed in week 6.",
      });
    }
  }, [openClarifyModal, closeClarifyModal, t]);

  const cleanup = useCallback(() => {
    typewriterRef.current = false;
    closeClarifyModal();
    useUiStore.setState({ tourTemplateOpen: false, tourTemplateApplied: false });
    const el = document.querySelector(COMPOSER_SELECTOR) as HTMLTextAreaElement | null;
    if (el) {
      el.value = "";
      el.dispatchEvent(new Event("input", { bubbles: true }));
    }
    useDatasetStore.getState().remove(TOUR_DATASET_NAME);
    useSessionStore.setState({ selectedAims: [] });
    useOutputStore.getState().clearResults();
  }, [closeClarifyModal]);

  const handleNext = () => {
    const next = step + 1;
    if (next >= STEPS.length) {
      cleanup();
      onClose();
      return;
    }
    injectStepData(next);
    setStep(next);
  };

  const handleSkip = () => {
    cleanup();
    onClose();
  };

  if (!active) return null;

  if (step === 9) {
    return (
      <>
        <div className="fixed inset-0 z-[9998] bg-black/60 backdrop-blur-sm" />
        <TourDemoCharts onNext={handleNext} />
      </>
    );
  }

  const s = STEPS[step];
  const isOverlay = !s.target;
  const bubbleSide = s.side || "bottom";

  let bubbleStyle: React.CSSProperties = {};
  if (targetRect && !isOverlay) {
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const BUBBLE_W = 340;
    const BUBBLE_H = 240;
    const GAP = 16;
    const EDGE = 12;
    const clampX = (x: number) => Math.max(EDGE, Math.min(x, vw - BUBBLE_W - EDGE));
    const clampY = (y: number) => Math.max(EDGE, Math.min(y, vh - BUBBLE_H - EDGE));
    const centerX = targetRect.left + targetRect.width / 2 - BUBBLE_W / 2;
    const midY = targetRect.top + targetRect.height / 2 - 60;
    switch (bubbleSide) {
      case "bottom":
        bubbleStyle = { left: clampX(centerX), top: Math.min(targetRect.bottom + GAP, vh - BUBBLE_H - EDGE) };
        break;
      case "top":
        bubbleStyle = { left: clampX(centerX), top: Math.max(EDGE, targetRect.top - BUBBLE_H - GAP) };
        break;
      case "right":
        bubbleStyle = { left: Math.min(targetRect.right + GAP, vw - BUBBLE_W - EDGE), top: clampY(midY) };
        break;
      case "left":
        bubbleStyle = { left: targetRect.left - GAP - BUBBLE_W, top: clampY(midY) };
        break;
    }
  }

  const highlightStyle: React.CSSProperties = targetRect && !isOverlay
    ? {
        position: "fixed",
        left: targetRect.left - 4,
        top: targetRect.top - 4,
        width: targetRect.width + 8,
        height: targetRect.height + 8,
        borderRadius: 8,
        border: "2px solid #3b82f6",
        boxShadow: "0 0 0 9999px rgba(0,0,0,0.55), 0 0 20px rgba(59,130,246,0.4)",
        pointerEvents: "none",
        zIndex: 9998,
        transition: "all 0.4s ease",
      }
    : {};

  if (isOverlay) {
    return (
      <div
        className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm"
        onClick={(e) => { if (e.target === e.currentTarget) handleSkip(); }}
      >
        <div className="rounded-2xl border border-border bg-surface-1 p-8 shadow-2xl max-w-md w-full mx-4 text-center">
          <div className="w-14 h-14 rounded-2xl bg-ic-amber-soft text-ic-amber flex items-center justify-center mx-auto mb-4">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="28" height="28" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3" />
              <path d="M12 17h.01" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-text mb-2">{t(s.titleKey)}</h2>
          <p className="text-sm text-muted mb-6">{t(s.descKey)}</p>
          <div className="flex justify-center gap-3">
            <button
              type="button"
              className="px-4 py-2 text-sm rounded-lg border border-border text-muted hover:text-text transition-colors"
              onClick={handleSkip}
            >
              {t("tour.skip")}
            </button>
            <button
              type="button"
              className="px-4 py-2 text-sm rounded-lg bg-accent text-white hover:bg-[#1d8cf0] transition-colors"
              onClick={handleNext}
            >
              {step === STEPS.length - 1 ? t("tour.finish") : t("tour.next")}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <div style={highlightStyle} />

      <div
        className="fixed z-[9999] pointer-events-none"
        style={{
          left: cursorPos.x + 10,
          top: cursorPos.y + 10,
          transition: "none",
        }}
      >
        <svg width="20" height="24" viewBox="0 0 20 24" fill="none">
          <path d="M2 2L2 20.586L6.293 16.293L10 22L11.414 20.586L7.707 14.879L14.879 14.879L15.586 14.172L2 2Z" fill="white" stroke="#aaa" strokeWidth="0.5" />
        </svg>
      </div>

      <div
        className="fixed z-[9999] rounded-2xl border border-border bg-surface-1 p-5 shadow-2xl w-[340px]"
        style={bubbleStyle}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-1.5 mb-2">
          <span className="inline-flex items-center justify-center w-6 h-6 rounded-lg bg-ic-amber-soft text-ic-amber text-[11px] font-bold">
            {step + 1}
          </span>
          <span className="text-sm font-semibold text-text">{t(s.titleKey)}</span>
        </div>
        <p className="text-sm text-muted mb-4 leading-relaxed">{t(s.descKey)}</p>
        <div className="flex justify-between items-center">
          <button
            type="button"
            className="text-xs text-muted hover:text-text transition-colors"
            onClick={handleSkip}
          >
            {t("tour.skip")}
          </button>
          <button
            type="button"
            className="px-4 py-1.5 text-sm rounded-lg bg-accent text-white hover:bg-[#1d8cf0] transition-colors font-medium"
            onClick={handleNext}
          >
            {step === STEPS.length - 1 ? t("tour.finish") : t("tour.next")}
          </button>
        </div>
      </div>

      {llmTyping && (
        <div className="fixed z-[10000] top-4 left-1/2 -translate-x-1/2 flex items-center gap-2.5 px-4 py-2 rounded-xl bg-[#1a1a2e] border border-accent/30 shadow-lg pointer-events-none">
          <IconRobot size={18} className="text-accent animate-pulse" />
          <span className="text-xs font-medium text-white">{t("tour.llmAnalyzing")}</span>
        </div>
      )}

      {step === 1 && targetRect && (
        <div
          className="fixed z-[9999] rounded-xl border border-border/40 bg-[#1a1a2e] p-3 shadow-2xl pointer-events-none"
          style={{
            left: targetRect.right + 20,
            top: Math.max(20, targetRect.top - 60),
            minWidth: 320,
          }}
        >
          <div className="flex items-center gap-1.5 mb-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span className="text-[10px] font-semibold text-emerald-400 tracking-wider uppercase">{t("tour.csvPreviewFile")}</span>
          </div>
          <pre className="text-[12px] font-mono leading-relaxed text-emerald-300/90 whitespace-pre-wrap m-0">
            {csvText}
            <span className="inline-block w-1.5 h-3.5 bg-emerald-300/70 ml-0.5 animate-pulse" />
          </pre>
        </div>
      )}

      {step === 2 && targetRect && (
        <div
          className="fixed z-[9999] rounded-xl border border-border/40 bg-[#1a1a2e] p-3 shadow-2xl pointer-events-none"
          style={{
            left: targetRect.right + 20,
            top: Math.max(20, targetRect.top - 60),
            minWidth: 320,
          }}
        >
          <div className="flex items-center gap-1.5 mb-1.5">
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            <span className="text-[10px] font-semibold text-amber-400 tracking-wider uppercase">{t("tour.defsPreviewFile")}</span>
          </div>
          <pre className="text-[12px] font-mono leading-relaxed text-amber-300/90 whitespace-pre-wrap m-0">
            {defsText}
            <span className="inline-block w-1.5 h-3.5 bg-amber-300/70 ml-0.5 animate-pulse" />
          </pre>
        </div>
      )}

      {step === 4 && targetRect && (
        <div
          className="fixed z-[9999] rounded-xl border border-border/60 bg-[#1a1a2e] p-4 shadow-2xl pointer-events-none min-w-[360px]"
          style={{
            left: targetRect.right + 20,
            top: Math.max(20, targetRect.top - 20),
          }}
        >
          <div className="relative mb-2">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="12" height="12" strokeWidth="2.2" className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted">
              <circle cx="10.5" cy="10.5" r="7.5" />
              <path d="M16.5 16.5L21 21" />
            </svg>
            <div className="w-full rounded-lg border border-border bg-surface-1 text-text text-[12px] pl-8 pr-3 py-2">
              {searchQueryText}
              {searchQueryText.length < 3 && (
                <span className="inline-block w-1 h-3.5 bg-white/70 ml-0.5 animate-pulse align-middle" />
              )}
            </div>
          </div>

          {showSearchResults && (
            <div className="rounded-lg border border-border bg-surface-1 overflow-hidden mb-2 transition-all duration-300">
              {FAKE_SEARCH_RESULTS.map((ds) => (
                <div
                  key={ds.name}
                  className={`flex items-center gap-2.5 px-2.5 py-2 border-b border-border/30 last:border-b-0 ${ds.checked ? "bg-ic-blue-soft/20" : ""}`}
                >
                  <span className={`w-3.5 h-3.5 rounded border-2 flex items-center justify-center shrink-0 ${ds.checked ? "bg-accent border-accent" : "border-border"}`}>
                    {ds.checked && (
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="8" height="8" strokeWidth="3" className="text-white">
                        <path d="M20 6L9 17l-5-5" />
                      </svg>
                    )}
                  </span>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="14" height="14" strokeWidth="2" className="shrink-0 text-ic-amber">
                    <path d="M3 5v14c0 1.1 3.6 2 8 2s8-.9 8-2V5" />
                    <path d="M3 5c0 1.1 3.6 2 8 2s8-.9 8-2-3.6-2-8-2-8 .9-8 2z" />
                    <path d="M3 12c0 1.1 3.6 2 8 2s8-.9 8-2" />
                  </svg>
                  <div className="flex-1 min-w-0">
                    <div className="text-[12px] font-medium text-text leading-tight">{t(ds.nameKey)}</div>
                    <div className="text-[10px] text-tertiary">{t(ds.lineKey)}</div>
                  </div>
                  <span className="text-[10px] text-muted shrink-0">{ds.cols} {t("chat.colsSuffix")}</span>
                </div>
              ))}
            </div>
          )}

          {showSuggestedAims && (
            <div className="rounded-lg border border-border bg-surface-1 p-2.5 transition-all duration-300">
              <div className="flex items-center gap-1.5 text-[9px] font-semibold tracking-wider uppercase text-muted mb-1.5">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="10" height="10" strokeWidth="2.2">
                  <circle cx="12" cy="12" r="9" />
                  <path d="M12 7v5l3 3" />
                </svg>
                {t("chat.suggestedAims")}
              </div>
              <div
                className={`inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-full border transition-all duration-300 ${
                  aimSelected
                    ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/40 shadow-[0_0_12px_rgba(52,211,153,0.3)]"
                    : "bg-stage-planner-soft/40 text-stage-planner border-stage-planner-line/30"
                }`}
              >
                {aimSelected && (
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="10" height="10" strokeWidth="3" className="text-emerald-400">
                    <path d="M20 6L9 17l-5-5" />
                  </svg>
                )}
                {t(FAKE_AIM.aimKey)}
              </div>
              {aimSelected && (
                <div className="text-[10px] text-emerald-400/80 mt-1.5 font-medium flex items-center gap-1">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="10" height="10" strokeWidth="2.5">
                    <path d="M22 11.08V12a10 10 0 11-5.93-9.14" />
                    <path d="M22 4L12 14.01l-3-3" />
                  </svg>
                  {t("tour.aimSelected")}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </>
  );
}
