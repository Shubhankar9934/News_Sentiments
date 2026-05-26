"""Credit Safety Score decomposition for the Open Full Report.

The card field ``credit_safety_score`` is produced by the existing
weighted formula in :mod:`app.services.options.credit_safety` and is
*never* recomputed here. This builder produces a trader-friendly
6-row "Why is it 4/10?" breakdown that sums to the same number, so the
explanation is mathematically consistent with the card.

Decomposition (anchor + signed deltas):

    move_stability                  anchor 0..10 derived from sigma_pct
    + pin_risk_impact               negative when nearest round is close
    + event_risk_impact             negative when key events crowd window
    + volatility_impact             negative in high-vol regimes
    + structure_placement_impact    negative when body sits near spot
    + liquidity_impact              +/- from card's liquidity grade
    -------------------------------------------
    = final_credit_safety           == options_intelligence.credit_safety.score
"""

from __future__ import annotations

from typing import Any

from app.services.dashboard.schemas import (
    CreditSafetyBreakdown,
    CreditSafetyBreakdownRow,
    ReverseBwbSummary,
)


def _round1(x: float) -> float:
    return round(float(x), 2)


def _move_stability_anchor(sigma_pct: float | None) -> float:
    """Map 1σ% over the horizon to an 0..10 stability anchor.

    sigma_pct == 0  → 10.0 (perfectly calm)
    sigma_pct == 8% → 0.0 (very wild)
    """

    if sigma_pct is None:
        return 5.5
    s = max(0.0, float(sigma_pct))
    raw = 1.0 - min(1.0, s / 8.0)
    return round(raw * 10.0, 2)


def _pin_impact(pin_risk_block: dict[str, Any] | None) -> CreditSafetyBreakdownRow:
    score = float((pin_risk_block or {}).get("score") or 0.0)
    label = str((pin_risk_block or {}).get("label") or "Low")
    if score >= 0.7:
        delta = -2.5
        text = (
            f"Pin risk {label} (score {score:.2f}); price magnetised toward "
            f"nearest round number — meaningful drag on credit safety."
        )
    elif score >= 0.4:
        delta = -1.2
        text = (
            f"Pin risk {label} (score {score:.2f}); some round-number drag "
            f"reduces the safe range."
        )
    elif score >= 0.2:
        delta = -0.4
        text = (
            f"Pin risk {label} (score {score:.2f}); minor magnet effect, "
            f"only a small deduction."
        )
    else:
        delta = 0.2
        text = f"Pin risk {label} (score {score:.2f}); essentially no drag."
    return CreditSafetyBreakdownRow(
        label="Pin Risk Impact",
        value=score,
        delta=_round1(delta),
        explanation=text,
    )


def _event_impact(event_risk_block: dict[str, Any] | None) -> CreditSafetyBreakdownRow:
    score = float((event_risk_block or {}).get("score") or 0.0)
    label = str((event_risk_block or {}).get("label") or "Low")
    drivers = list((event_risk_block or {}).get("drivers") or [])
    driver_clip = ", ".join(drivers[:2]) if drivers else "no major catalysts"
    if score >= 0.7:
        delta = -2.0
        text = (
            f"Event risk {label} (score {score:.2f}); {driver_clip}. "
            "Catalyst stack heavily reduces safety."
        )
    elif score >= 0.45:
        delta = -1.0
        text = (
            f"Event risk {label} (score {score:.2f}); {driver_clip}. "
            "Catalysts trim safe range."
        )
    elif score >= 0.2:
        delta = -0.3
        text = f"Event risk {label} (score {score:.2f}); {driver_clip}."
    else:
        delta = 0.1
        text = f"Event risk {label} (score {score:.2f}); no material catalysts in window."
    return CreditSafetyBreakdownRow(
        label="Event Risk Impact",
        value=score,
        delta=_round1(delta),
        explanation=text,
    )


def _vol_impact(vol_regime: str | None) -> CreditSafetyBreakdownRow:
    regime = (vol_regime or "unknown").lower()
    if regime in {"high", "elevated"}:
        delta = -1.5
        text = (
            f"Volatility regime '{regime}'; wider expected swings erode "
            "credit safety."
        )
    elif regime == "medium":
        delta = -0.4
        text = "Volatility regime 'medium'; moderate swings — small deduction."
    elif regime == "low":
        delta = 0.4
        text = "Volatility regime 'low'; calm tape supports credit safety."
    else:
        delta = -0.1
        text = "Volatility regime unknown; neutral deduction applied."
    return CreditSafetyBreakdownRow(
        label="Volatility Impact",
        value=None,
        delta=_round1(delta),
        explanation=text,
    )


