"""Deterministic ``ExecutiveSummary`` extractor.

The grid card is a pure projection of an already-completed research report:

* options_intelligence (deterministic options math from PR-A1)
* deliberation_layer.consensus (multi-LLM DIL)
* _pipeline_meta.price_snapshot (volume/liquidity)
* dominant_narrative / what_happened (Claude synthesis)

The extractor never calls an LLM and never blocks; it gracefully fills
sensible neutrals when fields are missing so the card always renders.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from app.services.summary.schemas import (
    DecisionLabel,
    ExecutiveSummary,
    ExpectedRangeShort,
    OutlookLabel,
    QualityLevel,
    RiskLevel,
)

log = structlog.get_logger(__name__)

# --- Threshold constants (tunable in one place) -----------------------------

CONFIDENCE_HIGH = 0.65
CONFIDENCE_MEDIUM = 0.35

PRED_CONFIDENCE_HIGH = 0.65
PRED_CONFIDENCE_MEDIUM = 0.35

MOVE_PROB_HIGH = 0.40
MOVE_PROB_MEDIUM = 0.20

VOLUME_VS_AVG_EXCELLENT = 1.50
VOLUME_VS_AVG_GOOD = 1.00
VOLUME_VS_AVG_FAIR = 0.60

EXPECTED_RANGE_CONF_HIGH = 0.70
EXPECTED_RANGE_CONF_LOW = 0.40

SUMMARY_MAX_CHARS = 400


# --- Helpers ---------------------------------------------------------------


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalise_risk(label: Any) -> RiskLevel:
    if not isinstance(label, str):
        return "Medium"
    upper = label.strip().upper()
    if upper in {"LOW", "L"}:
        return "Low"
    if upper in {"HIGH", "H"}:
        return "High"
    return "Medium"


def _move_prob_to_label(prob: float | None) -> RiskLevel:
    if prob is None:
        return "Medium"
    if prob >= MOVE_PROB_HIGH:
        return "High"
    if prob >= MOVE_PROB_MEDIUM:
        return "Medium"
    return "Low"


def _decision_from_credit_safety(label: Any, score: float | None) -> DecisionLabel:
    if isinstance(label, str):
        upper = label.strip().upper()
        if upper == "SAFE":
            return "SAFE"
        if upper == "UNSAFE":
            return "AVOID"
        if upper == "CAUTION":
            return "WATCH"
    if score is None:
        return "WATCH"
    if score >= 7.0:
        return "SAFE"
    if score >= 4.0:
        return "WATCH"
    return "AVOID"


def _outlook_from_consensus(
    consensus_stance: str | None,
    vol_regime: str | None,
    fallback_bias: str | None,
) -> OutlookLabel:
    """Map DIL consensus stance + vol regime → outlook bucket.

    Volatile wins when realized vol is high regardless of stance, mirroring how
    a credit-collection trader would read the tape.
    """
    regime = (vol_regime or "").strip().lower()
    stance_raw = (consensus_stance or fallback_bias or "").strip().lower()

    # If volatility is the dominant story, surface it first.
    if regime == "high":
        return "Volatile"

    if stance_raw:
        if "bullish" in stance_raw:
            return "Bullish"
        if "bearish" in stance_raw:
            return "Bearish"
        if "mixed" in stance_raw:
            return "Mixed"
        if "neutral" in stance_raw:
            return "Sideways"

    return "Sideways"


def _confidence_from_calibration(
    confidence_aggregate: float | None,
    fallback_pred_confidence: float | None,
) -> RiskLevel:
    if confidence_aggregate is not None:
        if confidence_aggregate >= CONFIDENCE_HIGH:
            return "High"
        if confidence_aggregate >= CONFIDENCE_MEDIUM:
            return "Medium"
        return "Low"
    if fallback_pred_confidence is not None:
        if fallback_pred_confidence >= PRED_CONFIDENCE_HIGH:
            return "High"
        if fallback_pred_confidence >= PRED_CONFIDENCE_MEDIUM:
            return "Medium"
        return "Low"
    return "Medium"


def _risk_from_blocks(
    credit_safety_label: Any,
    uncertainty: Any,
) -> RiskLevel:
    """Higher of (credit_safety risk inversion, DIL uncertainty)."""
    cs = (credit_safety_label or "").strip().upper() if isinstance(credit_safety_label, str) else ""
    if cs == "UNSAFE":
        cs_risk: RiskLevel = "High"
    elif cs == "CAUTION":
        cs_risk = "Medium"
    elif cs == "SAFE":
        cs_risk = "Low"
    else:
        cs_risk = "Medium"

    unc = (uncertainty or "").strip().lower() if isinstance(uncertainty, str) else ""
    if unc == "high":
        unc_risk: RiskLevel = "High"
    elif unc == "medium":
        unc_risk = "Medium"
    elif unc == "low":
        unc_risk = "Low"
    else:
        unc_risk = cs_risk

    rank = {"Low": 0, "Medium": 1, "High": 2}
    return cs_risk if rank[cs_risk] >= rank[unc_risk] else unc_risk


def _iv_quality(
    vol_regime: str | None,
    expected_range_confidence: float | None,
    options_source: str | None,
) -> QualityLevel:
    """Approximate IV-quality grade from realized vol + range-model confidence.

    * Live IV from a chain provider is always at least Good (model has real
      market input rather than a backward-looking estimator).
    * Otherwise: high vol with low confidence is Poor; high vol with high
      confidence is Good; medium/low vol with high confidence is Excellent.
    """
    regime = (vol_regime or "medium").strip().lower()
    conf = expected_range_confidence if expected_range_confidence is not None else 0.5
    source = (options_source or "").strip().lower()

    if source == "live_iv":
        if conf >= EXPECTED_RANGE_CONF_HIGH:
            return "Excellent"
        return "Good"

    if regime == "high":
        if conf >= EXPECTED_RANGE_CONF_HIGH:
            return "Good"
        if conf >= EXPECTED_RANGE_CONF_LOW:
            return "Fair"
        return "Poor"
    if regime == "low":
        if conf >= EXPECTED_RANGE_CONF_HIGH:
            return "Excellent"
        if conf >= EXPECTED_RANGE_CONF_LOW:
            return "Good"
        return "Fair"
    # medium
    if conf >= EXPECTED_RANGE_CONF_HIGH:
        return "Good"
    if conf >= EXPECTED_RANGE_CONF_LOW:
        return "Fair"
    return "Poor"


def _liquidity_from_volume(volume_vs_avg: float | None) -> QualityLevel:
    if volume_vs_avg is None:
        return "Fair"
    if volume_vs_avg >= VOLUME_VS_AVG_EXCELLENT:
        return "Excellent"
    if volume_vs_avg >= VOLUME_VS_AVG_GOOD:
        return "Good"
    if volume_vs_avg >= VOLUME_VS_AVG_FAIR:
        return "Fair"
    return "Poor"


def _trim_sentence(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut.rstrip(",;:- ") + "…"


def _compose_summary(
    consensus_summary: str | None,
    dominant_narrative: str | None,
    what_happened: str | None,
    fallback_decision_line: str,
) -> str:
    """Build a 3-4 sentence trader summary under SUMMARY_MAX_CHARS chars."""
    parts: list[str] = []
    seen: set[str] = set()

    def add(text: str | None) -> None:
        if not text:
            return
        clean = " ".join(str(text).split()).strip()
        if not clean:
            return
        first = clean.split(".", 1)[0].strip()
        if not first:
            return
        key = first.lower()
        if key in seen:
            return
        seen.add(key)
        parts.append(first.rstrip(".") + ".")

    add(consensus_summary)
    add(dominant_narrative)
    add(what_happened)
    if not parts:
        parts.append(fallback_decision_line)

    composed = " ".join(parts[:4])
    return _trim_sentence(composed, SUMMARY_MAX_CHARS)


# --- Public API ------------------------------------------------------------


def extract_executive_summary(report: dict[str, Any]) -> ExecutiveSummary:
    """Project a finished research report into the dashboard executive summary.

    Args:
        report: full ``report_json`` dict (must include ``options_intelligence``
            for non-degenerate output; missing fields fall back to neutrals).

    Returns:
        ``ExecutiveSummary`` Pydantic model. Always returns a valid model —
        callers can ``.model_dump()`` and persist directly.
    """
    options = report.get("options_intelligence") or {}
    deliberation = report.get("deliberation_layer") or {}
    consensus = deliberation.get("consensus") or {}
    calibration = consensus.get("calibration") or {}
    meta = report.get("_pipeline_meta") or {}
    price_snapshot = meta.get("price_snapshot") or {}
    price_prediction = report.get("price_prediction") or {}

    credit_safety = options.get("credit_safety") or {}
    expected_range = options.get("expected_range") or {}
    move_probabilities = options.get("move_probabilities") or {}
    pin_risk = options.get("pin_risk") or {}
    event_risk = options.get("event_risk") or {}

    cs_score = _safe_float(credit_safety.get("score"))

    council_layer = deliberation.get("council_layer") or {}
    council_consensus = council_layer.get("consensus") or {}
    council_decision_raw = council_consensus.get("decision")
    mapped_decision = deliberation.get("mapped_decision")

    if mapped_decision in ("SAFE", "WATCH", "AVOID"):
        decision: DecisionLabel = mapped_decision  # type: ignore[assignment]
    else:
        decision = _decision_from_credit_safety(credit_safety.get("label"), cs_score)

    council_summary = council_consensus.get("debate_summary")
    outlook = _outlook_from_consensus(
        consensus_stance=consensus.get("consensus"),
        vol_regime=meta.get("volatility_regime"),
        fallback_bias=price_prediction.get("bias"),
    )

    confidence_value = _safe_float(calibration.get("confidence_aggregate"))
    if council_consensus.get("confidence") is not None:
        confidence_value = _safe_float(council_consensus.get("confidence"))
    fallback_pred_conf = _safe_float(price_prediction.get("confidence"))
    confidence = _confidence_from_calibration(confidence_value, fallback_pred_conf)

    risk = _risk_from_blocks(credit_safety.get("label"), consensus.get("uncertainty"))

    plus_prob = _safe_float(move_probabilities.get("p_up_2pct"))
    minus_prob = _safe_float(move_probabilities.get("p_dn_2pct"))
    plus_move = _move_prob_to_label(plus_prob)
    minus_move = _move_prob_to_label(minus_prob)

    er_low = _safe_float(expected_range.get("low")) or 0.0
    er_high = _safe_float(expected_range.get("high")) or 0.0
    er_conf = _safe_float(expected_range.get("confidence"))

    iv_quality = _iv_quality(
        vol_regime=meta.get("volatility_regime"),
        expected_range_confidence=er_conf,
        options_source=options.get("source"),
    )

    liquidity = _liquidity_from_volume(_safe_float(price_snapshot.get("volume_vs_avg")))

    summary = _compose_summary(
        consensus_summary=council_summary or consensus.get("debate_summary"),
        dominant_narrative=report.get("dominant_narrative"),
        what_happened=report.get("what_happened"),
        fallback_decision_line=(
            f"Decision {decision} based on credit safety "
            f"{cs_score:.1f}/10."
            if cs_score is not None
            else f"Decision {decision}."
        ),
    )

    summary_version = 2 if (calibration or council_consensus or consensus.get("debate_summary")) else 1

    return ExecutiveSummary(
        decision=decision,
        credit_safety_score=round(cs_score if cs_score is not None else 0.0, 2),
        outlook=outlook,
        risk=risk,
        confidence=confidence,
        plus_move_risk=plus_move,
        minus_move_risk=minus_move,
        expected_range=ExpectedRangeShort(low=round(er_low, 2), high=round(er_high, 2)),
        event_risk=_normalise_risk(event_risk.get("label")),
        iv_quality=iv_quality,
        liquidity=liquidity,
        pin_risk=_normalise_risk(pin_risk.get("label")),
        summary=summary,
        summary_version=summary_version,
        derived_at=datetime.now(UTC).isoformat(),
        council_decision_raw=council_decision_raw,
    )


__all__ = ["extract_executive_summary"]
