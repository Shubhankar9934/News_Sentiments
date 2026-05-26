import { Clock } from "lucide-react";

type Props = {
  lastRunAt: string | null;
  state: "IDLE" | "RUNNING" | "COMPLETED" | "FAILED";
  error?: string;
};

function relative(iso: string | null): string {
  if (!iso) return "Never";
  const ts = Date.parse(iso);
  if (Number.isNaN(ts)) return "Unknown";
  const diffMs = Date.now() - ts;
  if (diffMs < 60_000) return "just now";
  if (diffMs < 3_600_000) return `${Math.round(diffMs / 60_000)}m ago`;
  if (diffMs < 86_400_000) return `${Math.round(diffMs / 3_600_000)}h ago`;
  return new Date(ts).toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatAbsolute(iso: string | null): string {
  if (!iso) return "—";
  const ts = Date.parse(iso);
  if (Number.isNaN(ts)) return iso;
  return new Date(ts).toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

export function ReportFooter({ lastRunAt, state, error }: Props) {
  if (state === "FAILED") {
    return (
      <footer className="flex items-center justify-between gap-2 border-t border-[hsl(var(--terminal-border))] pt-2 text-[11px] text-rose-300">
        <span className="font-semibold uppercase tracking-wider">Analysis failed</span>
        <span className="truncate text-rose-400/80">{error ?? "see logs"}</span>
      </footer>
    );
  }
  return (
    <footer className="flex items-center justify-between gap-2 border-t border-[hsl(var(--terminal-border))] pt-2 text-[11px] text-[hsl(var(--terminal-text-secondary))]">
      <span className="inline-flex items-center gap-1.5">
        <Clock className="h-3 w-3" />
        Last updated {relative(lastRunAt)}
      </span>
      <span className="font-mono text-[10px] text-[hsl(var(--terminal-text-tertiary))]">
        {formatAbsolute(lastRunAt)}
      </span>
    </footer>
  );
}