def _structure_placement_impact(
    body_danger_block: dict[str, Any] | None,
) -> CreditSafetyBreakdownRow:
    label = str((body_danger_block or {}).get("label") or "Low")
    distance_pct = (body_danger_block or {}).get("distance_pct")
    distance_text = (
        f"{float(distance_pct):.2f}% from spot"
        if isinstance(distance_pct, (int, float))
        else "distance unknown"
    )
    if label == "High":
        delta = -2.0
        text = (
            f"Body placement High ({distance_text}); the short body sits in "
            "the most-likely terminal zone — large deduction."
        )
    elif label == "Medium":
        delta = -0.9
        text = (
            f"Body placement Medium ({distance_text}); body partially exposed "
            "to expected terminal range."
        )
    else:
        delta = 0.3
        text = (
            f"Body placement Low ({distance_text}); body sits comfortably "
            "outside expected terminal range."
        )
    return CreditSafetyBreakdownRow(
        label="Structure Placement Impact",
        value=distance_pct if isinstance(distance_pct, (int, float)) else None,
        delta=_round1(delta),
        explanation=text,
    )


def _liquidity_impact(
    summary: ReverseBwbSummary | None, liquidity_block: dict[str, Any] | None
) -> CreditSafetyBreakdownRow:
    grade = None
    if summary is not None:
        grade = summary.liquidity
    elif liquidity_block:
        grade = liquidity_block.get("grade") or liquidity_block.get("label")
    grade_str = str(grade or "Average")
    if grade_str == "Good":
        delta = 0.5
        text = "Liquidity Good; tight spreads support clean credit collection."
    elif grade_str == "Average":
        delta = 0.0
        text = "Liquidity Average; no adjustment."
    else:
        delta = -0.6
        text = (
            "Liquidity Poor; wider spreads make holding/exit harder — "
            "small deduction."
        )
    return CreditSafetyBreakdownRow(
        label="Liquidity Impact",
        value=None,
        delta=_round1(delta),
        explanation=text,
    )


def build_credit_safety_breakdown(
    *,
    ticker: str,  # noqa: ARG001 - kept for assembler symmetry
    report: dict[str, Any],
    options_intel: dict[str, Any] | None,
    summary: ReverseBwbSummary | None,
) -> CreditSafetyBreakdown | None:
    """Decompose the existing card credit safety score into a 6-row table.

    Returns ``None`` if ``options_intelligence`` is absent — without a
    canonical card score there's nothing to anchor the breakdown to.
    """

    if not options_intel:
        return None

    credit_safety_block = options_intel.get("credit_safety") or {}
    final_score = credit_safety_block.get("score")
    if final_score is None:
        return None
    final_score_f = max(0.0, min(10.0, float(final_score)))

    expected_range = options_intel.get("expected_range") or {}
    sigma_pct = expected_range.get("sigma_pct")

    pipeline_meta = report.get("_pipeline_meta") if isinstance(report, dict) else {}
    vol_regime = None
    if isinstance(pipeline_meta, dict):
        vol_regime = pipeline_meta.get("volatility_regime") or pipeline_meta.get(
            "vol_regime"
        )

    anchor_value = _move_stability_anchor(sigma_pct)
    pin_row = _pin_impact(options_intel.get("pin_risk"))
    event_row = _event_impact(options_intel.get("event_risk"))
    vol_row = _vol_impact(vol_regime)
    structure_row = _structure_placement_impact(options_intel.get("body_danger"))
    liquidity_row = _liquidity_impact(summary, None)

    # Normalise deltas so the running sum lands on the card's score
    raw_deltas = [
        pin_row.delta or 0.0,
        event_row.delta or 0.0,
        vol_row.delta or 0.0,
        structure_row.delta or 0.0,
        liquidity_row.delta or 0.0,
    ]
    target_delta = final_score_f - anchor_value
    raw_sum = sum(raw_deltas)
    if abs(raw_sum) > 1e-6:
        scale = target_delta / raw_sum
        # Clamp scaling so qualitative direction is preserved
        scale = max(-2.0, min(2.0, scale))
    else:
        scale = 0.0
    scaled = [round(d * scale, 2) for d in raw_deltas]

    # Apply a final tiny correction on the last row so the sum is exact.
    achieved = anchor_value + sum(scaled)
    residual = round(final_score_f - achieved, 2)
    if abs(residual) >= 0.01:
        scaled[-1] = round(scaled[-1] + residual, 2)

    pin_row.delta = scaled[0]
    event_row.delta = scaled[1]
    vol_row.delta = scaled[2]
    structure_row.delta = scaled[3]
    liquidity_row.delta = scaled[4]

    anchor_row = CreditSafetyBreakdownRow(
        label="Move Stability",
        value=_round1(anchor_value),
        delta=None,
        explanation=(
            f"Anchor derived from expected 1σ move of {float(sigma_pct):.2f}% "
            "over the horizon."
            if isinstance(sigma_pct, (int, float))
            else "Anchor uses fallback midpoint — expected sigma unavailable."
        ),
    )

    return CreditSafetyBreakdown(
        move_stability=anchor_row,
        pin_risk_impact=pin_row,
        event_risk_impact=event_row,
        volatility_impact=vol_row,
        structure_placement_impact=structure_row,
        liquidity_impact=liquidity_row,
        final_credit_safety=_round1(final_score_f),
    )
