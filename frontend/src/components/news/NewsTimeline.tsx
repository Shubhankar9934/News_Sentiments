import { ExternalLink } from "lucide-react";
import type { ArticleEvidence } from "@/types/schemas";

type Props = { items: ArticleEvidence[]; limit?: number };

function formatClock(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

export function NewsTimeline({ items, limit = 14 }: Props) {
  const rows = [...items]
    .filter((x): x is ArticleEvidence & { published_at: string } => typeof x.published_at === "string" && x.published_at.length > 0)
    .sort((a, b) => b.published_at.localeCompare(a.published_at))
    .slice(0, limit);
  if (!rows.length) {
    return <p className="text-xs text-slate-500">No timestamped evidence in this report.</p>;
  }
  return (
    <ul className="space-y-2">
      {rows.map((ev, i) => {
        const lab = (ev.sentiment_label ?? "").toLowerCase();
        const tone =
          lab.includes("bull") ? "text-emerald-600 dark:text-emerald-400" : lab.includes("bear") ? "text-rose-600 dark:text-rose-400" : "text-slate-500";
        const href = ev.url?.trim();
        return (
          <li key={`${ev.headline}-${i}`} className="flex gap-2 text-xs">
            <span className="w-14 shrink-0 font-mono text-slate-500">{formatClock(ev.published_at)}</span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-1">
                <span className="font-medium text-slate-700 dark:text-slate-200">{ev.source}</span>
                <span className={tone}>{ev.sentiment_label ?? "—"}</span>
                {typeof ev.impact_score === "number" && (
                  <span className="text-slate-500">· impact {ev.impact_score.toFixed(2)}</span>
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
  );
}
