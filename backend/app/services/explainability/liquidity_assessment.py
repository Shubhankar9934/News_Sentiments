"""Liquidity Assessment explanation for the Open Full Report.

The card carries a single ``liquidity`` enum (Poor/Average/Good). The
report needs the 3-axis decomposition the user described:

    underlying_liquidity   — average daily volume of the underlying
    options_liquidity      — chain quality proxy (from credit safety label)
    execution_quality      — what actually matters for exit: pin / body
                             proximity that widens the mid on close

A short ``reason`` sentence names the specific driver so the user
understands why SPY (extremely liquid underlying) can still show
``Poor`` execution quality when sitting at a high-gamma pin.
"""

from __future__ import annotations

from typing import Any

from app.services.dashboard.schemas import (
    LiquidityAssessment,
    LiquidityAxis,
    LiquidityLabel,
    ReverseBwbSummary,
    normalize_liquidity,
)


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _grade_for_underlying(avg_vol_20d: float | None) -> LiquidityLabel:
    if not isinstance(avg_vol_20d, (int, float)):
        return "Average"
    if avg_vol_20d >= 5_000_000:
        return "Good"
    if avg_vol_20d >= 1_000_000:
        return "Good"
    if avg_vol_20d >= 200_000:
        return "Average"
    return "Poor"


def _grade_for_options(credit_label: str | None) -> LiquidityLabel:
    label = (credit_label or "").upper()
    if label == "SAFE":
        return "Good"
    if label == "CAUTION":
        return "Average"
    return "Poor"


def _execution_quality(options_intel: dict[str, Any]) -> tuple[LiquidityLabel, str]:
    pin_risk = _safe_dict(options_intel.get("pin_risk"))
    body_danger = _safe_dict(options_intel.get("body_danger"))
    pin_score = float(pin_risk.get("score") or 0.0)
    pin_label = pin_risk.get("label") or "Low"
    body_label = body_danger.get("label") or "Low"
    nearest_round = pin_risk.get("nearest_round")
    body_distance = body_danger.get("distance_pct")

    # Execution quality degrades when the body sits near a high-gamma magnet —
    # this widens the mid-spread on exit even on a thick underlying.
    high_pin = pin_score >= 0.7 or pin_label == "High"
    medium_pin = 0.4 <= pin_score < 0.7 or pin_label == "Medium"
    bad_body = body_label == "High"
    mid_body = body_label == "Medium"

    if high_pin and (bad_body or mid_body):
        grade: LiquidityLabel = "Poor"
        detail = (
            f"Body placement {body_label} with strong pin to "
            f"{nearest_round} → mid-spread expected to widen on exit."
        )
    elif high_pin or bad_body:
        grade = "Poor"
        detail = (
            f"High gamma magnet to {nearest_round} or body placement {body_label}; "
            "expect slippage on close."
        )
    elif medium_pin or mid_body:
        grade = "Average"
        detail = (
            f"Some round-number drag near {nearest_round}; exit spreads modestly wider."
            if nearest_round is not None
            else "Some round-number drag; exit spreads modestly wider."
        )
    else:
        grade = "Good"
        if isinstance(body_distance, (int, float)):
            detail = (
                f"Body is {float(body_distance):.2f}% from spot, clear of gamma "
                "magnets — clean exit expected."
            )
        else:
            detail = "Body clear of gamma magnets — clean exit expected."

    return grade, detail


def _underlying_detail(avg_vol_20d: float | None, grade: LiquidityLabel) -> str:
    if isinstance(avg_vol_20d, (int, float)) and avg_vol_20d > 0:
        return f"20-day average volume {int(avg_vol_20d):,} shares ({grade})."
    return f"Underlying volume profile {grade}."


def _options_detail(credit_label: str | None, grade: LiquidityLabel) -> str:
    if credit_label:
        return (
            f"Chain quality proxy {grade} (credit safety label "
            f"{credit_label})."
        )
    return f"Chain quality proxy {grade}."


def _compose_reason(
    underlying: LiquidityAxis,
    options: LiquidityAxis,
    execution: LiquidityAxis,
) -> str:
    grades = {underlying.grade, options.grade, execution.grade}
    if grades == {"Good"}:
        return (
            "Underlying, options chain and execution quality are all Good — "
            "no liquidity penalty applied."
        )
    if execution.grade == "Poor":
        return (
            f"Execution quality is Poor: {execution.detail or 'pin/body interaction'}. "
            "Underlying tape can be thick yet still produce a wide exit print."
        )
    if options.grade == "Poor":
        return (
            "Options chain is the bottleneck: low credit-safety quality often "
            "tracks wider strike spacing and thinner posted size."
        )
    if underlying.grade == "Poor":
        return (
            "Underlying tape is thin — every execution will reach further "
            "into the book and pay more crossing spread."
        )
    return (
        "Mixed: at least one of underlying / options / execution falls below "
        "Good, so liquidity carries a small drag on this setup."
    )


def build_liquidity_assessment(
    *,
    ticker: str,  # noqa: ARG001 - kept for assembler symmetry
    report: dict[str, Any],
    options_intel: dict[str, Any] | None,
    deliberation_layer: dict[str, Any] | None,
    summary: ReverseBwbSummary | None,
) -> LiquidityAssessment | None:
    """Compose the 3-axis liquidity decomposition."""

    if not options_intel:
        return None

    options_intel_d = _safe_dict(options_intel)
    pipeline_meta = report.get("_pipeline_meta") if isinstance(report, dict) else None
    price_snapshot = _safe_dict(_safe_dict(pipeline_meta).get("price_snapshot"))

    # Prefer the existing liquidity_context if the deliberation layer carries
    # it (more sources than just the price snapshot).
    avg_vol = price_snapshot.get("avg_volume_20d")
    lq_context = None
    if deliberation_layer:
        lq_context = _safe_dict(deliberation_layer.get("liquidity_context"))
        if lq_context.get("avg_volume_20d"):
            avg_vol = lq_context["avg_volume_20d"]

    underlying_grade = _grade_for_underlying(
        float(avg_vol) if isinstance(avg_vol, (int, float)) else None
    )
    underlying_axis = LiquidityAxis(
        grade=underlying_grade,
        detail=_underlying_detail(
            float(avg_vol) if isinstance(avg_vol, (int, float)) else None,
            underlying_grade,
        ),
    )

    credit_block = _safe_dict(options_intel_d.get("credit_safety"))
    options_grade = _grade_for_options(credit_block.get("label"))
    options_axis = LiquidityAxis(
        grade=options_grade,
        detail=_options_detail(credit_block.get("label"), options_grade),
    )

    exec_grade, exec_detail = _execution_quality(options_intel_d)
    execution_axis = LiquidityAxis(grade=exec_grade, detail=exec_detail)

    # When the card summary exists, conservatively raise the underlying
    # axis grade to match the card if the card was more generous.
    if summary is not None:
        card_grade = normalize_liquidity(summary.liquidity)
        if card_grade == "Good" and underlying_grade == "Average":
            underlying_axis = LiquidityAxis(
                grade=card_grade,
                detail=underlying_axis.detail,
            )

    reason = _compose_reason(underlying_axis, options_axis, execution_axis)

    return LiquidityAssessment(
        underlying_liquidity=underlying_axis,
        options_liquidity=options_axis,
        execution_quality=execution_axis,
        reason=reason,
    )
