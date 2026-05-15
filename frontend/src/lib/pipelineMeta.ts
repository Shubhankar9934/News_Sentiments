import type { ArticleEvidence, PipelineMeta, ResearchReport } from "@/types/schemas";

export function getPipelineMeta(report: ResearchReport): PipelineMeta | undefined {
  const m = report._pipeline_meta;
  if (m && typeof m === "object") return m as PipelineMeta;
  return undefined;
}

export function getArticleEvidence(report: ResearchReport): ArticleEvidence[] {
  const raw = getPipelineMeta(report)?.article_evidence ?? [];
  return raw.filter(
    (r) => typeof r.headline === "string" && r.headline.trim().length > 0 && typeof r.published_at === "string"
  ) as ArticleEvidence[];
}

export function getPriceSnapshot(report: ResearchReport) {
  return getPipelineMeta(report)?.price_snapshot;
}

export function pickDominantEventType(report: ResearchReport): string | null {
  const evidence = getArticleEvidence(report);
  const counts = new Map<string, number>();
  for (const e of evidence) {
    const t = e.event_type?.trim();
    if (!t) continue;
    counts.set(t, (counts.get(t) ?? 0) + 1);
  }
  let best: string | null = null;
  let n = 0;
  for (const [k, v] of counts) {
    if (v > n) {
      n = v;
      best = k;
    }
  }
  if (best) return best;
  const fromKey = report.key_events?.find((x) => x.type?.trim())?.type;
  return fromKey?.trim() ?? null;
}
