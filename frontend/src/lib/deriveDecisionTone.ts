/**
 * Tone helpers for the grid card. Centralised so every chip / pill / badge
 * speaks the same color-vocabulary across the app.
 *
 *   Enter / Low / Good / Bullish        -> "ok"     (emerald)
 *   Wait / Medium / Average / Choppy    -> "warn"   (amber)
 *   Avoid / High / Poor / Bearish       -> "bad"    (rose)
 *   Sideways / Volatile                 -> "neutral"
 *
 * Numeric scores use the credit-safety convention (>=7 ok, >=4 warn, <4 bad).
 *
 * Legacy values from un-refreshed dashboard rows (``SAFE``/``WATCH``/
 * ``Cheap``/``Extreme``/...) are tolerated and mapped onto the new
 * vocabulary so the grid keeps rendering during the rollout window.
 */

import type {
  DecisionLabel,
  QualityLevel,
  RiskLevel,
} from "@/types/schemas";

export type Tone = "ok" | "warn" | "bad" | "neutral";

const NORMALISED_OK = new Set([
  "ENTER",
  "SAFE",
  "LOW",
  "GOOD",
  "EXCELLENT",
  "BULLISH",
]);
const NORMALISED_WARN = new Set([
  "WAIT",
  "WATCH",
  "MEDIUM",
  "AVERAGE",
  "FAIR",
  "CHOPPY",
  "MIXED",
  "ELEVATED",
]);
const NORMALISED_BAD = new Set([
  "AVOID",
  "HIGH",
  "EXTREME",
  "POOR",
  "CHEAP",
  "RICH",
  "BEARISH",
]);

export function toneFor(label: string | null | undefined): Tone {
  if (!label) return "neutral";
  const upper = label.trim().toUpperCase();
  if (NORMALISED_OK.has(upper)) return "ok";
  if (NORMALISED_WARN.has(upper)) return "warn";
  if (NORMALISED_BAD.has(upper)) return "bad";
  return "neutral";
}

export function toneForScore(score: number | null | undefined): Tone {
  if (score == null || Number.isNaN(score)) return "neutral";
  if (score >= 7) return "ok";
  if (score >= 4) return "warn";
  return "bad";
}

/** Today's outlook is bullish/bearish/sideways/choppy. */
export function todayOutlookTone(
  outlook: string | null | undefined,
): Tone {
  if (!outlook) return "neutral";
  switch (outlook) {
    case "Bullish":
      return "ok";
    case "Bearish":
      return "bad";
    case "Choppy":
      return "warn";
    case "Sideways":
      return "neutral";
    default:
      return "neutral";
  }
}

/** Next 2-3 day outlook is bullish/bearish/sideways/volatile. */
export function nextOutlookTone(
  outlook: string | null | undefined,
): Tone {
  if (!outlook) return "neutral";
  switch (outlook) {
    case "Bullish":
      return "ok";
    case "Bearish":
      return "bad";
    case "Volatile":
      return "warn";
    case "Sideways":
      return "neutral";
    default:
      return "neutral";
  }
}

/**
 * Back-compat shim — older callers used ``outlookTone`` for both
 * today's and the next-3-day outlooks. Default to next-3-day tone
 * because ``Volatile`` lives on that scale.
 */
export function outlookTone(
  outlook: string | null | undefined,
): Tone {
  return nextOutlookTone(outlook);
}

/** IV quality + liquidity share the Poor / Average / Good palette. */
export function qualityTone(
  q: "Poor" | "Average" | "Good" | string | null | undefined,
): Tone {
  if (!q) return "neutral";
  switch (q) {
    case "Good":
      return "ok";
    case "Average":
      return "warn";
    case "Poor":
      return "bad";
    default:
      return toneFor(q);
  }
}

/** Back-compat: previously IV quality had its own Cheap/Fair/... scale. */
export function ivQualityTone(
  iv: string | null | undefined,
): Tone {
  return qualityTone(iv);
}

export const RISK_LEVELS: RiskLevel[] = ["Low", "Medium", "High"];
export const QUALITY_LEVELS: QualityLevel[] = ["Poor", "Average", "Good"];
export const DECISION_ORDER: DecisionLabel[] = ["Enter", "Wait", "Avoid"];

/** Map a tone to the Tailwind class strings used across grid badges. */
export function toneBadgeClass(tone: Tone): string {
  switch (tone) {
    case "ok":
      return "border-emerald-600/35 bg-emerald-50 text-emerald-800 dark:border-emerald-500/40 dark:bg-emerald-500/15 dark:text-emerald-200";
    case "warn":
      return "border-amber-600/35 bg-amber-50 text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/15 dark:text-amber-100";
    case "bad":
      return "border-rose-600/35 bg-rose-50 text-rose-800 dark:border-rose-500/40 dark:bg-rose-500/15 dark:text-rose-200";
    case "neutral":
    default:
      return "border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-500/30 dark:bg-slate-500/10 dark:text-slate-200";
  }
}

export function toneTextClass(tone: Tone): string {
  switch (tone) {
    case "ok":
      return "text-emerald-700 dark:text-emerald-300";
    case "warn":
      return "text-amber-800 dark:text-amber-200";
    case "bad":
      return "text-rose-700 dark:text-rose-300";
    case "neutral":
    default:
      return "text-slate-600 dark:text-slate-200";
  }
}

/** Convert risk level to a 0..1 fill for the movement-risk progress bar. */
export function riskFillPct(level: RiskLevel | null | undefined): number {
  if (!level) return 0;
  if (level === "Low") return 0.2;
  if (level === "Medium") return 0.55;
  return 0.9;
}
