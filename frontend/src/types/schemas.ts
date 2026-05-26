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

export const relevanceTierSchema = z.enum(["direct", "related_sector", "macro", "unrelated"]);

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
    relevance_tier: relevanceTierSchema.optional(),
    relevance_score: z.number().optional(),
    relevance_reasons: z.array(z.string()).optional(),
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
    relevance_stats: z
      .object({
        direct: z.number().optional(),
        related_sector: z.number().optional(),
        macro: z.number().optional(),
        unrelated: z.number().optional(),
      })
      .nullable()
      .optional(),
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

export const expectedRangeSchema = z
  .object({
    low: z.number(),
    high: z.number(),
    sigma_pct: z.number(),
    confidence: z.number(),
  })
  .passthrough();

export const moveProbabilitiesSchema = z
  .object({
    p_up_2pct: z.number(),
    p_dn_2pct: z.number(),
    p_up_3pct: z.number(),
    p_dn_3pct: z.number(),
    p_in_range_1sigma: z.number(),
  })
  .passthrough();

export const pinRiskSchema = z
  .object({
    score: z.number(),
    label: z.enum(["Low", "Medium", "High"]),
    nearest_round: z.number(),
    distance_pct: z.number(),
  })
  .passthrough();

export const bodyDangerSchema = z
  .object({
    short_body_lo: z.number(),
    short_body_hi: z.number(),
    distance_pct: z.number(),
    label: z.enum(["Low", "Medium", "High"]),
  })
  .passthrough();

export const eventRiskSchema = z
  .object({
    score: z.number(),
    label: z.enum(["Low", "Medium", "High"]),
    drivers: z.array(z.string()).optional(),
  })
  .passthrough();

export const creditSafetySchema = z
  .object({
    score: z.number(),
    label: z.enum(["SAFE", "CAUTION", "UNSAFE"]),
    components: z
      .object({
        prob_block: z.number(),
        pin_risk: z.number(),
        body_danger: z.number(),
        event_risk: z.number(),
        vol_regime: z.number(),
      })
      .passthrough(),
  })
  .passthrough();

export const reverseBwbSchema = z
  .object({
    score: z.number(),
    label: z.enum(["SAFE", "CAUTION", "UNSAFE"]),
    suggested_wing_width_pct: z.number(),
    suggested_dte: z.number(),
    rationale: z.string(),
  })
  .passthrough();

export const optionsIntelligenceSchema = z
  .object({
    source: z.enum(["realized_vol", "live_iv"]).optional(),
    horizon_days: z.number(),
    last_close: z.number(),
    daily_vol_pct: z.number(),
    expected_range: expectedRangeSchema,
    move_probabilities: moveProbabilitiesSchema,
    pin_risk: pinRiskSchema,
    body_danger: bodyDangerSchema,
    event_risk: eventRiskSchema,
    credit_safety: creditSafetySchema,
    reverse_bwb: reverseBwbSchema,
    disclaimer: z.string().optional(),
  })
  .passthrough();

export type OptionsIntelligence = z.infer<typeof optionsIntelligenceSchema>;

export const decisionLabelSchema = z.enum(["Enter", "Wait", "Avoid"]);
export const riskLevelSchema = z.enum(["Low", "Medium", "High"]);
export const qualityLevelSchema = z.enum(["Poor", "Average", "Good"]);
export const outlookLabelSchema = z.enum([
  "Bullish",
  "Bearish",
  "Volatile",
  "Sideways",
  "Choppy",
]);

export const expectedRangeShortSchema = z.object({
  low: z.number(),
  high: z.number(),
});

export const executiveSummarySchema = z
  .object({
    decision: decisionLabelSchema,
    credit_safety_score: z.number(),
    outlook: outlookLabelSchema,
    risk: riskLevelSchema,
    confidence: riskLevelSchema,
    plus_move_risk: riskLevelSchema,
    minus_move_risk: riskLevelSchema,
    expected_range: expectedRangeShortSchema,
    event_risk: riskLevelSchema,
    iv_quality: qualityLevelSchema,
    liquidity: qualityLevelSchema,
    pin_risk: riskLevelSchema,
    summary: z.string(),
    summary_version: z.number(),
    derived_at: z.string(),
  })
  .passthrough();

