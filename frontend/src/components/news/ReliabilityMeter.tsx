import { cn } from "@/lib/utils";

type Props = { score?: number; className?: string };

export function ReliabilityMeter({ score, className }: Props) {
  const s = typeof score === "number" && !Number.isNaN(score) ? Math.min(100, Math.max(0, score)) : null;
  return (
    <div className={cn("flex items-center gap-2", className)} title={s != null ? `Reliability ${s}/100` : undefined}>
      <span className="text-[10px] font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
        Reliability
      </span>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-[hsl(var(--muted))]">
        <div
          className="h-full rounded-full bg-indigo-500 transition-[width]"
          style={{ width: s != null ? `${s}%` : "0%" }}
        />
      </div>
      <span className="w-8 text-[10px] font-mono tabular-nums text-slate-600 dark:text-slate-300">
        {s != null ? s : "—"}
      </span>
    </div>
  );
}
