import { formatUtcTimestamp } from "@/lib/formatTimestamp";
import { cn } from "@/lib/utils";
import type { TickerStatus } from "@/types/schemas";

type Props = {
  generatedAt: string | null | undefined;
  status: TickerStatus | "running";
  isRunning: boolean;
  errorMessage?: string | null;
};

const ANALYSIS_TONE: Record<string, string> = {
  Completed: "text-emerald-600 dark:text-emerald-400",
  Failed: "text-rose-600 dark:text-rose-400",
  Running: "text-amber-600 dark:text-amber-400",
  Pending: "text-[hsl(var(--terminal-text-tertiary))]",
};

function analysisLabel(status: TickerStatus | "running"): string {
  switch (status) {
    case "running":
      return "Running";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    default:
      return "Pending";
  }
}

function updatedLabel(
  generatedAt: string | null | undefined,
  isRunning: boolean,
): string {
  if (generatedAt) return formatUtcTimestamp(generatedAt);
  if (isRunning) return "Updating…";
  return "Not yet analyzed";
}

export function CardAnalysisMeta({ generatedAt, status, isRunning, errorMessage }: Props) {
  const label = analysisLabel(status);
  const tone = ANALYSIS_TONE[label] ?? ANALYSIS_TONE.Pending;

  return (
    <div className="flex flex-col gap-0.5 border-b border-[hsl(var(--terminal-border))]/60 pb-3 text-[11px] leading-snug">
      <div className="flex flex-wrap gap-x-1.5 text-[hsl(var(--terminal-text-tertiary))]">
        <span className="font-medium uppercase tracking-wider">Updated:</span>
        <span className="font-mono text-[hsl(var(--terminal-text-secondary))]">
          {updatedLabel(generatedAt, isRunning)}
        </span>
      </div>
      <div
        className="flex flex-wrap gap-x-1.5"
        title={status === "failed" && errorMessage ? errorMessage : undefined}
      >
        <span className="font-medium uppercase tracking-wider text-[hsl(var(--terminal-text-tertiary))]">
          Analysis:
        </span>
        <span className={cn("font-semibold", tone)}>{label}</span>
      </div>
    </div>
  );
}
