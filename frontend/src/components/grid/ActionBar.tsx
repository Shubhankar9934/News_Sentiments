import { ArrowUpRight, Loader2, Play, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

type Props = {
  status: "IDLE" | "RUNNING" | "COMPLETED" | "FAILED";
  onRunAnalysis: () => void;
  onOpenFullReport: () => void;
  hasReport: boolean;
};

export function ActionBar({ status, onRunAnalysis, onOpenFullReport, hasReport }: Props) {
  const running = status === "RUNNING";
  const failed = status === "FAILED";
  const runLabel = running ? "Running…" : failed ? "Retry" : hasReport ? "Re-run Analysis" : "Run Analysis";
  const RunIcon = running ? Loader2 : failed ? RefreshCw : Play;
  return (
    <div className="grid grid-cols-2 gap-2">
      <Button
        size="sm"
        onClick={onRunAnalysis}
        disabled={running}
        className="h-9 bg-indigo-500 text-white hover:bg-indigo-400 dark:bg-indigo-500 dark:text-white dark:hover:bg-indigo-400"
      >
        <RunIcon className={running ? "h-4 w-4 animate-spin" : "h-4 w-4"} aria-hidden="true" />
        {runLabel}
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={onOpenFullReport}
        disabled={!hasReport || running}
        className="h-9 border-[hsl(var(--terminal-border))] text-slate-200 hover:bg-[hsl(var(--terminal-card-elevated))] hover:text-slate-100"
      >
        <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
        Open Full Report
      </Button>
    </div>
  );
}
