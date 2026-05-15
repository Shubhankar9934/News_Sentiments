import { cn } from "@/lib/utils";

function inferTier(source: string, tier?: string): string {
  if (tier?.trim()) return tier.trim();
  const s = source.toLowerCase();
  if (/reuters|bloomberg|wsj|financial times|sec\.gov/.test(s)) return "Tier 1";
  if (/cnbc|ft\.com|marketwatch|ap news/.test(s)) return "Tier 2";
  if (/reddit|twitter|x\.com|stocktwits/.test(s)) return "Social";
  if (/yahoo|seeking alpha|benzinga|fool|motley/.test(s)) return "Tier 3";
  return "Tier 2";
}

const tierStyle: Record<string, string> = {
  "Tier 1": "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  "Tier 2": "border-sky-500/40 bg-sky-500/10 text-sky-800 dark:text-sky-200",
  "Tier 3": "border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-200",
  Social: "border-violet-500/40 bg-violet-500/10 text-violet-800 dark:text-violet-200",
  Primary: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
};

type Props = { source: string; tier?: string; className?: string };

export function SourceBadge({ source, tier, className }: Props) {
  const t = inferTier(source, tier);
  return (
    <span
      className={cn(
        "inline-flex max-w-[14rem] min-w-0 items-center rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        tierStyle[t] ?? "border-[hsl(var(--border))] bg-[hsl(var(--muted))] text-slate-700 dark:text-slate-200",
        className
      )}
      title={`${source} · ${t}`}
    >
      <span className="flex min-w-0 items-center gap-1">
        <span className="truncate">{source}</span>
        <span className="shrink-0 opacity-70">· {t}</span>
      </span>
    </span>
  );
}
