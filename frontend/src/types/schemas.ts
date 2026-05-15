import { z } from "zod";

export const healthSchema = z.object({
  status: z.string(),
  version: z.string(),
  db: z.boolean(),
  redis: z.boolean(),
  qdrant: z.boolean(),
});

export type Health = z.infer<typeof healthSchema>;

export const sentimentBreakdownPieceSchema = z.object({
  label: z.string(),
  count: z.number(),
  pct: z.number().optional(),
  score: z.number().optional(),
});

export const keyEventSchema = z.object({
  type: z.string().optional().nullable(),
  description: z.string().optional(),
  impact: z.string().optional(),
  impact_score: z.number().optional(),
});

export const topImpactEventSchema = z.object({
  headline: z.string().optional(),
  source: z.string().optional(),
  url: z.string().optional(),
  impact: z.number().optional(),
  event: z.string().nullable().optional(),
  abnormal_return: z.number().nullable().optional(),
});

export const articleEvidenceSchema = z
  .object({
    headline: z.string().optional(),
    source: z.string().optional(),
    url: z.string().optional(),
    published_at: z.string().optional(),
    sentiment_score: z.number().optional(),
    sentiment_label: z.string().optional(),
    impact_score: z.number().optional(),
    reliability_score: z.number().optional(),
    event_type: z.string().nullable().optional(),
    abnormal_return: z.number().nullable().optional(),
  })
  .passthrough();

export const priceSnapshotSchema = z.object({
  last_close: z.number().optional(),
  prior_close: z.number().optional(),
  last_session_change_pct: z.number().nullable().optional(),
  last_volume: z.number().optional(),
  avg_volume_20d: z.number().optional(),
  volume_vs_avg: z.number().nullable().optional(),
});

export const pipelineMetaSchema = z
  .object({
    run_id: z.string().optional(),
    raw_articles: z.number().optional(),
    after_dedupe: z.number().optional(),
    duplicates_removed: z.number().optional(),
    clusters_to_claude: z.number().optional(),
    sources: z.array(z.string()).optional(),
    volatility_regime: z.string().optional(),
    price_snapshot: priceSnapshotSchema.optional(),
    article_evidence: z.array(articleEvidenceSchema).optional(),
    top_impact_events: z.array(topImpactEventSchema).optional(),
    data_mode: z.string().optional(),
    elapsed_s: z.number().optional(),
    run_at: z.string().optional(),
  })
  .passthrough();

export type ArticleEvidence = z.infer<typeof articleEvidenceSchema>;
export type PipelineMeta = z.infer<typeof pipelineMetaSchema>;

export const sourceReliabilitySchema = z.object({
  source: z.string(),
  articles: z.number().optional(),
  reliability_score: z.number().optional(),
  tier: z.string().optional(),
});

export const reportArticleSchema = z.object({
  headline: z.string().optional(),
  source: z.string().optional(),
  url: z.string().optional(),
  published_at: z.string().optional(),
  sentiment: z.number().optional(),
  sentiment_label: z.string().optional(),
  impact_score: z.number().optional(),
  event_type: z.string().nullable().optional(),
  reliability_score: z.number().optional(),
  ai_summary: z.string().optional(),
});

export const pricePredictionSchema = z.object({
  last_close: z.number().optional(),
  low: z.number().optional(),
  base: z.number().optional(),
  high: z.number().optional(),
  change_pct_low: z.number().optional(),
  change_pct_base: z.number().optional(),
  change_pct_high: z.number().optional(),
  confidence: z.number().optional(),
  bias: z.string().optional(),
  volatility_regime: z.string().optional(),
  reasoning: z.string().optional(),
  upside_catalyst: z.string().optional(),
  downside_risk: z.string().optional(),
  disclaimer: z.string().optional(),
});

export const researchReportSchema = z
  .object({
    data_mode: z.string().optional(),
    data_quality_note: z.string().optional(),
    articles_analyzed: z.number().optional(),
    unique_sources: z.number().optional(),
    duplicates_removed: z.number().optional(),
    overall_sentiment_score: z.number().optional(),
    overall_sentiment_label: z.string().optional(),
    sentiment_breakdown: z.array(sentimentBreakdownPieceSchema).optional(),
    key_events: z.array(keyEventSchema).optional(),
    dominant_narrative: z.string().optional(),
    what_happened: z.string().optional(),
    price_movers: z.string().optional(),
    source_reliability: z.array(sourceReliabilitySchema).optional(),
    articles: z.array(reportArticleSchema).optional(),
    price_prediction: pricePredictionSchema.optional(),
    _pipeline_meta: pipelineMetaSchema.optional(),
  })
  .passthrough();

export type ResearchReport = z.infer<typeof researchReportSchema>;
