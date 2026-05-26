import { SectionFrame } from "@/components/grid/primitives";
import { cn } from "@/lib/utils";
import { riskFillPct, toneFor, type Tone } from "@/lib/deriveDecisionTone";
import type { ExecutiveSummary, RiskLevel } from "@/types/schemas";

function MoveBar({
  label,
  level,
  direction,
}: {
  label: string;
  level: RiskLevel | null;
  direction: "up" | "down";
}) {
  const pct = level ? riskFillPct(level) : 0;
  const tone: Tone = level ? toneFor(level) : "neutral";
  const fillClass =
    tone === "ok"
      ? "bg-emerald-400"
      : tone === "warn"
        ? "bg-amber-400"
        : tone === "bad"
          ? "bg-rose-400"
          : "bg-slate-500";
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-[11px] font-semibold tracking-tight text-slate-300">
          <span
            aria-hidden="true"
            className={cn(
              "inline-block h-2 w-2 rounded-full",
              direction === "up" ? "bg-emerald-400" : "bg-rose-400",
            )}
          />
          {label}
        </span>
        <span
          className={cn(
            "font-mono text-[11px] font-bold uppercase tracking-wider",
            tone === "ok"
              ? "text-emerald-300"
              : tone === "warn"
                ? "text-amber-200"
                : tone === "bad"
                  ? "text-rose-300"
                  : "text-slate-400",
          )}
        >
          {level ?? "—"}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-[hsl(var(--terminal-card-elevated))]">
        <div
          className={cn("h-full rounded-full transition-[width] duration-300", fillClass)}
          style={{ width: `${pct * 100}%` }}
        />
      </div>
    </div>
  );
}

export function MovementRiskPanel({ summary }: { summary: ExecutiveSummary | null }) {
  return (
    <SectionFrame title="Movement Risk">
      <div className="flex flex-col gap-3 rounded-md border border-[hsl(var(--terminal-border))] bg-[hsl(var(--terminal-card-elevated))]/50 p-3">
        <MoveBar
          label="+2-3% Move Risk"
          level={summary?.plus_move_risk ?? null}
          direction="up"
        />
        <MoveBar
          label="-2-3% Move Risk"
          level={summary?.minus_move_risk ?? null}
          direction="down"
        />
        <div className="flex items-center justify-between gap-2 border-t border-[hsl(var(--terminal-border))] pt-2">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--terminal-text-secondary))]">
            Expected Range
          </span>
          <span className="font-mono text-sm font-bold text-slate-100">
            {summary
              ? `${summary.expected_range.low.toFixed(2)} → ${summary.expected_range.high.toFixed(2)}`
              : "—"}
          </span>
        </div>
      </div>
    </SectionFrame>
  );
}
