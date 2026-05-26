"""Deterministic Reverse BWB card projector.

Used as a fallback when the Reverse BWB Assessment Team can't reach
quorum (insufficient providers, all members failed). Computes every
card field from the deterministic options-intelligence block and a
handful of report-meta signals — no LLM call.

The function intentionally produces an ``AssessmentConsensus`` so the
rest of the pipeline (council, save_snapshot, etc.) does not need to
know whether the body came from the LLM panel or the deterministic
path.
"""

from __future__ import annotations

from typing import Any

from app.services.dashboard.schemas import (
    AssessmentConsensus,
    ChanceLabel,
    ExpectedRange,
    IvQualityLabel,
    LiquidityLabel,
    NextOutlook,
    RiskLevel,
    TodayOutlook,
)
from app.services.dashboard.watchlist import WATCHLIST_TIER_KEY_BY_SYMBOL
from app.services.options.expected_range import expected_range as compute_range


def _safe_get(d: Any, *keys: str, default: Any = None) -> Any:
    cur: Any = d
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def _bucket_chance(p: float | None) -> ChanceLabel:
    if p is None:
        return "Low"
    if p < 0.15:
        return "Low"
    if p < 0.30:
        return "Medium"
    return "High"


def _bucket_risk_from_label(label: Any) -> RiskLevel:
    if not isinstance(label, str):
        return "Medium"
    upper = label.strip().upper()
    if upper in ("LOW",):
        return "Low"
    if upper in ("MEDIUM", "MED"):
        return "Medium"
    if upper in ("HIGH", "EXTREME"):
        return "High"
    return "Medium"


def _confidence(report: dict[str, Any], oi: dict[str, Any]) -> str:
    articles = report.get("articles_analyzed") or 0
    quality_note = (report.get("data_quality_note") or "").lower()
    source = oi.get("source")
    if articles < 5 or "limited" in quality_note or "mock" in quality_note:
        return "Low"
    if source == "live_iv":
        return "High"
    return "Medium"


def _today_outlook(report: dict[str, Any], vol_regime: str) -> TodayOutlook:
    pp = report.get("price_prediction") or {}
    bias = str(pp.get("bias") or "").lower()
    regime = (vol_regime or "").lower()
    if bias.startswith("bull"):
        return "Bullish"
    if bias.startswith("bear"):
        return "Bearish"
    if regime in ("high", "elevated"):
        return "Choppy"
    return "Sideways"


def _next_outlook(report: dict[str, Any], vol_regime: str) -> NextOutlook:
    pp = report.get("price_prediction") or {}
    bias = str(pp.get("bias") or "").lower()
    regime = (vol_regime or "").lower()
    if bias.startswith("bull"):
        return "Bullish"
    if bias.startswith("bear"):
        return "Bearish"
    if regime in ("high", "elevated"):
        return "Volatile"
    return "Sideways"


def _iv_quality(sigma_pct: float | None) -> IvQualityLabel:
    if sigma_pct is None:
        return "Average"
    if sigma_pct < 1.0:
        return "Poor"
    if sigma_pct < 2.5:
        return "Average"
    return "Good"


def _liquidity_tier(ticker: str) -> LiquidityLabel:
    tier = WATCHLIST_TIER_KEY_BY_SYMBOL.get(ticker.upper(), "tier-3")
    if tier == "tier-1":
        return "Good"
    if tier == "tier-2":
        return "Good"
    return "Average"


def _danger_zone(oi: dict[str, Any], last_close: float | None) -> str:
    body = oi.get("body_danger") or {}
    lo = body.get("short_body_lo")
    hi = body.get("short_body_hi")
    if lo is None or hi is None or last_close is None:
        return "body width unavailable"
    half_width = max(float(hi) - float(lo), 0.0) / 2.0
    pct = round((half_width / float(last_close)) * 100.0, 1) if last_close else 0.0
    label = str(body.get("label") or "").lower()
    suffix = " (wide)" if label == "high" else ""
    return f"+/-{pct}% around ${round(float(last_close), 2)}{suffix}"