export type ExecutiveSummary = z.infer<typeof executiveSummarySchema>;
export type DecisionLabel = z.infer<typeof decisionLabelSchema>;
export type RiskLevel = z.infer<typeof riskLevelSchema>;
export type QualityLevel = z.infer<typeof qualityLevelSchema>;
export type OutlookLabel = z.infer<typeof outlookLabelSchema>;

export const tickerSummaryRowSchema = z.object({
  ticker: z.string(),
  report_id: z.string().nullable(),
  deliberation_status: z
    .enum(["pending", "running", "complete", "failed", "skipped", "unavailable"])
    .nullable(),
  last_close: z.number().nullable(),
  session_change_pct: z.number().nullable(),
  executive_summary: executiveSummarySchema.nullable(),
  last_run_at: z.string().nullable(),
});

export const tickerSummariesResponseSchema = z.array(tickerSummaryRowSchema);

export type TickerSummaryRow = z.infer<typeof tickerSummaryRowSchema>;

// Explainability layer (Phase 0..10) — entirely optional / additive; the
// frontend renders only the sub-blocks whose payload is present.
const explainCreditRowSchema = z
  .object({
    label: z.string(),
    value: z.number().nullable().optional(),
    delta: z.number().nullable().optional(),
    explanation: z.string(),
  })
  .passthrough();

const explainConfidenceRowSchema = z
  .object({
    label: z.string(),
    value: z.number().nullable().optional(),
    explanation: z.string(),
  })
  .passthrough();

const explainLiquidityAxisSchema = z
  .object({
    grade: z.enum(["Poor", "Average", "Good"]),
    detail: z.string().nullable().optional(),
  })
  .passthrough();

const explainStructureGeometrySchema = z
  .object({
    spot: z.number(),
    body_strike: z.number(),
    wing_width_pct: z.number(),
    wing_width_dollars: z.number(),
    credit: z.number(),
    max_loss: z.number(),
    dte: z.number(),
    distance_to_body_pct: z.number(),
    distance_to_body_sigma: z.number(),
    body_exposure_pct: z.number(),
    wing_protection_ratio: z.number(),
    credit_efficiency: z.number(),
    risk_reward: z.number(),
    upper_breakeven: z.number(),
    lower_breakeven: z.number(),
  })
  .passthrough();

const explainTransmissionNodeSchema = z
  .object({
    node: z.string(),
    label: z.string(),
    direction: z.string().nullable().optional(),
    evidence: z.string().nullable().optional(),
  })
  .passthrough();

const explainHistoricalMatchSchema = z
  .object({
    headline: z.string().nullable().optional(),
    published_at: z.string().nullable().optional(),
    sentiment_score: z.number().nullable().optional(),
    impact_score: z.number().nullable().optional(),
    match_reason: z.string().nullable().optional(),
    match_score: z.number().nullable().optional(),
    forward_return_pct: z.number().nullable().optional(),
    body_touched: z.boolean().nullable().optional(),
    credit_retained_pct: z.number().nullable().optional(),
  })
  .passthrough();

const explainCouncilVoteSchema = z
  .object({
    member: z.string(),
    label: z.string(),
    decision: z.string(),
    confidence: z.number().nullable().optional(),
    top_reason: z.string().nullable().optional(),
  })
  .passthrough();

