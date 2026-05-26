/**
 * Header button that triggers the backend's sequential watchlist batch.
 *
 * Renders three states from the live ``WatchlistBatchStatus``:
 *   idle / completed  -> green "Refresh All"
 *   running           -> amber progress chip "<current> · N/total done · F failed"
 *   failed            -> rose chip with retry affordance
 */

import { Loader2, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { WatchlistBatchStatus } from "@/types/schemas";

type Props = {
  status: WatchlistBatchStatus;
  onRefresh: () => void;
  isPending: boolean;
};

export function RefreshAllButton({ status, onRefresh, isPending }: Props) {
  const running = status.state === "running";
  const finished = status.completed.length + status.failed.length;
  const queuedCount = status.queued?.length ?? 0;

  if (running) {
    return (
      <div className="flex items-center gap-2">
        <span
          className="rounded-md border border-amber-600/30 bg-amber-50 px-3 py-1.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200"
          aria-live="polite"
        >
          <Loader2 className="mr-1.5 inline h-3 w-3 animate-spin" />
          {status.current_ticker ? `${status.current_ticker} · ` : ""}
          {finished}/{status.total} done
          {queuedCount > 0 ? ` · ${queuedCount} queued` : ""}
          {status.failed.length > 0 ? ` · ${status.failed.length} failed` : ""}
        </span>
      </div>
    );
  }

  return (
    <Button
      size="sm"
      onClick={onRefresh}
      disabled={isPending}
      className={cn(
        "h-9 bg-emerald-500 px-4 text-white hover:bg-emerald-400",
        "dark:bg-emerald-500 dark:text-white dark:hover:bg-emerald-400",
      )}
    >
      {isPending ? (
        <>
          <Loader2 className="h-4 w-4 animate-spin" /> Queuing…
        </>
      ) : (
        <>
          <RefreshCw className="h-4 w-4" /> Refresh All
        </>
      )}
    </Button>
  );
}
