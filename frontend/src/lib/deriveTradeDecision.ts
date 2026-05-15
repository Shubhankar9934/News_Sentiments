import { getArticleEvidence, getPipelineMeta, getPriceSnapshot } from "@/lib/pipelineMeta";
import type { ResearchReport } from "@/types/schemas";

function tierFromSourceName(source: string): string {
  const s = source.toLowerCase();
  if (/reuters|bloomberg|wsj|financial times|sec\.gov|filing/.test(s)) return "Tier 1";
  if (/cnbc|ft\.com|marketwatch|investing\.com|ap news/.test(s)) return "Tier 2";
  if (/reddit|twitter|x\.com|stocktwits/.test(s)) return "Social";
  if (/yahoo|seeking alpha|benzinga|motley fool|fool\.com/.test(s)) return "Tier 3";
  return "Tier 2";
}

export type NewsStrength = "WEAK" | "MODERATE" | "STRONG";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";
export type TradeQuality = "A+" | "A" | "A-" | "B+" | "B" | "C" | "NO TRADE";

export type DerivedTradingView = {
  signal: string;
  signalConfidencePct: number;
  newsStrength: NewsStrength;
  riskLevel: RiskLevel;
  tradeQuality: TradeQuality;
  noTrade: boolean;
  noTradeReason: string | null;
  momentumLabel: string;
  institutionalTone: string;
  retailTone: string;
  alignment: {
    newsBias: string;
    priceConfirmation: "YES" | "WEAK" | "NO" | "UNKNOWN";
    volumeConfirmation: "YES" | "WEAK" | "NO" | "UNKNOWN";
    momentumConfirmation: "YES" | "WEAK" | "NO" | "UNKNOWN";
    conclusion: string;
  };
  contradictory: { show: boolean; bullets: string[] };
  whyImportant: string[];
  strategyBullets: string[];
  sectorNote: string;
  spyNote: string;
};

function newsStrengthFrom(report: ResearchReport): NewsStrength {
  const n = report.articles_analyzed ?? 0;
  const top = getPipelineMeta(report)?.top_impact_events ?? [];
  const avgImpact =
    top.length > 0 ? top.reduce((s, x) => s + (typeof x.impact === "number" ? x.impact : 0), 0) / top.length : 0;
  if (n >= 40 && avgImpact > 0.35) return "STRONG";
  if (n >= 15 || avgImpact > 0.25) return "MODERATE";
  return "WEAK";
}

function riskFrom(report: ResearchReport, vol: string): RiskLevel {
  const mixed = (report.overall_sentiment_label ?? "").toLowerCase().includes("mix");
  const regime = (report.price_prediction?.volatility_regime ?? vol).toLowerCase();
  if (mixed && regime === "high") return "HIGH";
  if (regime === "high") return "MEDIUM";
  if (mixed) return "MEDIUM";
  return regime === "low" ? "LOW" : "MEDIUM";
}

