/**
 * Client-side fallback that mirrors the backend `extract_executive_summary`.
 *
 * Used in two places:
 *   1. Old reports persisted before the backend extractor existed.
 *   2. The "fresh research returned but DIL not yet complete" window inside a
 *      single render cycle, where we already have the report dict in memory
 *      and don't want to spin a separate hook.
 *
 * Mirrors backend thresholds in `backend/app/services/summary/extractor.py`.
 * Keep both files synced when tweaking thresholds.
 */

import type {
  DecisionLabel,
  ExecutiveSummary,
  OutlookLabel,
  QualityLevel,
  ResearchReport,
  RiskLevel,
} from "@/types/schemas";

const CONFIDENCE_HIGH = 0.65;
const CONFIDENCE_MEDIUM = 0.35;
const MOVE_PROB_HIGH = 0.4;
const MOVE_PROB_MEDIUM = 0.2;
const VOLUME_EXC = 1.5;
const VOLUME_GOOD = 1.0;
const VOLUME_FAIR = 0.6;
const ER_CONF_HIGH = 0.7;
const ER_CONF_LOW = 0.4;

const RANK: Record<RiskLevel, number> = { Low: 0, Medium: 1, High: 2 };

function toRisk(label: unknown): RiskLevel {
  if (typeof label !== "string") return "Medium";
  const u = label.trim().toUpperCase();
  if (u === "LOW") return "Low";
  if (u === "HIGH") return "High";
  return "Medium";
}

function moveLabel(p: number | null | undefined): RiskLevel {
  if (p == null) return "Medium";
  if (p >= MOVE_PROB_HIGH) return "High";
  if (p >= MOVE_PROB_MEDIUM) return "Medium";
  return "Low";
}

function decisionFromCreditSafety(
  label: unknown,
  score: number | null | undefined,
): DecisionLabel {
  if (typeof label === "string") {
    const u = label.trim().toUpperCase();
    if (u === "SAFE" || u === "ENTER") return "Enter";
    if (u === "UNSAFE" || u === "AVOID") return "Avoid";
    if (u === "CAUTION" || u === "WATCH" || u === "WAIT") return "Wait";
  }
  if (score == null) return "Wait";
  if (score >= 7) return "Enter";
  if (score >= 4) return "Wait";
  return "Avoid";
}

function outlookFromConsensus(
  stance: string | null | undefined,
  vol: string | null | undefined,
  fallbackBias: string | null | undefined,
): OutlookLabel {
  const regime = (vol ?? "").trim().toLowerCase();
  if (regime === "high") return "Volatile";
  const s = (stance ?? fallbackBias ?? "").trim().toLowerCase();
  if (s.includes("bullish")) return "Bullish";
  if (s.includes("bearish")) return "Bearish";
  if (s.includes("mixed")) return "Choppy";
  if (s.includes("neutral")) return "Sideways";
  return "Sideways";
}

function confidenceLevel(
  agg: number | null | undefined,
  fallback: number | null | undefined,
): RiskLevel {
  const v = agg ?? fallback;
  if (v == null) return "Medium";
  if (v >= CONFIDENCE_HIGH) return "High";
  if (v >= CONFIDENCE_MEDIUM) return "Medium";
  return "Low";
}

function riskCombined(creditSafetyLabel: unknown, uncertainty: unknown): RiskLevel {
  const cs = (typeof creditSafetyLabel === "string" ? creditSafetyLabel : "")
    .trim()
    .toUpperCase();
  const csRisk: RiskLevel =
    cs === "UNSAFE" ? "High" : cs === "CAUTION" ? "Medium" : cs === "SAFE" ? "Low" : "Medium";
  const u = (typeof uncertainty === "string" ? uncertainty : "").trim().toLowerCase();
  const unRisk: RiskLevel =
    u === "high" ? "High" : u === "medium" ? "Medium" : u === "low" ? "Low" : csRisk;
  return RANK[csRisk] >= RANK[unRisk] ? csRisk : unRisk;
}