export const explainabilitySchema = z
  .object({
    version: z.number().optional(),
    generated_at: z.string().optional(),
    credit_safety_breakdown: z
      .object({
        move_stability: explainCreditRowSchema,
        pin_risk_impact: explainCreditRowSchema,
        event_risk_impact: explainCreditRowSchema,
        volatility_impact: explainCreditRowSchema,
        structure_placement_impact: explainCreditRowSchema,
        liquidity_impact: explainCreditRowSchema,
        final_credit_safety: z.number(),
        method: z.string().optional(),
      })
      .passthrough()
      .nullable()
      .optional(),
    confidence_calibration: z
      .object({
        raw_desk_confidence: explainConfidenceRowSchema,
        cross_agent_agreement: explainConfidenceRowSchema,
        evidence_overlap: explainConfidenceRowSchema,
        contradiction_penalty: explainConfidenceRowSchema,
        council_confidence: explainConfidenceRowSchema.nullable().optional(),
        final_confidence_pct: z.number(),
        final_confidence_bucket: z.enum(["Low", "Medium", "High"]),
      })
      .passthrough()
      .nullable()
      .optional(),
    liquidity_assessment: z
      .object({
        underlying_liquidity: explainLiquidityAxisSchema,
        options_liquidity: explainLiquidityAxisSchema,
        execution_quality: explainLiquidityAxisSchema,
        reason: z.string(),
      })
      .passthrough()
      .nullable()
      .optional(),
    structure_analysis: z
      .object({
        geometry: explainStructureGeometrySchema,
        desk_narrative: z.string().nullable().optional(),
        desk_role_key: z.string().nullable().optional(),
        desk_model: z.string().nullable().optional(),
      })
      .passthrough()
      .nullable()
      .optional(),
    position_risk: z
      .object({
        probability_of_profit: z.number(),
        probability_of_touch: z.number(),
        probability_of_breakeven: z.number(),
        probability_of_max_loss: z.number(),
        expected_value_usd: z.number(),
        method: z.string().optional(),
        assumptions: z.array(z.string()).optional(),
      })
      .passthrough()
      .nullable()
      .optional(),
    macro_transmission: z
      .object({
        chain: z.array(explainTransmissionNodeSchema).default([]),
        narrative: z.string().nullable().optional(),
        primary_shock: z.string().nullable().optional(),
        ticker_impact: z.string().nullable().optional(),
      })
      .passthrough()
      .nullable()
      .optional(),
    historical_analogs: z
      .object({
        matches: z.array(explainHistoricalMatchSchema).default([]),
        aggregates: z
          .object({
            n_setups: z.number().default(0),
            win_rate: z.number().nullable().optional(),
            avg_credit_retained: z.number().nullable().optional(),
            max_loss_frequency: z.number().nullable().optional(),
            avg_forward_return_pct: z.number().nullable().optional(),
            p_touch_body: z.number().nullable().optional(),
          })
          .passthrough(),
        lookback_window: z.string().nullable().optional(),
        sample_size_warning: z.string().nullable().optional(),
      })
      .passthrough()
      .nullable()
      .optional(),
    assessment_reasoning: z
      .object({
        lenses: z.array(
          z
            .object({
              lens: z.enum([
                "ticker_risk",
                "structure_risk",
                "position_risk",
                "historical_analogs",
                "macro_transmission",
              ]),
              summary: z.string(),
              member_views: z.array(z.string()).default([]),
            })
            .passthrough(),
        ),
        members_used: z.array(z.string()).default([]),
      })
      .passthrough()
      .nullable()
      .optional(),
    decision_justification: z
      .object({
        council_votes: z.array(explainCouncilVoteSchema).default([]),
        consensus_decision: z.string(),
        support_counts: z.record(z.string(), z.number()).default({}),
        consensus_confidence: z.number().nullable().optional(),
        primary_reasons: z.array(z.string()).default([]),
        dissent: z.array(z.string()).default([]),
        main_conflict: z.string().nullable().optional(),
      })
      .passthrough()
      .nullable()
      .optional(),
    decision_sensitivity: z
      .object({
        current_decision: z.enum(["Enter", "Wait", "Avoid"]),
        key_drivers: z
          .array(
            z
              .object({
                label: z.string(),
                weight_pct: z.number(),
                direction: z.enum(["supports", "opposes", "neutral"]).default(
                  "supports",
                ),
                detail: z.string().nullable().optional(),
              })
              .passthrough(),
          )
          .default([]),
        assumptions: z
          .array(
            z
              .object({
                label: z.string(),
                basis: z.string().nullable().optional(),
                fragility: z.enum(["low", "medium", "high"]).default("medium"),
              })
              .passthrough(),
          )
          .default([]),
        triggers: z
          .array(
            z
              .object({
                target_decision: z.enum(["Enter", "Wait", "Avoid"]),
                conditions: z.array(z.string()).default([]),
              })
              .passthrough(),
          )
          .default([]),
        analyst_disagreement: z
          .object({
            stances: z
              .array(
                z
                  .object({
                    member: z.string(),
                    label: z.string(),
                    stance: z.enum(["Bullish", "Bearish", "Neutral"]),
                    decision_view: z
                      .enum(["Enter", "Wait", "Avoid"])
                      .nullable()
                      .optional(),
                    risk_view: z
                      .enum(["Low", "Medium", "High"])
                      .nullable()
                      .optional(),
                    confidence_view: z
                      .enum(["Low", "Medium", "High"])
                      .nullable()
                      .optional(),
                    headline: z.string().nullable().optional(),
                  })
                  .passthrough(),
              )
              .default([]),
            stance_counts: z.record(z.string(), z.number()).default({}),
            main_conflict: z.string().nullable().optional(),
            converged: z.boolean().default(false),
          })
          .passthrough()
          .nullable()
          .optional(),
      })
      .passthrough()
      .nullable()
      .optional(),
  })
  .passthrough();

