"""Pydantic schemas for the options-intelligence block attached to each report."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

OptionsSource = Literal["realized_vol", "live_iv"]
RiskLabel = Literal["Low", "Medium", "High"]
SafetyLabel = Literal["SAFE", "CAUTION", "UNSAFE"]


class ExpectedRange(BaseModel):
    low: float
    high: float
    sigma_pct: float
    confidence: float = Field(ge=0.0, le=1.0)


class MoveProbabilities(BaseModel):
    p_up_2pct: float = Field(ge=0.0, le=1.0)
    p_dn_2pct: float = Field(ge=0.0, le=1.0)
    p_up_3pct: float = Field(ge=0.0, le=1.0)
    p_dn_3pct: float = Field(ge=0.0, le=1.0)
    p_in_range_1sigma: float = Field(ge=0.0, le=1.0)


class PinRisk(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    label: RiskLabel
    nearest_round: float
    distance_pct: float


class BodyDanger(BaseModel):
    short_body_lo: float
    short_body_hi: float
    distance_pct: float
    label: RiskLabel


class EventRisk(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    label: RiskLabel
    drivers: list[str] = Field(default_factory=list)


class CreditSafetyComponents(BaseModel):
    prob_block: float
    pin_risk: float
    body_danger: float
    event_risk: float
    vol_regime: float


class CreditSafety(BaseModel):
    score: float = Field(ge=0.0, le=10.0)
    label: SafetyLabel
    components: CreditSafetyComponents


class ReverseBwb(BaseModel):
    score: float = Field(ge=0.0, le=10.0)
    label: SafetyLabel
    suggested_wing_width_pct: float
    suggested_dte: int
    rationale: str


class StructureGeometryBlock(BaseModel):
    """Reverse-BWB structure geometry decomposition.

    Attached to ``options_intelligence.structure_geometry`` only when
    the deterministic structure_geometry module produces output. Not
    on the card.
    """

    spot: float
    body_strike: float
    wing_width_pct: float
    wing_width_dollars: float
    credit: float
    max_loss: float
    dte: int
    distance_to_body_pct: float
    distance_to_body_sigma: float
    body_exposure_pct: float
    wing_protection_ratio: float
    credit_efficiency: float
    risk_reward: float
    upper_breakeven: float
    lower_breakeven: float


class PositionRiskBlock(BaseModel):
    """Position-level risk math attached to ``options_intelligence.position_risk``."""

    probability_of_profit: float = Field(ge=0.0, le=1.0)
    probability_of_touch: float = Field(ge=0.0, le=1.0)
    probability_of_breakeven: float = Field(ge=0.0, le=1.0)
    probability_of_max_loss: float = Field(ge=0.0, le=1.0)
    expected_value_usd: float
    method: str = "lognormal_closed_form"
    assumptions: list[str] = Field(default_factory=list)


class OptionsIntelligence(BaseModel):
    source: OptionsSource = "realized_vol"
    horizon_days: int
    last_close: float
    daily_vol_pct: float
    expected_range: ExpectedRange
    move_probabilities: MoveProbabilities
    pin_risk: PinRisk
    body_danger: BodyDanger
    event_risk: EventRisk
    credit_safety: CreditSafety
    reverse_bwb: ReverseBwb
    structure_geometry: StructureGeometryBlock | None = None
    position_risk: PositionRiskBlock | None = None
    disclaimer: str = (
        "Probability model from realized volatility; not financial advice."
    )
