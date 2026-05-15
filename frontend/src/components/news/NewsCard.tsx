import { ImpactIndicator } from "@/components/news/ImpactIndicator";
import { ReliabilityMeter } from "@/components/news/ReliabilityMeter";
import { SourceBadge } from "@/components/news/SourceBadge";
import { VerificationPanel } from "@/components/news/VerificationPanel";
import type { ArticleEvidence, ResearchReport } from "@/types/schemas";

type LlmArticle = NonNullable<ResearchReport["articles"]>[number];

type Props = {
  row: ArticleEvidence;
  llmArticle?: LlmArticle;
};

function formatTime(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function NewsCard({ row, llmArticle }: Props) {
  const summary = llmArticle?.ai_summary?.trim();
  return (
    <details className="group rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] text-sm">
      <summary className="flex cursor-pointer list-none flex-wrap items-center gap-2 px-3 py-2 marker:content-none [&::-webkit-details-marker]:hidden">
        <SourceBadge source={row.source ?? "Unknown"} />
        <span className="min-w-0 flex-1 truncate font-medium text-slate-900 dark:text-slate-50">
          {row.headline}
        </span>
        <span className="text-xs text-slate-500">{formatTime(row.published_at ?? "")}</span>
        <span
          className={
            (row.sentiment_label ?? "").toLowerCase().includes("bull")
              ? "text-emerald-600 dark:text-emerald-400"
              : (row.sentiment_label ?? "").toLowerCase().includes("bear")
                ? "text-rose-600 dark:text-rose-400"
                : "text-slate-500"
          }
        >
          {row.sentiment_label ?? "—"}
        </span>
        <ImpactIndicator impact={row.impact_score} />
      </summary>
      <div className="space-y-3 border-t border-[hsl(var(--border))] px-3 py-3 text-xs">
        <div className="flex flex-wrap items-center gap-3">
          <ReliabilityMeter score={row.reliability_score} />
          {row.event_type && (
            <span className="rounded bg-[hsl(var(--muted))] px-2 py-0.5 font-mono text-[10px] uppercase text-slate-600 dark:text-slate-300">
              {row.event_type}
            </span>
          )}
          {typeof row.sentiment_score === "number" && (
            <span className="font-mono text-slate-600 dark:text-slate-300">
              FinBERT {row.sentiment_score >= 0 ? "+" : ""}
              {row.sentiment_score.toFixed(2)}
            </span>
          )}
        </div>
        {summary && (
          <div>
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">AI line</div>
            <p className="leading-relaxed text-slate-700 dark:text-slate-200">{summary}</p>
          </div>
        )}
        <VerificationPanel url={row.url} headline={row.headline ?? ""} />
        {typeof row.abnormal_return === "number" && (
          <p className="text-[11px] text-slate-500">
            Same-day return on article date (broad tape proxy):{" "}
            <span className="font-mono font-medium text-slate-700 dark:text-slate-200">
              {row.abnormal_return >= 0 ? "+" : ""}
              {row.abnormal_return.toFixed(2)}%
            </span>
          </p>
        )}
      </div>
    </details>
  );
}
