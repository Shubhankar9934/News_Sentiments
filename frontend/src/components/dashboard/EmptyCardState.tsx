/**
 * Fallback body shown inside the ticker card when the backend has not yet
 * produced a successful refresh for this ticker (status === "pending" or
 * "failed"). Keeps the card height stable so the grid layout never reflows.
 */

import { AlertCircle, Clock } from "lucide-react";

type Props = {
  status: "pending" | "failed" | "running";
  errorMessage?: string | null;
};

export function EmptyCardState({ status, errorMessage }: Props) {
  const isFailed = status === "failed";
  const isRunning = status === "running";
  const Icon = isFailed ? AlertCircle : Clock;

  const headline = isFailed
    ? "Data unavailable"
    : isRunning
      ? "Refresh running"
      : "Awaiting first refresh";

  const subline = isFailed
    ? "Retry pending — the next batch will re-run this ticker."
    : isRunning
      ? "Pipeline + Reverse BWB summary in flight..."
      : "Click Refresh All to populate this card.";

  return (
    <div
      className="flex flex-1 flex-col items-center justify-center gap-2 rounded-md border border-dashed border-[hsl(var(--terminal-border))] bg-[hsl(var(--terminal-card-elevated))]/40 px-4 py-10 text-center"
      role="status"
    >
      <Icon
        className={
          isFailed
            ? "h-6 w-6 text-rose-600 dark:text-rose-300"
            : isRunning
              ? "h-6 w-6 animate-pulse text-amber-600 dark:text-amber-200"
              : "h-6 w-6 text-slate-400"
        }
        aria-hidden
      />
      <div className="font-mono text-[12px] font-semibold uppercase tracking-wider text-[hsl(var(--terminal-text-primary))]">
        {headline}
      </div>
      <div className="max-w-[240px] text-[11px] text-[hsl(var(--terminal-text-secondary))]">
        {subline}
      </div>
      {isFailed && errorMessage ? (
        <div
          className="mt-1 max-w-full overflow-hidden truncate font-mono text-[10px] text-rose-700 dark:text-rose-300/80"
          title={errorMessage}
        >
          {errorMessage}
        </div>
      ) : null}
    </div>
  );
}
