"""Position-risk explainability block.

Lifts the deterministic ``options_intelligence.position_risk`` payload
into the report-side schema. Pure read; never recomputes math.
"""

from __future__ import annotations

from typing import Any

from app.services.dashboard.schemas import PositionRiskExplain


def build_position_risk_explain(
    *,
    ticker: str,  # noqa: ARG001
    options_intel: dict[str, Any] | None,
) -> PositionRiskExplain | None:
    if not options_intel:
        return None
    block = options_intel.get("position_risk")
    if not block:
        return None
    try:
        return PositionRiskExplain.model_validate(block)
    except Exception:
        return None
