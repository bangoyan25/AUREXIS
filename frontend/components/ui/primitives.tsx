"use client";
/** AUREXIS UI primitives — base components */
import { clsx } from "clsx";

type BadgeVariant = "default"|"success"|"danger"|"warning"|"info"|"accent"|"muted";
const BADGE_STYLES: Record<BadgeVariant, string> = {
  default: "bg-aurexis-muted text-aurexis-subtle border-aurexis-border",
  success: "bg-green-900/30 text-aurexis-success border-aurexis-success/30",
  danger:  "bg-red-900/30  text-aurexis-danger  border-aurexis-danger/30",
  warning: "bg-amber-900/30 text-aurexis-warning border-aurexis-warning/30",
  info:    "bg-blue-900/30  text-aurexis-info    border-aurexis-info/30",
  accent:  "bg-yellow-900/30 text-aurexis-accent border-aurexis-accent/30",
  muted:   "bg-transparent   text-aurexis-faint  border-aurexis-border",
};

export function Badge({ children, variant = "default", className }: {
  children: React.ReactNode; variant?: BadgeVariant; className?: string;
}) {
  return (
    <span className={clsx(
      "inline-flex items-center px-1.5 py-0.5 text-2xs font-mono font-medium uppercase tracking-wide border rounded whitespace-nowrap",
      BADGE_STYLES[variant], className
    )}>{children}</span>
  );
}

type DotColor = "success"|"danger"|"warning"|"info"|"accent"|"muted";
const DOT_COLORS: Record<DotColor, string> = {
  success:"bg-aurexis-success", danger:"bg-aurexis-danger", warning:"bg-aurexis-warning",
  info:"bg-aurexis-info", accent:"bg-aurexis-accent", muted:"bg-aurexis-faint",
};
export function StatusDot({ color="muted", pulse }: { color?: DotColor; pulse?: boolean }) {
  return <span aria-hidden="true" className={clsx("inline-block w-1.5 h-1.5 rounded-full flex-shrink-0", DOT_COLORS[color], pulse && "animate-pulse")} />;
}

export function Label({ children, className }: { children: React.ReactNode; className?: string }) {
  return <span className={clsx("text-2xs font-medium uppercase tracking-widest text-aurexis-subtle leading-none", className)}>{children}</span>;
}

export function Panel({ children, className, title, action }: {
  children: React.ReactNode; className?: string; title?: string; action?: React.ReactNode;
}) {
  return (
    <section className={clsx("bg-aurexis-surface border border-aurexis-border rounded", className)}>
      {title && (
        <div className="flex items-center justify-between px-4 py-3 border-b border-aurexis-border">
          <Label>{title}</Label>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center gap-2">
      <p className="text-xs font-medium text-aurexis-subtle uppercase tracking-wide">{title}</p>
      {description && <p className="text-xs text-aurexis-faint max-w-xs leading-relaxed">{description}</p>}
    </div>
  );
}

export function NotConfigured({ name, detail }: { name: string; detail?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-10 px-4 gap-3 text-center">
      <Badge variant="warning">NOT CONFIGURED</Badge>
      <p className="text-xs font-medium text-aurexis-subtle">{name}</p>
      {detail && <p className="text-2xs text-aurexis-faint max-w-sm leading-relaxed">{detail}</p>}
    </div>
  );
}

export function StatRow({ label, value, valueClass }: {
  label: string; value: React.ReactNode; valueClass?: string;
}) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-aurexis-border/40 last:border-0">
      <Label>{label}</Label>
      <span className={clsx("font-financial text-xs text-aurexis-text", valueClass)}>{value}</span>
    </div>
  );
}

export function PnlValue({ value, prefix="$" }: { value: number; prefix?: string }) {
  const cls = value > 0 ? "text-aurexis-success" : value < 0 ? "text-aurexis-danger" : "text-aurexis-subtle";
  return (
    <span className={clsx("font-financial tabular-nums text-sm", cls)}>
      {value >= 0 ? "+" : ""}{prefix}{Math.abs(value).toFixed(2)}
    </span>
  );
}

export function MockIndicator() {
  return (
    <div className="fixed bottom-4 right-4 z-50 pointer-events-none" aria-label="Mock mode active">
      <span className="inline-flex items-center gap-1.5 px-2 py-1 text-2xs font-mono uppercase tracking-widest bg-aurexis-elevated border border-aurexis-accent/40 text-aurexis-accent rounded">
        <span className="w-1 h-1 rounded-full bg-aurexis-accent animate-pulse" aria-hidden="true" />
        MOCK
      </span>
    </div>
  );
}
