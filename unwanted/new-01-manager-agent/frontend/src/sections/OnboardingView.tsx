const MANAGER = "#ff8a4c";
const MANAGER_DIM = "rgba(255,138,76,0.35)";
const MANAGER_BG = "rgba(255,138,76,0.07)";
const PLANNER = "#f0c419";
const PLANNER_DIM = "rgba(240,196,25,0.35)";
const PLANNER_BG = "rgba(240,196,25,0.07)";
const EXECUTION = "#3ddc97";
const EXECUTION_DIM = "rgba(61,220,151,0.35)";
const EXECUTION_BG = "rgba(61,220,151,0.07)";
const ACCENT = "#7c6fef";
const MUTED = "#8d8d9c";
const LINE_COLOR = "rgba(230,230,238,0.18)";

function SubAgentRow({ label, color, delay }: { label: string; color: string; delay: string }) {
  return (
    <div className="relative flex items-center gap-1.5" style={{ paddingLeft: 14 }}>
      <div
        className="absolute w-px"
        style={{
          left: 4,
          top: -4,
          bottom: 7,
          background: LINE_COLOR,
        }}
      />
      <div
        className="absolute"
        style={{
          left: -10,
          top: "50%",
          width: 8,
          height: 1,
          background: LINE_COLOR,
        }}
      />
      <span
        className="w-[5px] h-[5px] rounded-full shrink-0"
        style={{
          background: color,
          animation: `workPulse 1.5s ease-in-out infinite`,
          animationDelay: delay,
        }}
      />
      <span className="font-mono text-[9.5px]" style={{ color: MUTED }}>
        {label}
      </span>
    </div>
  );
}

function HubBlock({
  position,
  name,
  desc,
  color,
  dimColor,
  bgColor,
  children,
}: {
  position: React.CSSProperties;
  name: string;
  desc: string;
  color: string;
  dimColor: string;
  bgColor: string;
  children: React.ReactNode;
}) {
  return (
    <div className="absolute flex flex-col" style={{ ...position, width: 132 }}>
      <div
        className="flex flex-col items-start rounded-xl py-2.5 px-3"
        style={{ border: `1.5px solid ${dimColor}`, background: bgColor, color, width: 132 }}
      >
        <span
          className="font-display text-[12.5px] font-semibold mb-1"
          style={{ color }}
        >
          {name}
        </span>
        {children}
      </div>
      <span
        className="text-[10.5px] font-medium leading-tight mt-1.5 px-0.5"
        style={{ color }}
      >
        {desc}
      </span>
    </div>
  );
}