export function deriveTradingView(report: ResearchReport, ticker: string): DerivedTradingView {
  const meta = getPipelineMeta(report);
  const volRegime = (meta?.volatility_regime ?? report.price_prediction?.volatility_regime ?? "medium").toString();
  const pred = report.price_prediction;
  const bias = (pred?.bias ?? report.overall_sentiment_label ?? "Neutral").toString();
  const conf = typeof pred?.confidence === "number" ? pred.confidence : Math.round(Math.abs(report.overall_sentiment_score ?? 0) * 100);
  const newsStrength = newsStrengthFrom(report);
  const riskLevel = riskFrom(report, volRegime);

  const snap = getPriceSnapshot(report);
  const volVs = snap?.volume_vs_avg;
  const sessionChg = snap?.last_session_change_pct;

  const predBias = (pred?.bias ?? "").toLowerCase();
  const chgBase = pred?.change_pct_base;
  const bullishPred = predBias.includes("bull");
  const bearishPred = predBias.includes("bear");

  const contradictory: string[] = [];
  if (bullishPred && typeof chgBase === "number" && chgBase < -0.5) {
    contradictory.push("Model bias is bullish but expected session change is negative.");
  }
  if (bearishPred && typeof chgBase === "number" && chgBase > 0.5) {
    contradictory.push("Model bias is bearish but expected session change is positive.");
  }
  if (typeof sessionChg === "number" && sessionChg < 0 && (report.overall_sentiment_label ?? "").toLowerCase().includes("bull")) {
    contradictory.push("Bullish news skew but the last daily session printed red.");
  }
  if (typeof volVs === "number" && volVs < 0.85 && newsStrength === "STRONG") {
    contradictory.push("Strong headline flow vs. volume not confirming (below 20-day average).");
  }

  const mixed = (report.overall_sentiment_label ?? "").toLowerCase().includes("mix");
  const lowConf = conf < 48;
  const noTrade = mixed && lowConf && newsStrength !== "STRONG";
  const noTradeReason = noTrade ? "Mixed sentiment and low model confidence — stand aside unless your process invalidates this." : null;

  let tradeQuality: TradeQuality = "B";
  if (noTrade) tradeQuality = "NO TRADE";
  else if (conf >= 78 && newsStrength === "STRONG" && contradictory.length === 0) tradeQuality = "A-";
  else if (conf >= 85 && contradictory.length === 0) tradeQuality = "A";
  else if (conf >= 70) tradeQuality = "B+";
  else if (conf < 45) tradeQuality = "C";

  const tier1 = (report.source_reliability ?? []).filter((s) => (s.tier ?? tierFromSourceName(s.source)).includes("1"));
  const social = (report.source_reliability ?? []).filter((s) => (s.tier ?? "").toLowerCase().includes("social"));

  const instScore =
    tier1.length > 0
      ? tier1.reduce((a, s) => a + (s.reliability_score ?? 60), 0) / tier1.length
      : report.source_reliability?.length
        ? (report.source_reliability.reduce((a, s) => a + (s.reliability_score ?? 60), 0) ?? 0) /
          report.source_reliability.length
        : 60;

  let institutionalTone = "Balanced";
  if (instScore >= 75 && bias.toLowerCase().includes("bull")) institutionalTone = "Institutionally constructive";
  else if (instScore >= 75 && bias.toLowerCase().includes("bear")) institutionalTone = "Institutionally cautious";
  else if (instScore < 62) institutionalTone = "Thin Tier-1 confirmation";

  let retailTone = "Not enough social-tier sources in this window.";
  if (social.length > 0) {
    const avg = social.reduce((a, s) => a + (s.reliability_score ?? 50), 0) / social.length;
    retailTone = avg > 70 ? "Retail-heavy sources skew hot" : "Retail/social present but not dominant";
  }

  const retOnDay =
    getArticleEvidence(report)
      .map((a) => a.abnormal_return)
      .filter((x): x is number => typeof x === "number") ?? [];
  const avgAr = retOnDay.length ? retOnDay.reduce((a, b) => a + b, 0) / retOnDay.length : null;

  let priceConfirmation: DerivedTradingView["alignment"]["priceConfirmation"] = "UNKNOWN";
  if (typeof sessionChg === "number" && typeof avgAr === "number") {
    if (bias.toLowerCase().includes("bull") && sessionChg > 0 && avgAr > 0) priceConfirmation = "YES";
    else if (bias.toLowerCase().includes("bear") && sessionChg < 0 && avgAr < 0) priceConfirmation = "YES";
    else if (Math.abs(sessionChg) < 0.15) priceConfirmation = "WEAK";
    else priceConfirmation = "NO";
  } else if (typeof sessionChg === "number") {
    if (bias.toLowerCase().includes("bull") && sessionChg > 0.2) priceConfirmation = "YES";
    else if (bias.toLowerCase().includes("bear") && sessionChg < -0.2) priceConfirmation = "YES";
    else if (Math.abs(sessionChg) < 0.1) priceConfirmation = "WEAK";
    else priceConfirmation = "NO";
  }

  let volumeConfirmation: DerivedTradingView["alignment"]["volumeConfirmation"] = "UNKNOWN";
  if (typeof volVs === "number") {
    if (volVs >= 1.15) volumeConfirmation = "YES";
    else if (volVs >= 0.9) volumeConfirmation = "WEAK";
    else volumeConfirmation = "NO";
  }

  let momentumConfirmation: DerivedTradingView["alignment"]["momentumConfirmation"] = "UNKNOWN";
  if (volRegime.toLowerCase() === "high" && newsStrength === "STRONG") momentumConfirmation = "YES";
  else if (volRegime.toLowerCase() === "low" && newsStrength === "WEAK") momentumConfirmation = "WEAK";
  else if (volRegime.toLowerCase() === "high") momentumConfirmation = "WEAK";

  const alignParts = [priceConfirmation, volumeConfirmation, momentumConfirmation];
  const yesCt = alignParts.filter((x) => x === "YES").length;
  let conclusion = "Treat the tape as ambiguous until price confirms your scenario.";
  if (yesCt >= 2 && !bias.toLowerCase().includes("neutral")) {
    conclusion = "Narrative, liquidity, and recent session direction broadly line up.";
  } else if (priceConfirmation === "NO" && (report.overall_sentiment_label ?? "").toLowerCase().includes("bull")) {
    conclusion = "Bullish headlines but weak or conflicting session follow-through — fade FOMO.";
  }

  const whyImportant: string[] = [];
  whyImportant.push(
    `Desk scan for ${ticker.toUpperCase()} — ${meta?.after_dedupe ?? report.articles_analyzed ?? 0} unique articles in window.`
  );
  if (report.dominant_narrative) whyImportant.push(`Dominant narrative: ${report.dominant_narrative}`);
  const srcCt = new Set(getArticleEvidence(report).map((a) => a.source)).size;
  if (srcCt > 0) whyImportant.push(`Confirmed across ${srcCt} distinct outlets in the ingestion window.`);
  if (typeof volVs === "number" && volVs >= 1.2) whyImportant.push("Volume is elevated vs. its recent average — liquidity is validating attention.");
  if (tier1.length >= 2) whyImportant.push("Multiple Tier-1 / wire-level sources anchor the story.");

  let strategyBullets: string[] = [];
  if (noTrade) {
    strategyBullets = ["Avoid initiating new risk", "Journal headlines only — wait for cleaner edge", "If already positioned, tighten risk"];
  } else if (bias.toLowerCase().includes("bull")) {
    strategyBullets = ["Buy dips vs. defined intraday support if your timeframe allows", "Favor continuation after digestion, not blind chase", "Avoid fighting strength with naked shorts"];
  } else if (bias.toLowerCase().includes("bear")) {
    strategyBullets = ["Favor rallies into supply for risk reduction", "Avoid catching falling knives without a catalyst clock", "Respect elevated gap risk"];
  } else {
    strategyBullets = ["Range tools only — reduce size", "Wait for a break + hold before directional commitment", "News for context, not for impulse entries"];
  }

  const momentumLabel =
    volRegime.toLowerCase() === "high" ? "STRONG" : volRegime.toLowerCase() === "low" ? "QUIET" : "MODERATE";

  return {
    signal: bias,
    signalConfidencePct: Math.min(99, Math.max(0, conf)),
    newsStrength,
    riskLevel,
    tradeQuality,
    noTrade,
    noTradeReason,
    momentumLabel,
    institutionalTone,
    retailTone,
    alignment: {
      newsBias: bias,
      priceConfirmation,
      volumeConfirmation,
      momentumConfirmation,
      conclusion,
    },
    contradictory: { show: contradictory.length > 0, bullets: contradictory },
    whyImportant,
    strategyBullets,
    sectorNote: "Sector breadth not wired in this build — check your tape.",
    spyNote: "SPY correlation not wired in this build — confirm index context manually.",
  };
}

export function formatExpectedMove(report: ResearchReport): string {
  const p = report.price_prediction;
  if (!p) return "—";
  const lo = p.change_pct_low;
  const hi = p.change_pct_high;
  if (typeof lo === "number" && typeof hi === "number") {
    const a = Math.min(lo, hi);
    const b = Math.max(lo, hi);
    return `${a >= 0 ? "+" : ""}${a.toFixed(1)}% to ${b >= 0 ? "+" : ""}${b.toFixed(1)}%`;
  }
  return "—";
}

export function isTodayImportant(report: ResearchReport): { level: "HIGH" | "MEDIUM" | "LOW"; detail: string } {
  const ev = report.key_events?.length ?? 0;
  const n = report.articles_analyzed ?? 0;
  const hi = (report.key_events ?? []).filter((e) => (e.impact ?? "").toLowerCase() === "high").length;
  if (hi >= 2 || n >= 45) return { level: "HIGH", detail: "Dense high-impact headline flow — treat today as eventful." };
  if (ev >= 3 || n >= 20) return { level: "MEDIUM", detail: "Meaningful drivers present — be selective, not absent." };
  return { level: "LOW", detail: "Quiet news regime relative to this scan — edge may be elsewhere." };
}
