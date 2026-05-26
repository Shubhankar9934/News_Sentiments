"""Credit Safety Score [0..10] for a Reverse-BWB style credit structure.

Inputs are already normalized 0..1 scores. Weights are kept in a single
dict so they can be tuned without code change and surfaced to the UI for
transparency.
"""

from __future__ import annotations

from typing import Literal

DEFAULT_WEIGHTS: dict[str, float] = {
    "prob_block": 0.35,
    "pin_risk": 0.20,
    "body_danger": 0.20,
    "event_risk": 0.15,
    "vol_regime": 0.10,
}

_VOL_SCORE: dict[str, float] = {"low": 0.85, "medium": 0.55, "high": 0.20, "unknown": 0.45}


def _label_from_score(score: float) -> Literal["SAFE", "CAUTION", "UNSAFE"]:
    if score >= 7.0:
        return "SAFE"
    if score >= 4.0:
        return "CAUTION"
    return "UNSAFE"


def credit_safety_score(
    prob_block: float,
    pin_risk: float,
    body_danger: float,
    event_risk: float,
    vol_regime: str | None,
    weights: dict[str, float] | None = None,
) -> dict[str, object]:
    """Combine the component sub-scores into a 0..10 safety score.

    ``prob_block`` is the probability the underlying *stays inside* the safe
    zone (e.g. ``p_in_range_1sigma``) — higher is better.

    ``pin_risk``, ``body_danger``, ``event_risk`` are 0..1 measures where higher
    is *worse*; we invert them before weighting.

    ``vol_regime`` is one of ``low``/``medium``/``high``/``unknown`` and contributes
    a fixed contextual sub-score.
    """
    w = weights or DEFAULT_WEIGHTS
    safe_prob_block = max(0.0, min(1.0, prob_block))
    safe_pin = 1.0 - max(0.0, min(1.0, pin_risk))
    safe_body = 1.0 - max(0.0, min(1.0, body_danger))
    safe_event = 1.0 - max(0.0, min(1.0, event_risk))
    safe_vol = _VOL_SCORE.get((vol_regime or "unknown").lower(), 0.45)

    weighted = (
        w["prob_block"] * safe_prob_block
        + w["pin_risk"] * safe_pin
        + w["body_danger"] * safe_body
        + w["event_risk"] * safe_event
        + w["vol_regime"] * safe_vol
    )
    total_weight = sum(w.values()) or 1.0
    score_0_1 = weighted / total_weight
    score_0_10 = round(score_0_1 * 10.0, 2)
    return {
        "score": score_0_10,
        "label": _label_from_score(score_0_10),
        "components": {
            "prob_block": round(safe_prob_block, 3),
            "pin_risk": round(safe_pin, 3),
            "body_danger": round(safe_body, 3),
            "event_risk": round(safe_event, 3),
            "vol_regime": round(safe_vol, 3),
        },
    }
