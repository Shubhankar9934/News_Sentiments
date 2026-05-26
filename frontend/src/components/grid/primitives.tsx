/**
 * Tiny shared primitives reused across every grid-card section: the chip,
 * the section header, and a "section frame" that gives every panel the
 * same divider + uppercase title rhythm.
 */

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { toneBadgeClass, type Tone } from "@/lib/deriveDecisionTone";

export function Chip({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center rounded-md border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider",
        toneBadgeClass(tone),
        className,
      )}
    >
      {children}
    </span>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <div className="grid-card-section-title">{children}</div>;
}

export function SectionFrame({
  title,
  children,
  trailing,
  className,
}: {
  title?: string;
  trailing?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("flex flex-col gap-2", className)}>
      {(title || trailing) && (
        <div className="flex items-center justify-between gap-2">
          {title ? <SectionTitle>{title}</SectionTitle> : <span />}
          {trailing}
        </div>
      )}
      {children}
    </section>
  );
}

export function MetricCell({
  label,
  value,
  tone,
  emphasis = false,
  className,
}: {
  label: string;
  value: ReactNode;
  tone?: Tone;
  emphasis?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-1 rounded-md border border-[hsl(var(--terminal-border))] bg-[hsl(var(--terminal-card-elevated))]/60 px-3 py-2",
        className,
      )}
    >
      <span className="text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--terminal-text-secondary))]">
        {label}
      </span>
      {emphasis ? (
        <span
          className={cn(
            "font-mono text-base font-bold leading-tight",
            tone === "ok"
              ? "text-emerald-700 dark:text-emerald-300"
              : tone === "warn"
                ? "text-amber-700 dark:text-amber-200"
                : tone === "bad"
                  ? "text-rose-700 dark:text-rose-300"
                  : "text-[hsl(var(--terminal-text-primary))]",
          )}
        >
          {value}
        </span>
      ) : (
        <div className="text-sm font-semibold text-[hsl(var(--terminal-text-primary))]">{value}</div>
      )}
    </div>
  );
}

export function HorizontalDivider() {
  return <div className="grid-card-divider" />;
}
