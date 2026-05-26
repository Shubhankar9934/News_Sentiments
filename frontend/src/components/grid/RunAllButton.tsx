import { Loader2, Play, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { RunAllSnapshot } from "@/hooks/useRunAll";

type Props = {
  snapshot: RunAllSnapshot;
  onStart: () => void;
  onCancel: () => void;
};

export function RunAllButton({ snapshot, onStart, onCancel }: Props) {
  const running = snapshot.isRunning;
  if (running) {
    return (
      <div className="flex items-center gap-2">
        <span className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-1.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-amber-200">
          <Loader2 className="mr-1.5 inline h-3 w-3 animate-spin" />
          {snapshot.finished}/{snapshot.total} done · {snapshot.failed} failed
        </span>
        <Button
          size="sm"
          variant="outline"
          onClick={onCancel}
          className="border-rose-500/40 text-rose-200 hover:bg-rose-500/10"
        >
          <Square className="h-4 w-4" /> Cancel queue
        </Button>
      </div>
    );
  }
  return (
    <Button
      size="sm"
      onClick={onStart}
      className={cn(
        "h-9 bg-emerald-500 px-4 text-white hover:bg-emerald-400",
        "dark:bg-emerald-500 dark:text-white dark:hover:bg-emerald-400",
      )}
    >
      <Play className="h-4 w-4" /> Run All
    </Button>
  );
}
