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
    report_id: z.string().optional(),
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

export const reasoningStepSchema = z.object({
  step: z.number(),
  title: z.string(),
  analysis: z.string(),
});

export const independentOpinionSchema = z.object({
  model: z.string(),
  stance: z.string(),
  confidence: z.number(),
  time_horizon: z.string().optional(),
  reasoning_steps: z.array(reasoningStepSchema).optional(),
  key_risks: z.array(z.string()).optional(),
  invalidators: z.array(z.string()).optional(),
  position_size_suggestion: z.string().optional(),
  hidden_assumptions: z.array(z.string()).optional(),
  error: z.string().nullable().optional(),
});

export const debateCritiqueSchema = z.object({
  model: z.string(),
  agrees_with: z.array(z.string()).optional(),
  disagrees_with: z.array(z.string()).optional(),
  strongest_counterargument: z.string().optional(),
  weakest_reasoning_detected: z.string().optional(),
  new_risks_identified: z.array(z.string()).optional(),
  confidence_revision: z
    .object({ old: z.number(), new: z.number() })
    .nullable()
    .optional(),
  error: z.string().nullable().optional(),
});

export const calibrationOutputSchema = z.object({
  directional_conviction: z.number(),
  consensus_strength: z.number(),
  evidence_quality: z.number(),
  confidence_aggregate: z.number(),
  uncertainty: z.enum(["high", "medium", "low"]),
});

export const structuredRiskSchema = z.object({
  cluster_id: z.string(),
  headline: z.string(),
  members: z.array(z.string()).optional(),
  support_models: z.array(z.string()).optional(),
  support_count: z.number().optional(),
  severity: z.enum(["high", "medium", "low"]).optional(),
  topic: z.string().optional(),
});

export const thesisClusterSchema = z.object({
  stance: z.string(),
  models: z.array(z.string()).optional(),
  bullets: z.array(z.string()).optional(),
  summary: z.string().optional(),
  support_count: z.number().optional(),
});

export const consensusOutputSchema = z.object({
  consensus: z.string(),
  agreement_score: z.number(),
  uncertainty: z.enum(["high", "medium", "low"]),
  main_conflicts: z.array(z.string()).optional(),
  hidden_risks: z.array(z.string()).optional(),
  recommended_positioning: z.string().optional(),
  debate_summary: z.string().optional(),
  dominant_thesis: z.string().optional(),
  conflicting_thesis: z.string().optional(),
  reconciled_label: z.string().nullable().optional(),
  support_counts: z.record(z.string(), z.array(z.string())).optional(),
  calibration: calibrationOutputSchema.nullable().optional(),
  structured_risks: z.array(structuredRiskSchema).optional(),
  thesis_clusters: z.array(thesisClusterSchema).optional(),
});

export const debateAssignmentSchema = z.object({
  round: z.number(),
  model: z.string(),
  targets: z.array(z.string()).optional(),
  role: z.string().optional(),
  rationale: z.string().optional(),
});

export const deliberationLayerSchema = z
  .object({
    report_id: z.string().optional(),
    status: z.enum(["pending", "running", "complete", "failed", "skipped", "unavailable"]),
    run_id: z.string().optional(),
    started_at: z.string().optional(),
    completed_at: z.string().optional(),
    models_requested: z.array(z.string()).optional(),
    models_used: z.array(z.string()).optional(),
    round1: z.record(z.string(), independentOpinionSchema).optional(),
    debate_rounds: z.array(z.record(z.string(), debateCritiqueSchema)).optional(),
    debate_assignments: z.array(debateAssignmentSchema).optional(),
    evidence_verification: z
      .array(
        z.object({
          id: z.string(),
          claim: z.string(),
          source_title: z.string().nullable().optional(),
          source_url: z.string().nullable().optional(),
          status: z.string(),
          supporting_models: z.array(z.string()).optional(),
          contradicting_models: z.array(z.string()).optional(),
        }),
      )
      .optional(),
    consensus: consensusOutputSchema.optional(),
    metrics: z
      .object({
        disagreement_matrix: z.record(z.string(), z.record(z.string(), z.string())).optional(),
        confidence_drift: z
          .array(
            z.object({
              model: z.string(),
              before: z.number(),
              after: z.number(),
              delta: z.number(),
            })
          )
          .optional(),
        model_divergence: z.number().optional(),
        confidence_spread: z.number().optional(),
        contradiction_density: z.number().optional(),
        reasoning_overlap: z.number().optional(),
        round_novelty: z
          .array(
            z.object({
              model: z.string(),
              similarity: z.number(),
              low_novelty: z.boolean(),
            }),
          )
          .optional(),
        disagreement_topology: z
          .object({
            axes: z.record(z.string(), z.number()).optional(),
            overall: z.number().optional(),
            hot_topics: z.array(z.string()).optional(),
          })
          .nullable()
          .optional(),
        conviction_heatmap: z
          .object({
            topics: z.array(z.string()).optional(),
            models: z.array(z.string()).optional(),
            cells: z
              .record(
                z.string(),
                z.record(
                  z.string(),
                  z.object({
                    stance: z.string(),
                    confidence: z.number(),
                    risk_score: z.number(),
                  }),
                ),
              )
              .optional(),
          })
          .nullable()
          .optional(),
        contradictions: z
          .array(
            z
              .object({
                type: z.string(),
                topic: z.string().optional(),
                model_a: z.string(),
                model_b: z.string().optional(),
                stance_a: z.string().optional(),
                stance_b: z.string().optional(),
                severity: z.string().optional(),
                note: z.string().optional(),
                evidence_refs: z.array(z.string()).optional(),
              })
              .passthrough(),
          )
          .optional(),
      })
      .passthrough()
      .optional(),
    error: z.string().optional(),
    skip_reason: z.string().optional(),
  })
  .passthrough();

export type DeliberationLayer = z.infer<typeof deliberationLayerSchema>;
export type IndependentOpinion = z.infer<typeof independentOpinionSchema>;
export type DebateCritique = z.infer<typeof debateCritiqueSchema>;
export type ConsensusOutput = z.infer<typeof consensusOutputSchema>;
export type CalibrationOutput = z.infer<typeof calibrationOutputSchema>;
export type DebateAssignment = z.infer<typeof debateAssignmentSchema>;
export type StructuredRisk = z.infer<typeof structuredRiskSchema>;
export type ThesisCluster = z.infer<typeof thesisClusterSchema>;
