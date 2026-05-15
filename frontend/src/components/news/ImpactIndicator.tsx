import { cn } from "@/lib/utils";

function band(score: number | undefined): { label: string; cls: string } {
  if (typeof score !== "number" || Number.isNaN(score)) {
    return { label: "—", cls: "bg-slate-500/20 text-slate-600 dark:text-slate-300" };
  }
  if (score >= 0.45) return { label: "HIGH", cls: "bg-rose-500/15 text-rose-700 dark:text-rose-300" };
  if (score >= 0.22) return { label: "MED", cls: "bg-amber-500/15 text-amber-800 dark:text-amber-200" };
  return { label: "LOW", cls: "bg-slate-500/15 text-slate-700 dark:text-slate-300" };
}

type Props = { impact?: number; className?: string };

export function ImpactIndicator({ impact, className }: Props) {
  const { label, cls } = band(impact);
  return (
    <span
      className={cn("rounded px-1.5 py-0.5 text-[10px] font-bold tabular-nums", cls, className)}
      title={typeof impact === "number" ? `Impact ${impact.toFixed(3)}` : undefined}
    >
      Impact {label}
    </span>
  );
}
