import { useMemo, useState } from "react";
import { ExternalLink } from "lucide-react";
import type { ArticleEvidence } from "@/types/schemas";

type Props = { items: ArticleEvidence[]; limit?: number };

type FilterKey = "all" | "direct" | "related_sector" | "macro";

const TAB_DEFS: { key: FilterKey; label: string; tone: string }[] = [
  { key: "all", label: "All", tone: "border-slate-400/40 text-slate-700 dark:text-slate-200" },
  { key: "direct", label: "Direct", tone: "border-emerald-500/40 text-emerald-800 dark:text-emerald-200" },
  { key: "related_sector", label: "Related", tone: "border-sky-500/40 text-sky-800 dark:text-sky-200" },
  { key: "macro", label: "Macro", tone: "border-amber-500/40 text-amber-900 dark:text-amber-100" },
];

const TIER_BADGE: Record<string, { label: string; cls: string }> = {
  direct: {
    label: "Direct",
    cls: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-200",
  },
  related_sector: {
    label: "Sector",
    cls: "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-200",
  },
  macro: {
    label: "Macro",
    cls: "border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-100",
  },
};

function formatClock(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

export function NewsTimeline({ items, limit = 14 }: Props) {
  const [filter, setFilter] = useState<FilterKey>("all");

  const counts = useMemo(() => {
    const c: Record<FilterKey, number> = { all: 0, direct: 0, related_sector: 0, macro: 0 };
    for (const x of items) {
      c.all += 1;
      const t = x.relevance_tier as FilterKey | undefined;
      if (t && t in c) c[t] += 1;
    }
    return c;
  }, [items]);

  const rows = useMemo(() => {
    const filtered = items.filter((x) => {
      if (typeof x.published_at !== "string" || !x.published_at) return false;
      if (filter === "all") return true;
      return x.relevance_tier === filter;
    });
    return filtered
      .sort((a, b) => (b.published_at ?? "").localeCompare(a.published_at ?? ""))
      .slice(0, limit);
  }, [items, filter, limit]);

  const hasRelevance = useMemo(() => items.some((x) => Boolean(x.relevance_tier)), [items]);

  return (
    <div className="space-y-2">
      {hasRelevance && (
        <div className="flex flex-wrap items-center gap-1.5">
          {TAB_DEFS.map((t) => {
            const active = filter === t.key;
            return (
              <button
                key={t.key}
                type="button"
                onClick={() => setFilter(t.key)}
                className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold transition ${
                  active
                    ? "border-indigo-500 bg-indigo-500/10 text-indigo-700 dark:text-indigo-300"
                    : `bg-transparent ${t.tone} hover:bg-[hsl(var(--muted))]`
                }`}
              >
                {t.label} <span className="ml-1 text-[10px] opacity-75">{counts[t.key]}</span>
              </button>
            );
          })}
        </div>
      )}

      {!rows.length ? (
        <p className="text-xs text-slate-500">
          {filter === "all" ? "No timestamped evidence in this report." : `No ${filter.replace("_", " ")} items in window.`}
        </p>
      ) : (
        <ul className="space-y-2">
          {rows.map((ev, i) => {
            const lab = (ev.sentiment_label ?? "").toLowerCase();
            const tone = lab.includes("bull")
              ? "text-emerald-600 dark:text-emerald-400"
              : lab.includes("bear")
                ? "text-rose-600 dark:text-rose-400"
                : "text-slate-500";
            const href = ev.url?.trim();
            const badge = ev.relevance_tier ? TIER_BADGE[ev.relevance_tier] : undefined;
            return (
              <li key={`${ev.headline}-${i}`} className="flex gap-2 text-xs">
                <span className="w-14 shrink-0 font-mono text-slate-500">{formatClock(ev.published_at as string)}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1">
                    <span className="font-medium text-slate-700 dark:text-slate-200">{ev.source}</span>
                    <span className={tone}>{ev.sentiment_label ?? "—"}</span>
                    {typeof ev.impact_score === "number" && (
                      <span className="text-slate-500">· impact {ev.impact_score.toFixed(2)}</span>
                    )}
                    {badge && (
                      <span className={`ml-1 rounded-full border px-1.5 py-0 text-[9px] font-semibold ${badge.cls}`}>
                        {badge.label}
                      </span>
                    )}
                  </div>
                  <div className="truncate text-slate-600 dark:text-slate-300">{ev.headline}</div>
                  {href ? (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-0.5 inline-flex items-center gap-1 text-[11px] font-medium text-indigo-600 hover:underline dark:text-indigo-400"
                    >
                      <ExternalLink className="h-3 w-3" />
                      Open article
                    </a>
                  ) : (
                    <span className="mt-0.5 text-[10px] text-amber-700 dark:text-amber-300">No URL</span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
