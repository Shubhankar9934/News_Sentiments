"""Reverse-BWB suitability score and wing-width / DTE suggestion."""

from __future__ import annotations

from typing import Literal


def _suggest_wing_width_pct(sigma_pct: float) -> float:
    """Wing width as a percent of spot — wider in high-vol regimes to absorb noise."""
    if sigma_pct >= 5.0:
        return 3.0
    if sigma_pct >= 3.0:
        return 2.5
    if sigma_pct >= 1.5:
        return 2.0
    return 1.5


def _suggest_dte(vol_regime: str | None, event_risk_score: float) -> int:
    regime = (vol_regime or "unknown").lower()
    base = {"low": 14, "medium": 7, "high": 4, "unknown": 7}.get(regime, 7)
    if event_risk_score >= 0.7:
        base = max(2, base - 3)
    elif event_risk_score >= 0.45:
        base = max(3, base - 1)
    return base


def reverse_bwb_suitability(
    credit_safety_score: float,
    expected_range_sigma_pct: float,
    vol_regime: str | None,
    event_risk_score: float,
) -> dict[str, object]:
    """Return ``{score, label, suggested_wing_width_pct, suggested_dte, rationale}``."""
    # blend credit safety (0..10) with vol headroom (smaller sigma is easier)
    vol_headroom = max(0.0, min(1.0, 1.0 - expected_range_sigma_pct / 8.0))
    score_0_1 = 0.6 * (credit_safety_score / 10.0) + 0.4 * vol_headroom
    score_0_10 = round(score_0_1 * 10.0, 2)
    label: Literal["SAFE", "CAUTION", "UNSAFE"] = (
        "SAFE" if score_0_10 >= 7.0 else "CAUTION" if score_0_10 >= 4.0 else "UNSAFE"
    )

    wing = _suggest_wing_width_pct(expected_range_sigma_pct)
    dte = _suggest_dte(vol_regime, event_risk_score)

    if label == "SAFE":
        rationale = (
            f"Favorable: credit safety {credit_safety_score:.1f}/10, "
            f"{expected_range_sigma_pct:.2f}% expected sigma — collect a defined-risk credit."
        )
    elif label == "CAUTION":
        rationale = (
            f"Mixed setup: credit safety {credit_safety_score:.1f}/10 with "
            f"{expected_range_sigma_pct:.2f}% expected sigma. Size small and widen wings."
        )
    else:
        rationale = (
            f"Unfavorable: credit safety {credit_safety_score:.1f}/10 and "
            f"{expected_range_sigma_pct:.2f}% expected sigma — wait or use a different structure."
        )

    return {
        "score": score_0_10,
        "label": label,
        "suggested_wing_width_pct": wing,
        "suggested_dte": dte,
        "rationale": rationale,
    }
