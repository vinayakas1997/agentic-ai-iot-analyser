import { SVGProps } from "react";

type Props = SVGProps<SVGSVGElement> & { size?: number };

function Icon({ size = 14, children, ...props }: Props & { children: React.ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width={size} height={size} {...props}>
      {children}
    </svg>
  );
}

export function IconEye(props: Props) {
  return (
    <Icon {...props} strokeWidth="2.2">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </Icon>
  );
}

export function IconUser(props: Props) {
  return (
    <Icon {...props} strokeWidth="2.4">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4 4-6 8-6s8 2 8 6" />
    </Icon>
  );
}

export function IconLock(props: Props) {
  return (
    <Icon {...props} strokeWidth="2">
      <rect x="4" y="10" width="16" height="10" rx="2" />
      <path d="M8 10V7a4 4 0 018 0v3" />
    </Icon>
  );
}

export function IconCheck(props: Props) {
  return (
    <Icon {...props} strokeWidth="2.5">
      <path d="M20 6L9 17l-5-5" />
    </Icon>
  );
}

export function IconMenu(props: Props) {
  return (
    <Icon {...props} strokeWidth="2.4">
      <path d="M3 12h18M3 6h18M3 18h18" />
    </Icon>
  );
}

export function IconClock(props: Props) {
  return (
    <Icon {...props} strokeWidth="2.2">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 3" />
    </Icon>
  );
}

export function IconCheckCircle(props: Props) {
  return (
    <Icon {...props} strokeWidth="2.2">
      <path d="M9 11l3 3L22 4" />
      <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" />
    </Icon>
  );
}

export function IconMapPin(props: Props) {
  return (
    <Icon {...props} strokeWidth="2.4">
      <path d="M20.5 10.5c0 6-8.5 11-8.5 11s-8.5-5-8.5-11a8.5 8.5 0 0117 0z" />
      <circle cx="12" cy="10.5" r="2.5" />
    </Icon>
  );
}

export function IconDatabase(props: Props) {
  return (
    <Icon {...props} strokeWidth="2.2">
      <path d="M3 5v14c0 1.1 3.6 2 8 2s8-.9 8-2V5" />
      <path d="M3 5c0 1.1 3.6 2 8 2s8-.9 8-2-3.6-2-8-2-8 .9-8 2z" />
      <path d="M3 12c0 1.1 3.6 2 8 2s8-.9 8-2" />
    </Icon>
  );
}

export function IconTarget(props: Props) {
  return (
    <Icon {...props} strokeWidth="2.4">
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="12" cy="12" r="0.5" fill="currentColor" />
    </Icon>
  );
}

export function IconGrid(props: Props) {
  return (
    <Icon {...props} strokeWidth="2.2">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M3 9h18M3 15h18M9 3v18" />
    </Icon>
  );
}

export function IconStar(props: Props) {
  return (
    <Icon {...props}>
      <path d="M12 2l1.5 5.5L19 9l-5.5 1.5L12 16l-1.5-5.5L5 9l5.5-1.5z" fill="currentColor" />
    </Icon>
  );
}

export function IconChevronRight(props: Props) {
  return (
    <Icon {...props} strokeWidth="2.5">
      <path d="M9 18l6-6-6-6" />
    </Icon>
  );
}

export function IconEdit(props: Props) {
  return (
    <Icon {...props} strokeWidth="2">
      <path d="M17 3a2.828 2.828 0 114 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
    </Icon>
  );
}

export function IconUpload(props: Props) {
  return (
    <Icon {...props} strokeWidth="2.2">
      <path d="M12 16V4M7 9l5-5 5 5" />
      <path d="M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2" />
    </Icon>
  );
}

export function IconTrash(props: Props) {
  return (
    <Icon {...props} strokeWidth="2.2">
      <path d="M4 7h16M9 7V4h6v3M6 7l1 13a2 2 0 002 2h6a2 2 0 002-2l1-13" />
    </Icon>
  );
}

export function IconSave(props: Props) {
  return (
    <Icon {...props} strokeWidth="2">
      <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
      <polyline points="17 21 17 13 7 13 7 21" />
      <polyline points="7 3 7 8 15 8" />
    </Icon>
  );
}

export function IconChart(props: Props) {
  return (
    <Icon {...props} strokeWidth="2.2">
      <rect x="3" y="12" width="4" height="9" rx="1" />
      <rect x="10" y="6" width="4" height="15" rx="1" />
      <rect x="17" y="3" width="4" height="18" rx="1" />
    </Icon>
  );
}

export function IconRobot(props: Props) {
  return (
    <Icon {...props} strokeWidth="2">
      <path d="M12 2v3" />
      <circle cx="12" cy="2" r="1" fill="currentColor" stroke="none" />
      <rect x="4" y="8" width="16" height="12" rx="3" />
      <circle cx="9" cy="14" r="1.4" fill="currentColor" stroke="none" />
      <circle cx="15" cy="14" r="1.4" fill="currentColor" stroke="none" />
      <path d="M9 17.5c1 .8 5 .8 6 0" />
      <path d="M2 13v3M22 13v3" />
    </Icon>
  );
}

export function IconHelp(props: Props) {
  return (
    <Icon {...props} strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3" />
      <path d="M12 17h.01" />
    </Icon>
  );
}

export function IconSend(props: Props) {
  return (
    <Icon {...props} strokeWidth="2.2">
      <path d="M22 2L11 13" />
      <path d="M22 2l-7 20-4-9-9-4 20-7z" />
    </Icon>
  );
}

/** Looping bowling-ball-hits-pins -> glowing lightbulb animation, used for the navbar help/tour trigger. */
export function IconHelpAnimated({ size = 20 }: { size?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} className="hlp-anim" aria-hidden>
      <g className="hlp-ball">
        <circle cx="2.5" cy="17" r="2.8" fill="white" />
        <circle cx="1.5" cy="16" r="0.45" fill="white" opacity="0.5" />
        <circle cx="3.5" cy="15.9" r="0.4" fill="white" opacity="0.5" />
      </g>
      <g className="hlp-pin hlp-pin-1">
        <rect x="15.6" y="11" width="2.8" height="7" rx="1.4" fill="white" />
        <circle cx="17" cy="10.6" r="1.3" fill="white" />
      </g>
      <g className="hlp-pin hlp-pin-2">
        <rect x="18.6" y="12.2" width="2.8" height="7" rx="1.4" fill="white" />
        <circle cx="20" cy="11.8" r="1.3" fill="white" />
      </g>
      <g className="hlp-pin hlp-pin-3">
        <rect x="18.6" y="8.2" width="2.8" height="7" rx="1.4" fill="white" />
        <circle cx="20" cy="7.8" r="1.3" fill="white" />
      </g>
      <g className="hlp-bulb-glow">
        <circle cx="12" cy="10" r="7" fill="white" opacity="0.5" />
      </g>
      <g className="hlp-bulb">
        <path
          d="M12 3.5a5.5 5.5 0 00-3 10.1c.6.4 1 1.1 1 1.9v.5h4v-.5c0-.8.4-1.5 1-1.9A5.5 5.5 0 0012 3.5z"
          fill="white"
        />
        <rect x="10" y="17.2" width="4" height="1.1" rx="0.5" fill="white" />
        <rect x="10.3" y="18.6" width="3.4" height="1" rx="0.5" fill="white" />
      </g>
    </svg>
  );
}