function ivQuality(
  vol: string | null | undefined,
  conf: number | null | undefined,
  source: string | null | undefined,
): QualityLevel {
  const regime = (vol ?? "medium").trim().toLowerCase();
  const c = conf ?? 0.5;
  if ((source ?? "").toLowerCase() === "live_iv") {
    return c >= ER_CONF_HIGH ? "Good" : "Good";
  }
  if (regime === "high") {
    if (c >= ER_CONF_HIGH) return "Good";
    if (c >= ER_CONF_LOW) return "Average";
    return "Poor";
  }
  if (regime === "low") {
    if (c >= ER_CONF_HIGH) return "Good";
    if (c >= ER_CONF_LOW) return "Good";
    return "Average";
  }
  if (c >= ER_CONF_HIGH) return "Good";
  if (c >= ER_CONF_LOW) return "Average";
  return "Poor";
}

function liquidity(volRatio: number | null | undefined): QualityLevel {
  if (volRatio == null) return "Average";
  if (volRatio >= VOLUME_EXC) return "Good";
  if (volRatio >= VOLUME_GOOD) return "Good";
  if (volRatio >= VOLUME_FAIR) return "Average";
  return "Poor";
}

function composeSummary(
  consensusSummary: string | null | undefined,
  dominantNarrative: string | null | undefined,
  whatHappened: string | null | undefined,
  fallback: string,
  maxChars = 400,
): string {
  const parts: string[] = [];
  const seen = new Set<string>();
  const add = (text: unknown) => {
    if (typeof text !== "string") return;
    const clean = text.replace(/\s+/g, " ").trim();
    if (!clean) return;
    const first = clean.split(".", 1)[0]!.trim();
    if (!first) return;
    const key = first.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    parts.push(first.replace(/\.$/, "") + ".");
  };
  add(consensusSummary);
  add(dominantNarrative);
  add(whatHappened);
  if (parts.length === 0) parts.push(fallback);
  const composed = parts.slice(0, 4).join(" ");
  if (composed.length <= maxChars) return composed;
  const cut = composed.slice(0, maxChars).split(" ");
  cut.pop();
  return cut.join(" ").replace(/[,;:\-\s]+$/, "") + "…";
}

/**
 * Derive an `ExecutiveSummary` from a full report. Returns null when there
 * is genuinely nothing usable to display (e.g. completely empty report).
 */
export function extractDashboardSummary(report: ResearchReport | null | undefined): ExecutiveSummary | null {
  if (!report) return null;
  const opts = report.options_intelligence;
  const meta = report._pipeline_meta;
  const snap = meta?.price_snapshot;
  // We need at least an options_intelligence block for a meaningful summary;
  // older reports without it should land back in IDLE.
  const cs = opts?.credit_safety;
  if (!opts || !cs) return null;

  const deliberation = (report as { deliberation_layer?: { consensus?: { consensus?: string; uncertainty?: string; debate_summary?: string; calibration?: { confidence_aggregate?: number } } } }).deliberation_layer;
  const consensus = deliberation?.consensus;
  const calibration = consensus?.calibration;

  const decision = decisionFromCreditSafety(cs.label, cs.score);
  const outlook = outlookFromConsensus(
    consensus?.consensus,
    meta?.volatility_regime,
    report.price_prediction?.bias,
  );
  const confidence = confidenceLevel(
    calibration?.confidence_aggregate,
    report.price_prediction?.confidence,
  );
  const risk = riskCombined(cs.label, consensus?.uncertainty);
  const plus = moveLabel(opts.move_probabilities.p_up_2pct);
  const minus = moveLabel(opts.move_probabilities.p_dn_2pct);

  const summaryText = composeSummary(
    consensus?.debate_summary,
    report.dominant_narrative,
    report.what_happened,
    `Decision ${decision} based on credit safety ${cs.score.toFixed(1)}/10.`,
  );

  return {
    decision,
    credit_safety_score: Number(cs.score.toFixed(2)),
    outlook,
    risk,
    confidence,
    plus_move_risk: plus,
    minus_move_risk: minus,
    expected_range: {
      low: Number(opts.expected_range.low.toFixed(2)),
      high: Number(opts.expected_range.high.toFixed(2)),
    },
    event_risk: toRisk(opts.event_risk.label),
    iv_quality: ivQuality(meta?.volatility_regime, opts.expected_range.confidence, opts.source),
    liquidity: liquidity(snap?.volume_vs_avg ?? null),
    pin_risk: toRisk(opts.pin_risk.label),
    summary: summaryText,
    summary_version: calibration || consensus?.debate_summary ? 2 : 1,
    derived_at: new Date().toISOString(),
  };
}
