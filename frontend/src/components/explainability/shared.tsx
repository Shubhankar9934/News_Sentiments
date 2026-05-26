import type { ReactNode } from "react";
import { Card } from "@/components/ui/card";
import { Pill } from "@/components/deliberation/shared";

export function ExplainCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <Card className="flex flex-col gap-3">
      <header className="flex flex-col gap-0.5">
        <h3 className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
          {title}
        </h3>
        {subtitle && (
          <p className="text-xs text-slate-600 dark:text-slate-400">{subtitle}</p>
        )}
      </header>
      {children}
    </Card>
  );
}

export function ExplainRow({
  label,
  value,
  detail,
  delta,
  tone,
}: {
  label: string;
  value?: string | number | null;
  detail?: string;
  delta?: number | null;
  tone?: "ok" | "warn" | "bad" | "neutral";
}) {
  return (
    <div className="grid grid-cols-[minmax(8rem,1fr)_auto] items-start gap-x-3 gap-y-1 border-b border-[hsl(var(--border))] pb-2 last:border-b-0 last:pb-0">
      <div className="flex flex-col">
        <span className="text-sm font-medium text-slate-700 dark:text-slate-200">
          {label}
        </span>
        {detail && (
          <span className="text-xs text-slate-500 dark:text-slate-400">{detail}</span>
        )}
      </div>
      <div className="flex items-center gap-2 justify-self-end">
        {value !== undefined && value !== null && value !== "" && (
          <Pill tone={tone ?? "neutral"}>{value}</Pill>
        )}
        {typeof delta === "number" && (
          <Pill tone={delta < 0 ? "bad" : delta > 0 ? "ok" : "neutral"}>
            {delta > 0 ? "+" : ""}
            {delta.toFixed(2)}
          </Pill>
        )}
      </div>
    </div>
  );
}

export function gradeTone(
  grade: string,
): "ok" | "warn" | "bad" | "neutral" {
  const g = grade.toLowerCase();
  if (g === "good" || g === "low") return "ok";
  if (g === "average" || g === "medium") return "warn";
  if (g === "poor" || g === "high") return "bad";
  return "neutral";
}
