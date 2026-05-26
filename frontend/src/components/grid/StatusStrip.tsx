import { ShieldCheck, Eye, AlertOctagon } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DecisionLabel } from "@/types/schemas";

type Props = {
  decision: DecisionLabel | null;
  creditSafetyScore: number | null;
  loading?: boolean;
};

function decisionPalette(decision: DecisionLabel | null): {
  bg: string;
  ring: string;
  text: string;
  scoreText: string;
  Icon: typeof ShieldCheck;
} {
  // Tolerate both the new ``Enter`` and legacy ``SAFE`` vocabularies so a
  // refresh that lands mid-rollout keeps the chip rendering correctly.
  const normalised = (decision ?? "").toString().toUpperCase();
  if (normalised === "ENTER" || normalised === "SAFE") {
    return {
      bg: "bg-emerald-500/15",
      ring: "border-emerald-500/40",
      text: "text-emerald-200",
      scoreText: "text-emerald-300",
      Icon: ShieldCheck,
    };
  }
  if (normalised === "WAIT" || normalised === "WATCH") {
    return {
      bg: "bg-amber-500/15",
      ring: "border-amber-500/40",
      text: "text-amber-100",
      scoreText: "text-amber-200",
      Icon: Eye,
    };
  }
  if (normalised === "AVOID") {
    return {
      bg: "bg-rose-500/15",
      ring: "border-rose-500/40",
      text: "text-rose-200",
      scoreText: "text-rose-300",
      Icon: AlertOctagon,
    };
  }
  return {
    bg: "bg-slate-700/30",
    ring: "border-slate-500/40",
    text: "text-slate-200",
    scoreText: "text-slate-300",
    Icon: Eye,
  };
}

export function StatusStrip({ decision, creditSafetyScore, loading }: Props) {
  const palette = decisionPalette(decision);
  const { Icon } = palette;
  const score = creditSafetyScore ?? 0;
  const showScore = creditSafetyScore != null;

  return (
    <div
      className={cn(
        "flex items-center justify-between gap-3 rounded-md border px-4 py-3",
        palette.bg,
        palette.ring,
        loading && "opacity-50",
      )}
    >
      <div className="flex items-center gap-2.5">
        <Icon className={cn("h-5 w-5", palette.text)} aria-hidden="true" />
        <div className={cn("text-base font-bold uppercase tracking-[0.18em]", palette.text)}>
          {decision ?? "PENDING"}
        </div>
      </div>
      <div className="flex flex-col items-end leading-none">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--terminal-text-secondary))]">
          Credit Safety
        </span>
        <span className={cn("font-mono text-lg font-bold", palette.scoreText)}>
          {showScore ? score.toFixed(1) : "—"}
          <span className="text-xs text-slate-500">/10</span>
        </span>
      </div>
    </div>
  );
}