export default function OnboardingView() {
  return (
    <div className="flex flex-col items-center justify-center flex-1 gap-9">
      <div className="w-full max-w-[640px]">
        <h3 className="text-center font-display text-lg font-semibold mb-1">
          Three agents, one shared registry
        </h3>
        <p className="text-center text-[13px] mb-7" style={{ color: "#b4b4c4" }}>
          Each agent works independently, picking up and dropping off tasks
        </p>

        <div className="relative w-full" style={{ height: 320 }}>
          {/* ── SVG connections + animated cubes ── */}
          <svg
            className="absolute inset-0 w-full h-full"
            viewBox="0 0 640 320"
          >
            {/* Connection lines */}
            <path d="M132,145 L255,155" stroke={MANAGER_DIM} strokeWidth={1} fill="none" />
            <path d="M508,90 L385,135" stroke={PLANNER_DIM} strokeWidth={1} fill="none" />
            <path d="M508,230 L385,185" stroke={EXECUTION_DIM} strokeWidth={1} fill="none" />

            {/* Manager ↔ Registry */}
            <rect x="-4" y="-4" width="8" height="8" rx="1.5" fill={ACCENT}>
              <animateMotion dur="2.6s" repeatCount="indefinite" path="M132,145 L255,155" />
            </rect>
            <rect x="-4" y="-4" width="8" height="8" rx="1.5" fill={MANAGER}>
              <animateMotion dur="2.6s" begin="1.3s" repeatCount="indefinite" path="M255,155 L132,145" />
            </rect>

            {/* Planner ↔ Registry */}
            <rect x="-4" y="-4" width="8" height="8" rx="1.5" fill={PLANNER}>
              <animateMotion dur="2.8s" repeatCount="indefinite" path="M385,135 L508,90" />
            </rect>
            <rect x="-4" y="-4" width="8" height="8" rx="1.5" fill={ACCENT}>
              <animateMotion dur="2.8s" begin="1.4s" repeatCount="indefinite" path="M508,90 L385,135" />
            </rect>

            {/* Executor ↔ Registry */}
            <rect x="-4" y="-4" width="8" height="8" rx="1.5" fill={EXECUTION}>
              <animateMotion dur="2.7s" repeatCount="indefinite" path="M385,185 L508,230" />
            </rect>
            <rect x="-4" y="-4" width="8" height="8" rx="1.5" fill={ACCENT}>
              <animateMotion dur="2.7s" begin="1.35s" repeatCount="indefinite" path="M508,230 L385,185" />
            </rect>
          </svg>

          {/* ── Central registry ── */}
          <div
            className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center justify-center gap-1.5"
            style={{
              width: 130,
              height: 100,
              borderRadius: 10,
              border: `1.5px solid ${LINE_COLOR}`,
              background: "rgba(230,230,238,0.03)",
            }}
          >
            <span className="font-mono text-[10.5px] tracking-wide" style={{ color: MUTED }}>
              task registry
            </span>
            <div className="flex gap-1">
              {[
                { bg: MANAGER, delay: "0s" },
                { bg: ACCENT, delay: "0.3s" },
                { bg: PLANNER, delay: "0.6s" },
                { bg: EXECUTION, delay: "0.9s" },
              ].map((c, i) => (
                <span
                  key={i}
                  className="w-2.5 h-2.5 rounded-sm"
                  style={{
                    background: c.bg,
                    animation: `cubeSettle 2.4s ease-in-out infinite`,
                    animationDelay: c.delay,
                  }}
                />
              ))}
            </div>
          </div>

          {/* ── Manager hub ── */}
          <HubBlock
            position={{ left: 0, top: 96 }}
            name="Manager Agent"
            desc="Turns your problem into a plan"
            color={MANAGER}
            dimColor={MANAGER_DIM}
            bgColor={MANAGER_BG}
          >
            <div className="flex flex-col gap-[5px] mt-2">
              <SubAgentRow label="subagent1" color={MANAGER} delay="0s" />
              <SubAgentRow label="subagent2" color={MANAGER} delay="0.35s" />
              <SubAgentRow label="subagent3" color={MANAGER} delay="0.7s" />
            </div>
          </HubBlock>

          {/* ── Planner hub ── */}
          <HubBlock
            position={{ right: 0, top: 6 }}
            name="Planner Agent"
            desc="Turns the plan into executable queries"
            color={PLANNER}
            dimColor={PLANNER_DIM}
            bgColor={PLANNER_BG}
          >
            <div className="flex flex-col gap-[5px] mt-2">
              <SubAgentRow label="subagent1" color={PLANNER} delay="0s" />
              <SubAgentRow label="subagent2" color={PLANNER} delay="0.35s" />
              <SubAgentRow label="subagent3" color={PLANNER} delay="0.7s" />
            </div>
          </HubBlock>

          {/* ── Execution hub ── */}
          <HubBlock
            position={{ right: 0, bottom: 6 }}
            name="Executor Agent"
            desc="Turns queries into reality"
            color={EXECUTION}
            dimColor={EXECUTION_DIM}
            bgColor={EXECUTION_BG}
          >
            <div className="flex flex-col gap-[5px] mt-2">
              <SubAgentRow label="subagent1" color={EXECUTION} delay="0s" />
              <SubAgentRow label="subagent2" color={EXECUTION} delay="0.35s" />
              <SubAgentRow label="subagent3" color={EXECUTION} delay="0.7s" />
            </div>
          </HubBlock>
        </div>
      </div>
    </div>
  );
}
