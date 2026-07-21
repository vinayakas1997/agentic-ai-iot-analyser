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
