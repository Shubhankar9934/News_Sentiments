"""Liquidity quality from price snapshot and options intelligence."""

from __future__ import annotations

from typing import Any


def build_liquidity_context(
    price_snapshot: dict[str, Any],
    options_intelligence: dict[str, Any] | None,
) -> dict[str, Any]:
    avg_vol = price_snapshot.get("avg_volume_20d") or 0
    last_vol = price_snapshot.get("last_volume") or 0
    vol_ratio = price_snapshot.get("volume_vs_avg")

    if avg_vol >= 5_000_000:
        equity_grade = "Excellent"
    elif avg_vol >= 1_000_000:
        equity_grade = "Good"
    elif avg_vol >= 200_000:
        equity_grade = "Fair"
    else:
        equity_grade = "Poor"

    credit = (options_intelligence or {}).get("credit_safety") or {}
    options_grade = "Good" if credit.get("label") == "SAFE" else "Fair" if credit.get("label") == "CAUTION" else "Poor"

    overall = equity_grade
    if options_grade == "Poor" or equity_grade == "Poor":
        overall = "Poor"
    elif options_grade == "Fair" and equity_grade != "Excellent":
        overall = "Fair"

    return {
        "overall_grade": overall,
        "equity_liquidity": equity_grade,
        "options_liquidity": options_grade,
        "avg_volume_20d": avg_vol,
        "last_volume": last_vol,
        "volume_vs_avg": vol_ratio,
        "credit_safety_score": credit.get("score"),
    }