export type Explainability = z.infer<typeof explainabilitySchema>;

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
    options_intelligence: optionsIntelligenceSchema.optional(),
    executive_summary: executiveSummarySchema.optional(),
    explainability: explainabilitySchema.nullable().optional(),
    _pipeline_meta: pipelineMetaSchema.optional(),
  })
  .passthrough();

export type ResearchReport = z.infer<typeof researchReportSchema>;

export type ParsedResearchReport = {
  report: ResearchReport | null;
  error: string | null;
};

/** Validate a persisted report without blocking render on minor schema drift. */
export function parseResearchReportLoose(raw: unknown): ParsedResearchReport {
  if (!raw || typeof raw !== "object") {
    return { report: null, error: "Report payload is empty or invalid" };
  }
  const parsed = researchReportSchema.safeParse(raw);
  if (parsed.success) {
    return { report: parsed.data, error: null };
  }
  const message =
    parsed.error.issues[0]?.message ?? "Report payload failed validation";
  return { report: raw as ResearchReport, error: message };
}

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
  role_key: z.string().nullable().optional(),
  role_label: z.string().nullable().optional(),
  provider_attempts: z.array(z.string()).optional(),
});

export const debateCritiqueSchema = z.object({
  model: z.string(),
  role_key: z.string().nullable().optional(),
  role_label: z.string().nullable().optional(),
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
  model: z.string().optional(),
  desk_key: z.string().optional(),
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
    desks_requested: z.array(z.string()).optional(),
    desks_used: z.array(z.string()).optional(),
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
    analysis_layer: z
      .object({
        desks: z.record(z.string(), z.record(z.string(), z.unknown())).optional(),
      })
      .passthrough()
      .optional(),
    intelligence_package: z.record(z.string(), z.unknown()).optional(),
    council_layer: z.record(z.string(), z.unknown()).optional(),
    council_triggered: z.boolean().optional(),
    council_question: z.string().optional(),
    mapped_decision: z.enum(["Enter", "Wait", "Avoid"]).optional(),
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

// ---------------------------------------------------------------------------
// Reverse BWB Intelligence Dashboard — strict mirrors of
// `backend/app/services/dashboard/schemas.py`.
// ---------------------------------------------------------------------------

export const reverseBwbRiskLevelSchema = z.enum(["Low", "Medium", "High"]);
export const reverseBwbConfidenceSchema = z.enum(["Low", "Medium", "High"]);
export const reverseBwbTodayOutlookSchema = z.enum([
  "Bullish",
  "Bearish",
  "Sideways",
  "Choppy",
]);
export const reverseBwbNextOutlookSchema = z.enum([
  "Bullish",
  "Bearish",
  "Sideways",
  "Volatile",
]);
// Back-compat alias — some callers (debug panels, deliberation views) still
// reference ``reverseBwbOutlookSchema``. New code should use the explicit
// today/next variants above.
export const reverseBwbOutlookSchema = z.enum([
  "Bullish",
  "Bearish",
  "Sideways",
  "Choppy",
  "Volatile",
]);
export const reverseBwbChanceSchema = z.enum(["Low", "Medium", "High"]);
export const reverseBwbIvQualitySchema = z.enum(["Poor", "Average", "Good"]);
export const reverseBwbLiquiditySchema = z.enum(["Poor", "Average", "Good"]);
export const reverseBwbDecisionSchema = z.enum(["Enter", "Wait", "Avoid"]);
export const tickerStatusSchema = z.enum(["pending", "running", "completed", "failed"]);
export const batchStateSchema = z.enum(["idle", "running", "completed", "failed"]);
export const optionTypeSchema = z.enum(["CALL", "PUT"]);

export const reverseBwbExpectedRangeSchema = z.object({
  low: z.number(),
  high: z.number(),
});

export const reverseBwbSummarySchema = z.object({
  ticker: z.string(),
  decision: reverseBwbDecisionSchema,
  credit_safety_score: z.number(),
  risk: reverseBwbRiskLevelSchema,
  confidence: reverseBwbConfidenceSchema,
  today_outlook: reverseBwbTodayOutlookSchema,
  next_3d_outlook: reverseBwbNextOutlookSchema,
  chance_up_2_3_pct: reverseBwbChanceSchema,
  chance_down_2_3_pct: reverseBwbChanceSchema,
  expected_range_today: reverseBwbExpectedRangeSchema,
  expected_range_next_3d: reverseBwbExpectedRangeSchema,
  danger_zone: z.string(),
  pin_risk: reverseBwbRiskLevelSchema,
  event_risk: reverseBwbRiskLevelSchema,
  iv_quality: reverseBwbIvQualitySchema,
  liquidity: reverseBwbLiquiditySchema,
  actual_dynamics_summary: z.array(z.string()).min(3).max(4),
});

export const optionOpportunitySchema = z.object({
  combo: z.string(),
  expiry: z.string(),
  premium: z.number(),
  margin: z.number(),
  liquidity: reverseBwbLiquiditySchema,
});

export const optionOpportunitiesSchema = z.object({
  calls: z.array(optionOpportunitySchema),
  puts: z.array(optionOpportunitySchema),
});

export const dashboardPriceSnapshotSchema = z.object({
  price: z.number().nullable().optional(),
  daily_change_pct: z.number().nullable().optional(),
  as_of: z.string().nullable().optional(),
  source: z.string().nullable().optional(),
});

export const dashboardTickerCardSchema = z.object({
  ticker: z.string(),
  company_name: z.string(),
  tier_key: z.string(),
  status: tickerStatusSchema,
  generated_at: z.string().nullable().optional(),
  price_snapshot: dashboardPriceSnapshotSchema.nullable().optional(),
  reverse_bwb: reverseBwbSummarySchema.nullable().optional(),
  opportunities: optionOpportunitiesSchema.nullable().optional(),
  report_id: z.string().nullable().optional(),
  error_message: z.string().nullable().optional(),
});

export const watchlistBatchStatusSchema = z.object({
  state: batchStateSchema,
  current_ticker: z.string().nullable().optional(),
  queued: z.array(z.string()).default([]),
  completed: z.array(z.string()).default([]),
  failed: z.array(z.string()).default([]),
  total: z.number().default(0),
  started_at: z.string().nullable().optional(),
  finished_at: z.string().nullable().optional(),
  last_error: z.string().nullable().optional(),
});

export const dashboardTickersResponseSchema = z.object({
  status: watchlistBatchStatusSchema,
  cards: z.array(dashboardTickerCardSchema),
});

export type ReverseBwbSummary = z.infer<typeof reverseBwbSummarySchema>;
export type ReverseBwbRiskLevel = z.infer<typeof reverseBwbRiskLevelSchema>;
export type ReverseBwbConfidence = z.infer<typeof reverseBwbConfidenceSchema>;
export type ReverseBwbTodayOutlook = z.infer<typeof reverseBwbTodayOutlookSchema>;
export type ReverseBwbNextOutlook = z.infer<typeof reverseBwbNextOutlookSchema>;
export type ReverseBwbOutlook = z.infer<typeof reverseBwbOutlookSchema>;
export type ReverseBwbChance = z.infer<typeof reverseBwbChanceSchema>;
export type ReverseBwbIvQuality = z.infer<typeof reverseBwbIvQualitySchema>;
export type ReverseBwbLiquidity = z.infer<typeof reverseBwbLiquiditySchema>;
export type ReverseBwbDecision = z.infer<typeof reverseBwbDecisionSchema>;
export type OptionOpportunity = z.infer<typeof optionOpportunitySchema>;
export type OptionOpportunities = z.infer<typeof optionOpportunitiesSchema>;
export type DashboardPriceSnapshot = z.infer<typeof dashboardPriceSnapshotSchema>;
export type DashboardTickerCard = z.infer<typeof dashboardTickerCardSchema>;
export type WatchlistBatchStatus = z.infer<typeof watchlistBatchStatusSchema>;
export type DashboardTickersResponse = z.infer<typeof dashboardTickersResponseSchema>;
export type TickerStatus = z.infer<typeof tickerStatusSchema>;
export type BatchState = z.infer<typeof batchStateSchema>;
export type OptionType = z.infer<typeof optionTypeSchema>;

// ---------------------------------------------------------------------------
// Live IBKR market-data layer — strict mirrors of
// `backend/app/services/market_data/schemas.py`.
//
// NOTE: this layer is completely separate from the snapshot schemas above.
// A live price tick must never flow into the frozen analysis card
// (`ReverseBwbSummary`); the card stays static between Re-Run Analysis
// runs even while the IBKR feed pushes new ticks every second.
// ---------------------------------------------------------------------------

export const sideLiteralSchema = z.enum(["call", "put"]);
export const liquidityGradeSchema = z.enum(["Excellent", "Good", "Average", "Poor"]);
export const feedStatusSchema = z.enum([
  "live",
  "stale",
  "disconnected",
  "unavailable",
]);

export const liveQuoteSchema = z.object({
  ticker: z.string(),
  last_price: z.number().nullable().optional(),
  bid: z.number().nullable().optional(),
  ask: z.number().nullable().optional(),
  change_abs: z.number().nullable().optional(),
  change_pct: z.number().nullable().optional(),
  volume: z.number().int().nullable().optional(),
  prev_close: z.number().nullable().optional(),
  feed_status: feedStatusSchema,
  updated_at: z.string().nullable().optional(),
});

// Reverse BWB Workstation schema — every column the live + history
// generator emits. `liquidity` is now a pure integer (min OI per leg);
// the legacy `liquidity_grade` is preserved on the optional snapshot
// shape only.
export const marginSourceSchema = z.union([
  z.literal("deterministic"),
  z.literal("whatif"),
]);

export const liveOpportunitySchema = z.object({
  ticker: z.string(),
  side: sideLiteralSchema,
  rank: z.number().int().nonnegative(),
  combo: z.string(),
  strike_long_wing_a: z.number().nullable().optional(),
  strike_short_body: z.number().nullable().optional(),
  strike_long_wing_b: z.number().nullable().optional(),
  expiration: z.string(),
  expiry_days: z.number().int().nullable().optional(),
  delta_pct: z.number().nullable().optional(),
  // Sign-preserved per-share value. Negative = credit (the BWB's typical
  // case), positive = debit.
  premium: z.number(),
  init_margin: z.number().nullable().optional(),
  maint_margin: z.number().nullable().optional(),
  init_margin_source: marginSourceSchema.default("deterministic"),
  liquidity: z.number().int().nonnegative().default(0),
  minimum_open_interest: z.number().int().nullable().optional(),
  minimum_volume: z.number().int().nullable().optional(),
  oi_leg1: z.number().int().nullable().optional(),
  oi_leg2: z.number().int().nullable().optional(),
  oi_leg3: z.number().int().nullable().optional(),
  vol_leg1: z.number().int().nullable().optional(),
  vol_leg2: z.number().int().nullable().optional(),
  vol_leg3: z.number().int().nullable().optional(),
  iv_leg1: z.number().nullable().optional(),
  iv_leg2: z.number().nullable().optional(),
  iv_leg3: z.number().nullable().optional(),
  mid_leg1: z.number().nullable().optional(),
  mid_leg2: z.number().nullable().optional(),
  mid_leg3: z.number().nullable().optional(),
  credit_efficiency: z.number().nullable().optional(),
  ranking_score: z.number().nullable().optional(),
  underlying_price: z.number().nullable().optional(),
  iv: z.number().nullable().optional(),
  opportunity_version: z.string().uuid().nullable().optional(),
  generated_at: z.string().nullable().optional(),
  updated_at: z.string().nullable().optional(),
});

export const liveOpportunityBundleSchema = z.object({
  calls: z.array(liveOpportunitySchema).default([]),
  puts: z.array(liveOpportunitySchema).default([]),
  call_version: z.string().uuid().nullable().optional(),
  put_version: z.string().uuid().nullable().optional(),
  updated_at: z.string().nullable().optional(),
  feed_status: feedStatusSchema,
});

export const dashboardLiveTickerEntrySchema = z.object({
  ticker: z.string(),
  quote: liveQuoteSchema.nullable().optional(),
  opportunities: liveOpportunityBundleSchema.nullable().optional(),
});

export const dashboardLiveBundleSchema = z.object({
  feed_status: feedStatusSchema,
  prices_updated_at: z.string().nullable().optional(),
  opportunities_updated_at: z.string().nullable().optional(),
  tickers: z.record(z.string(), dashboardLiveTickerEntrySchema).default({}),
});

// Per-ticker response shapes (used by the optional single-ticker hooks).
export const marketDataResponseSchema = z.object({
  ticker: z.string(),
  price: z.number().nullable().optional(),
  bid: z.number().nullable().optional(),
  ask: z.number().nullable().optional(),
  change_abs: z.number().nullable().optional(),
  change_pct: z.number().nullable().optional(),
  volume: z.number().int().nullable().optional(),
  prev_close: z.number().nullable().optional(),
  feed_status: feedStatusSchema,
  updated_at: z.string().nullable().optional(),
});

export const optionsOpportunitiesResponseSchema = z.object({
  ticker: z.string(),
  calls: z.array(liveOpportunitySchema).default([]),
  puts: z.array(liveOpportunitySchema).default([]),
  call_version: z.string().uuid().nullable().optional(),
  put_version: z.string().uuid().nullable().optional(),
  updated_at: z.string().nullable().optional(),
  feed_status: feedStatusSchema,
});

export const opportunityExplorerResponseSchema = z.object({
  ticker: z.string(),
  total: z.number().int().nonnegative(),
  limit: z.number().int().positive(),
  offset: z.number().int().nonnegative(),
  rows: z.array(liveOpportunitySchema).default([]),
  feed_status: feedStatusSchema,
});

export const opportunityHistoryEntrySchema = liveOpportunitySchema.extend({
  id: z.string().uuid(),
  snapshot_date: z.string(),
  opportunity_version: z.string().uuid(),
  generated_at: z.string(),
});

export const opportunityHistoryResponseSchema = z.object({
  ticker: z.string(),
  total: z.number().int().nonnegative(),
  limit: z.number().int().positive(),
  offset: z.number().int().nonnegative(),
  rows: z.array(opportunityHistoryEntrySchema).default([]),
});

export type SideLiteral = z.infer<typeof sideLiteralSchema>;
export type LiquidityGrade = z.infer<typeof liquidityGradeSchema>;
export type MarginSource = z.infer<typeof marginSourceSchema>;
export type FeedStatus = z.infer<typeof feedStatusSchema>;
export type LiveQuote = z.infer<typeof liveQuoteSchema>;
export type LiveOpportunity = z.infer<typeof liveOpportunitySchema>;
export type LiveOpportunityBundle = z.infer<typeof liveOpportunityBundleSchema>;
export type DashboardLiveTickerEntry = z.infer<typeof dashboardLiveTickerEntrySchema>;
export type DashboardLiveBundle = z.infer<typeof dashboardLiveBundleSchema>;
export type MarketDataResponse = z.infer<typeof marketDataResponseSchema>;
export type OptionsOpportunitiesResponse = z.infer<typeof optionsOpportunitiesResponseSchema>;
export type OpportunityExplorerResponse = z.infer<typeof opportunityExplorerResponseSchema>;
export type OpportunityHistoryEntry = z.infer<typeof opportunityHistoryEntrySchema>;
export type OpportunityHistoryResponse = z.infer<typeof opportunityHistoryResponseSchema>;