def project_assessment_consensus(
    ticker: str,
    report: dict[str, Any],
) -> AssessmentConsensus:
    """Deterministic projection from the report → AssessmentConsensus.

    Always returns a valid ``AssessmentConsensus`` even when the
    options-intelligence block is missing; in that case the card body
    defaults to the most conservative bucket per field.
    """

    oi = report.get("options_intelligence") or {}
    credit = oi.get("credit_safety") or {}
    expected = oi.get("expected_range") or {}
    move_probs = oi.get("move_probabilities") or {}
    pin = oi.get("pin_risk") or {}
    event = oi.get("event_risk") or {}

    last_close = (
        _safe_get(oi, "last_close")
        or _safe_get(report, "_pipeline_meta", "price_snapshot", "last_close")
        or _safe_get(report, "price_prediction", "last_close")
    )
    daily_vol = oi.get("daily_vol_pct") or 1.0
    vol_regime = (
        _safe_get(report, "_pipeline_meta", "volatility_regime")
        or _safe_get(report, "price_prediction", "volatility_regime")
        or "medium"
    )

    credit_score = float(credit.get("score") or 0.0)
    if credit_score >= 7.0:
        risk: RiskLevel = "Low"
    elif credit_score >= 4.0:
        risk = "Medium"
    else:
        risk = "High"

    confidence = _confidence(report, oi)

    # 1-day expected range
    if last_close is not None and daily_vol:
        today_band = compute_range(
            last_close=float(last_close),
            daily_vol_pct=float(daily_vol),
            horizon_days=1,
        )
        today_range = ExpectedRange(
            low=today_band["low"], high=today_band["high"]
        )
        next_band = compute_range(
            last_close=float(last_close),
            daily_vol_pct=float(daily_vol),
            horizon_days=3,
        )
        next_range = ExpectedRange(low=next_band["low"], high=next_band["high"])
    else:
        low = expected.get("low") or 0.0
        high = expected.get("high") or 0.0
        today_range = ExpectedRange(low=float(low), high=float(high))
        next_range = ExpectedRange(low=float(low), high=float(high))

    chance_up = _bucket_chance(move_probs.get("p_up_3pct"))
    chance_down = _bucket_chance(move_probs.get("p_dn_3pct"))

    danger_zone = _danger_zone(oi, last_close)
    pin_risk = _bucket_risk_from_label(pin.get("label"))
    event_risk = _bucket_risk_from_label(event.get("label"))
    iv_quality = _iv_quality(expected.get("sigma_pct"))
    liquidity = _liquidity_tier(ticker)

    today_outlook = _today_outlook(report, str(vol_regime))
    next_3d_outlook = _next_outlook(report, str(vol_regime))

    summary_sentences = _dynamics_sentences(
        ticker=ticker,
        risk=risk,
        chance_up=chance_up,
        chance_down=chance_down,
        pin_risk=pin_risk,
        event_risk=event_risk,
        iv_quality=iv_quality,
        today_outlook=today_outlook,
        next_outlook=next_3d_outlook,
    )

    return AssessmentConsensus(
        credit_safety_score=round(credit_score, 1),
        risk=risk,
        confidence=confidence,  # type: ignore[arg-type]
        today_outlook=today_outlook,
        next_3d_outlook=next_3d_outlook,
        chance_up_2_3_pct=chance_up,
        chance_down_2_3_pct=chance_down,
        expected_range_today=today_range,
        expected_range_next_3d=next_range,
        danger_zone=danger_zone,
        pin_risk=pin_risk,
        event_risk=event_risk,
        iv_quality=iv_quality,
        liquidity=liquidity,
        actual_dynamics_summary=summary_sentences,
    )


def _dynamics_sentences(
    *,
    ticker: str,
    risk: str,
    chance_up: str,
    chance_down: str,
    pin_risk: str,
    event_risk: str,
    iv_quality: str,
    today_outlook: str,
    next_outlook: str,
) -> list[str]:
    """Deterministic fallback narrative — no generic advice."""

    # 1. Calm vs move framing.
    move_risk = "Low"
    if chance_up == "High" or chance_down == "High":
        move_risk = "High"
    elif chance_up == "Medium" or chance_down == "Medium":
        move_risk = "Medium"
    if move_risk == "High":
        calm = f"{ticker} is likely to make a 2-3% move within the DTE window."
    elif move_risk == "Medium":
        calm = f"{ticker} has a meaningful chance of a 2-3% move but could also stay calm."
    else:
        calm = f"{ticker} is more likely to stay inside the expected range than to make a 2-3% move."

    # 2. Directional bias.
    if chance_up == chance_down:
        bias = "Up and down move probabilities are roughly balanced."
    elif _rank_chance(chance_up) > _rank_chance(chance_down):
        bias = "Upside risk slightly outweighs downside on the chance buckets."
    else:
        bias = "Downside risk slightly outweighs upside on the chance buckets."

    # 3. Body safety.
    if pin_risk == "High" or risk == "High":
        body = "The short body sits inside a wider danger zone and should be treated as risky."
    elif pin_risk == "Medium":
        body = "The short body has moderate pin exposure but no flashing red flags."
    else:
        body = "The short body sits outside the immediate danger zone and looks defensible."

    # 4. IV + event context.
    if event_risk == "High":
        catalyst = "Event risk is elevated — IV expansion around a known catalyst is a real possibility."
    elif iv_quality == "Good":
        catalyst = "Premium is attractive given the current realized vol, but watch for event-driven IV crush."
    elif iv_quality == "Poor":
        catalyst = "Premium is thin for a credit collector; expected-value is sensitive to even small moves."
    else:
        catalyst = "IV and event context are unremarkable; the trade lives or dies on the directional read."

    sentences = [calm, bias, body, catalyst]
    # AssessmentConsensus accepts 3 or 4; keep at 4 unless any line is empty.
    return [s for s in sentences if s]


_CHANCE_RANK = {"Low": 0, "Medium": 1, "High": 2}


def _rank_chance(c: str) -> int:
    return _CHANCE_RANK.get(c, 0)


def fallback_decision_from_consensus(consensus: AssessmentConsensus) -> str:
    """Deterministic Enter/Wait/Avoid when the Decision Council can't run."""

    score = consensus.credit_safety_score
    if score >= 7.0 and consensus.risk == "Low":
        return "Enter"
    if score < 4.0 or consensus.risk == "High":
        return "Avoid"
    return "Wait"
