"""Pydantic schema for the dashboard executive-summary block."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DecisionLabel = Literal["SAFE", "WATCH", "AVOID"]
RiskLevel = Literal["Low", "Medium", "High"]
QualityLevel = Literal["Poor", "Fair", "Good", "Excellent"]
OutlookLabel = Literal["Bullish", "Bearish", "Volatile", "Sideways", "Mixed"]


class ExpectedRangeShort(BaseModel):
    """Slimmed expected-range projection for the card."""

    low: float
    high: float


class ExecutiveSummary(BaseModel):
    """Trader-facing one-glance summary derived from a completed report.

    All fields are deterministic projections of `options_intelligence`,
    `deliberation_layer.consensus`, and `_pipeline_meta` — no new LLM calls.
    """

    decision: DecisionLabel
    credit_safety_score: float = Field(ge=0.0, le=10.0)
    outlook: OutlookLabel
    risk: RiskLevel
    confidence: RiskLevel
    plus_move_risk: RiskLevel
    minus_move_risk: RiskLevel
    expected_range: ExpectedRangeShort
    event_risk: RiskLevel
    iv_quality: QualityLevel
    liquidity: QualityLevel
    pin_risk: RiskLevel
    summary: str = Field(max_length=500)
    summary_version: int = Field(ge=1, le=2)
    derived_at: str
    council_decision_raw: str | None = None
