"""Market regime classifier — deterministic, no LLM."""

from __future__ import annotations

from typing import Any


def build_regime_context(
    *,
    volatility_regime: str | None,
    sentiment: dict[str, Any],
    key_events: list[dict[str, Any]],
    options_intelligence: dict[str, Any] | None,
    news_momentum: dict[str, Any] | None,
) -> dict[str, Any]:
    vol = (volatility_regime or "medium").lower()
    score_label = (sentiment.get("overall_sentiment_label") or "Neutral").lower()
    momentum = (news_momentum or {}).get("label", "neutral")

    macro_events = sum(
        1 for e in key_events if "macro" in str(e.get("event_type", "")).lower()
    )
    earnings_events = sum(
        1 for e in key_events if "earn" in str(e.get("event_type", "")).lower()
    )

    event_risk = (options_intelligence or {}).get("event_risk") or {}
    event_label = (event_risk.get("label") or "Low").lower()

    labels: list[str] = []
    if "bull" in score_label and vol != "high":
        labels.append("Risk-On")
    elif "bear" in score_label or vol == "high":
        labels.append("Risk-Off")
    if vol == "high":
        labels.append("Volatile")
    elif vol == "low":
        labels.append("Range Bound")
    if earnings_events >= 2 or event_label == "high":
        labels.append("Post Earnings")
    if macro_events >= 2:
        labels.append("Macro Week")
    if "accelerating" in momentum:
        labels.append("Trending")

    primary = labels[0] if labels else "Range Bound"
    return {
        "primary_regime": primary,
        "regime_tags": labels or ["Range Bound"],
        "volatility_regime": vol,
        "sentiment_skew": score_label,
        "macro_event_density": macro_events,
        "earnings_event_density": earnings_events,
        "event_risk_label": event_risk.get("label"),
    }
