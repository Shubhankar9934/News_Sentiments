"""Pydantic schemas for the Reverse BWB Intelligence Dashboard.

Three layers live here:

1. ``AssessmentConsensus`` — the canonical card body produced by the
   Reverse BWB Assessment Team (3 LLMs x 4 rounds). Owns every field
   except ``decision``.

2. ``ReverseBwbSummary`` — the final stored object: assessment fields
   plus a ``decision`` from the 5-member Decision Council. This is the
   single contract persisted to ``ticker_reverse_bwb_summary`` and
   returned by ``GET /api/v1/dashboard/tickers``.

3. ``DashboardTickerCard`` / ``WatchlistBatchStatus`` — read-side
   shapes served to the frontend grid.

Enum vocabularies are intentionally narrow per the trader spec:
decision ``Enter/Wait/Avoid``; risk/chance/pin/event ``Low/Medium/High``;
outlook split between today (``Bullish/Bearish/Sideways/Choppy``) and
the next 2-3 days (``Bullish/Bearish/Sideways/Volatile``); IV quality
and liquidity both on a unified ``Poor/Average/Good`` scale.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# Label vocabularies (kept in one place so the LLM prompt, frontend Zod and
# DB column comments can quote a single source of truth).
DecisionLabel = Literal["Enter", "Wait", "Avoid"]
RiskLevel = Literal["Low", "Medium", "High"]
ConfidenceLevel = Literal["Low", "Medium", "High"]
TodayOutlook = Literal["Bullish", "Bearish", "Sideways", "Choppy"]
NextOutlook = Literal["Bullish", "Bearish", "Sideways", "Volatile"]
ChanceLabel = Literal["Low", "Medium", "High"]
IvQualityLabel = Literal["Poor", "Average", "Good"]
LiquidityLabel = Literal["Poor", "Average", "Good"]
OptionType = Literal["CALL", "PUT"]
TickerStatus = Literal["pending", "running", "completed", "failed"]
BatchState = Literal["idle", "running", "completed", "failed"]


class ExpectedRange(BaseModel):
    low: float
    high: float


class AssessmentConsensus(BaseModel):
    """Card body produced by the Assessment Team — every field except decision.

    This is the strict contract the Assessment Team's deterministic
    consensus synthesizer must emit. The watchlist runner merges this
    with the Decision Council's ``Enter/Wait/Avoid`` to form the final
    ``ReverseBwbSummary``.
    """

    credit_safety_score: float = Field(ge=0.0, le=10.0)
    risk: RiskLevel
    confidence: ConfidenceLevel

    today_outlook: TodayOutlook
    next_3d_outlook: NextOutlook

    chance_up_2_3_pct: ChanceLabel
    chance_down_2_3_pct: ChanceLabel

    expected_range_today: ExpectedRange
    expected_range_next_3d: ExpectedRange

    danger_zone: str = Field(min_length=1, max_length=200)

    pin_risk: RiskLevel
    event_risk: RiskLevel
    iv_quality: IvQualityLabel
    liquidity: LiquidityLabel

    actual_dynamics_summary: list[str] = Field(min_length=3, max_length=4)

    model_config = ConfigDict(extra="forbid")


class ReverseBwbSummary(BaseModel):
    """Final canonical trader summary (assessment fields + council decision).

    One row in ``ticker_reverse_bwb_summary`` per watchlist ticker.
    Validation here is the contract that protects the dashboard tables —
    if either layer returns a malformed payload the batch runner raises
    and marks the ticker as failed.
    """

    ticker: str

    decision: DecisionLabel
    credit_safety_score: float = Field(ge=0.0, le=10.0)
    risk: RiskLevel
    confidence: ConfidenceLevel

    today_outlook: TodayOutlook
    next_3d_outlook: NextOutlook

    chance_up_2_3_pct: ChanceLabel
    chance_down_2_3_pct: ChanceLabel

    expected_range_today: ExpectedRange
    expected_range_next_3d: ExpectedRange

    danger_zone: str = Field(min_length=1, max_length=200)

    pin_risk: RiskLevel
    event_risk: RiskLevel
    iv_quality: IvQualityLabel
    liquidity: LiquidityLabel

    actual_dynamics_summary: list[str] = Field(min_length=3, max_length=4)

    model_config = ConfigDict(extra="forbid")


class OptionOpportunity(BaseModel):
    combo: str
    expiry: str
    premium: float = Field(ge=0.0)
    margin: float = Field(ge=0.0)
    liquidity: LiquidityLabel


class OptionOpportunities(BaseModel):
    calls: list[OptionOpportunity] = Field(default_factory=list)
    puts: list[OptionOpportunity] = Field(default_factory=list)


class PriceSnapshot(BaseModel):
    """Header info for section 1 of the ticker card.

    V1 uses pipeline ``_pipeline_meta.price_snapshot`` (yesterday's close +
    today's % change). V2 will swap in an IBKR realtime feed.
    """

    price: float | None = None
    daily_change_pct: float | None = None
    as_of: str | None = None
    source: str | None = None


class DashboardTickerCard(BaseModel):
    """Server-side projection consumed by the grid card."""

    ticker: str
    company_name: str
    tier_key: str
    status: TickerStatus

    generated_at: datetime | None = None
    price_snapshot: PriceSnapshot | None = None
    reverse_bwb: ReverseBwbSummary | None = None
    opportunities: OptionOpportunities | None = None

    report_id: str | None = None
    error_message: str | None = None


class WatchlistBatchStatus(BaseModel):
    """Live snapshot of the in-process batch runner."""

    state: BatchState = "idle"
    current_ticker: str | None = None
    queued: list[str] = Field(default_factory=list)
    completed: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    total: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_error: str | None = None


class DashboardTickersResponse(BaseModel):
    """Combined payload for ``GET /api/v1/dashboard/tickers``."""

    status: WatchlistBatchStatus
    cards: list[DashboardTickerCard]


class DashboardTickerReportResponse(BaseModel):
    """Full persisted report snapshot for ``GET /dashboard/tickers/{ticker}/report``.

    Sourced from ``ticker_reports.report_json`` — the canonical post-refresh
    payload that includes inline DIL output merged by the watchlist batch.
    """

    ticker: str
    status: TickerStatus
    research_report_id: str | None = None
    generated_at: datetime | None = None
    report_json: dict[str, Any]


# --------------------------------------------------------------------------
# Explainability layer (Open Full Report only).
#
# This is the "Why?" container behind every frozen card value. Every sub-block
# is Optional so a partial pipeline run still produces a renderable payload,
# and so old reports written before this layer existed continue to parse.
#
# The card schema (``ReverseBwbSummary`` / ``DashboardTickerCard``) is
# completely unaffected by anything here — these structures only ever ride
# inside ``report_json["explainability"]`` returned by the full-report
# endpoint, never on the card endpoint.
# --------------------------------------------------------------------------

EXPLAINABILITY_LAYER_VERSION: int = 1


class CreditSafetyBreakdownRow(BaseModel):
    """Single row in the Credit Safety decomposition table.

    The 0..10 ``move_stability`` row is the anchor; every subsequent row
    contributes a signed ``delta`` so the running sum lands on the card's
    ``credit_safety_score``.
    """

    label: str
    value: float | None = None
    delta: float | None = None
    explanation: str

    model_config = ConfigDict(extra="forbid")


class CreditSafetyBreakdown(BaseModel):
    move_stability: CreditSafetyBreakdownRow
    pin_risk_impact: CreditSafetyBreakdownRow
    event_risk_impact: CreditSafetyBreakdownRow
    volatility_impact: CreditSafetyBreakdownRow
    structure_placement_impact: CreditSafetyBreakdownRow
    liquidity_impact: CreditSafetyBreakdownRow
    final_credit_safety: float = Field(ge=0.0, le=10.0)
    method: str = "weighted_components_v1"

    model_config = ConfigDict(extra="forbid")


class ConfidenceCalibrationRow(BaseModel):
    label: str
    value: float | None = None
    explanation: str

    model_config = ConfigDict(extra="forbid")


class ConfidenceCalibration(BaseModel):
    raw_desk_confidence: ConfidenceCalibrationRow
    cross_agent_agreement: ConfidenceCalibrationRow
    evidence_overlap: ConfidenceCalibrationRow
    contradiction_penalty: ConfidenceCalibrationRow
    council_confidence: ConfidenceCalibrationRow | None = None
    final_confidence_pct: float = Field(ge=0.0, le=100.0)
    final_confidence_bucket: ConfidenceLevel

    model_config = ConfigDict(extra="forbid")


class LiquidityAxis(BaseModel):
    grade: LiquidityLabel
    detail: str | None = None

    model_config = ConfigDict(extra="forbid")


class LiquidityAssessment(BaseModel):
    underlying_liquidity: LiquidityAxis
    options_liquidity: LiquidityAxis
    execution_quality: LiquidityAxis
    reason: str

    model_config = ConfigDict(extra="forbid")


class StructureGeometry(BaseModel):
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

    model_config = ConfigDict(extra="forbid")


class StructureAnalysisExplain(BaseModel):
    geometry: StructureGeometry
    desk_narrative: str | None = None
    desk_role_key: str | None = None
    desk_model: str | None = None

    model_config = ConfigDict(extra="forbid")


class PositionRiskExplain(BaseModel):
    probability_of_profit: float = Field(ge=0.0, le=1.0)
    probability_of_touch: float = Field(ge=0.0, le=1.0)
    probability_of_breakeven: float = Field(ge=0.0, le=1.0)
    probability_of_max_loss: float = Field(ge=0.0, le=1.0)
    expected_value_usd: float
    method: str = "lognormal_closed_form"
    assumptions: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class MacroTransmissionNode(BaseModel):
    node: str
    label: str
    direction: Literal["up", "down", "flat", "mixed"] | None = None
    evidence: str | None = None

    model_config = ConfigDict(extra="forbid")


class MacroTransmission(BaseModel):
    chain: list[MacroTransmissionNode] = Field(default_factory=list)
    narrative: str | None = None
    primary_shock: str | None = None
    ticker_impact: Literal["supportive", "bearish", "neutral", "mixed"] | None = None

    model_config = ConfigDict(extra="forbid")


class HistoricalAnalogMatch(BaseModel):
    headline: str | None = None
    published_at: str | None = None
    sentiment_score: float | None = None
    impact_score: float | None = None
    match_reason: str | None = None
    match_score: float | None = None
    forward_return_pct: float | None = None
    body_touched: bool | None = None
    credit_retained_pct: float | None = None

    model_config = ConfigDict(extra="forbid")


class HistoricalAnalogAggregates(BaseModel):
    n_setups: int = 0
    win_rate: float | None = None
    avg_credit_retained: float | None = None
    max_loss_frequency: float | None = None
    avg_forward_return_pct: float | None = None
    p_touch_body: float | None = None

    model_config = ConfigDict(extra="forbid")


class HistoricalAnalogsExplain(BaseModel):
    matches: list[HistoricalAnalogMatch] = Field(default_factory=list)
    aggregates: HistoricalAnalogAggregates = Field(default_factory=HistoricalAnalogAggregates)
    lookback_window: str | None = None
    sample_size_warning: str | None = None

    model_config = ConfigDict(extra="forbid")


class AssessmentReasoningLens(BaseModel):
    lens: Literal[
        "ticker_risk",
        "structure_risk",
        "position_risk",
        "historical_analogs",
        "macro_transmission",
    ]
    summary: str
    member_views: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class AssessmentReasoningExplain(BaseModel):
    lenses: list[AssessmentReasoningLens] = Field(default_factory=list)
    members_used: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class CouncilVoteRow(BaseModel):
    member: str
    label: str
    decision: str
    confidence: float | None = None
    top_reason: str | None = None

    model_config = ConfigDict(extra="forbid")


class DecisionJustificationExplain(BaseModel):
    council_votes: list[CouncilVoteRow] = Field(default_factory=list)
    consensus_decision: str
    support_counts: dict[str, int] = Field(default_factory=dict)
    consensus_confidence: float | None = None
    primary_reasons: list[str] = Field(default_factory=list)
    dissent: list[str] = Field(default_factory=list)
    main_conflict: str | None = None

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------
# Phase 11 — Decision Sensitivity Analysis.
#
# Four read-side sub-blocks computed from already-existing intel:
#   1. Key Drivers          — weighted attribution of WHY this decision
#   2. Critical Assumptions — what the decision quietly depends on
#   3. Decision Triggers    — what would flip the decision (ENTER/AVOID)
#   4. Analyst Disagreement — assessment-team stance split + main conflict
#
# All four ride inside ``explainability.decision_sensitivity`` and are
# rendered only in the Open Full Report view — the dashboard card is
# completely unaffected.
# --------------------------------------------------------------------------


class DecisionKeyDriver(BaseModel):
    label: str
    weight_pct: float = Field(ge=0.0, le=100.0)
    direction: Literal["supports", "opposes", "neutral"] = "supports"
    detail: str | None = None

    model_config = ConfigDict(extra="forbid")


class DecisionAssumption(BaseModel):
    label: str
    basis: str | None = None
    fragility: Literal["low", "medium", "high"] = "medium"

    model_config = ConfigDict(extra="forbid")


class DecisionTrigger(BaseModel):
    target_decision: DecisionLabel
    conditions: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class AnalystStanceRow(BaseModel):
    member: str
    label: str
    stance: Literal["Bullish", "Bearish", "Neutral"]
    decision_view: DecisionLabel | None = None
    risk_view: RiskLevel | None = None
    confidence_view: ConfidenceLevel | None = None
    headline: str | None = None

    model_config = ConfigDict(extra="forbid")


class AnalystDisagreementExplain(BaseModel):
    stances: list[AnalystStanceRow] = Field(default_factory=list)
    stance_counts: dict[str, int] = Field(default_factory=dict)
    main_conflict: str | None = None
    converged: bool = False

    model_config = ConfigDict(extra="forbid")


class DecisionSensitivityExplain(BaseModel):
    current_decision: DecisionLabel
    key_drivers: list[DecisionKeyDriver] = Field(default_factory=list)
    assumptions: list[DecisionAssumption] = Field(default_factory=list)
    triggers: list[DecisionTrigger] = Field(default_factory=list)
    analyst_disagreement: AnalystDisagreementExplain | None = None

    model_config = ConfigDict(extra="forbid")


class ExplainabilityLayer(BaseModel):
    """Versioned ``report_json.explainability`` container.

    Every sub-block is Optional so partial-degradation is safe (e.g. when
    the LLM council fails but Phase-1..5 deterministic blocks still ran).
    The frontend renders only the sub-blocks whose payload is present.
    """

    version: int = EXPLAINABILITY_LAYER_VERSION
    generated_at: datetime | None = None

    credit_safety_breakdown: CreditSafetyBreakdown | None = None
    confidence_calibration: ConfidenceCalibration | None = None
    liquidity_assessment: LiquidityAssessment | None = None
    structure_analysis: StructureAnalysisExplain | None = None
    position_risk: PositionRiskExplain | None = None
    macro_transmission: MacroTransmission | None = None
    historical_analogs: HistoricalAnalogsExplain | None = None
    assessment_reasoning: AssessmentReasoningExplain | None = None
    decision_justification: DecisionJustificationExplain | None = None
    decision_sensitivity: DecisionSensitivityExplain | None = None

    model_config = ConfigDict(extra="forbid")


def empty_card(ticker: str, company_name: str, tier_key: str) -> DashboardTickerCard:
    """Placeholder card shown for watchlist tickers that haven't run yet."""

    return DashboardTickerCard(
        ticker=ticker,
        company_name=company_name,
        tier_key=tier_key,
        status="pending",
    )


# --------------------------------------------------------------------------
# Legacy → new-vocabulary upgrade tables.
# Old persisted rows + occasional LLM stylistic drift are remapped on read so
# the strict Pydantic ``Literal`` validation passes without forcing a full
# refresh of every watchlist row.
# --------------------------------------------------------------------------
_DECISION_UPGRADE: dict[str, str] = {
    "SAFE": "Enter",
    "ENTER": "Enter",
    "WATCH": "Wait",
    "WAIT": "Wait",
    "AVOID": "Avoid",
}

_RISK_UPGRADE: dict[str, str] = {
    "LOW": "Low",
    "MEDIUM": "Medium",
    "MED": "Medium",
    "HIGH": "High",
    "EXTREME": "High",
}

_CONFIDENCE_UPGRADE: dict[str, str] = {
    "LOW": "Low",
    "MEDIUM": "Medium",
    "MED": "Medium",
    "HIGH": "High",
}

_TODAY_OUTLOOK_UPGRADE: dict[str, str] = {
    "BULLISH": "Bullish",
    "BEARISH": "Bearish",
    "SIDEWAYS": "Sideways",
    "CHOPPY": "Choppy",
    "VOLATILE": "Choppy",  # legacy Volatile on today's outlook folds to Choppy
    "MIXED": "Choppy",
    "NEUTRAL": "Sideways",
}

_NEXT_OUTLOOK_UPGRADE: dict[str, str] = {
    "BULLISH": "Bullish",
    "BEARISH": "Bearish",
    "SIDEWAYS": "Sideways",
    "VOLATILE": "Volatile",
    "CHOPPY": "Volatile",  # legacy Choppy on next_3d outlook folds to Volatile
    "MIXED": "Volatile",
    "NEUTRAL": "Sideways",
}

_CHANCE_UPGRADE: dict[str, str] = {
    "NONE": "Low",
    "LOW": "Low",
    "MEDIUM": "Medium",
    "MED": "Medium",
    "HIGH": "High",
    "EXTREME": "High",
}

_IV_QUALITY_UPGRADE: dict[str, str] = {
    "CHEAP": "Poor",
    "POOR": "Poor",
    "FAIR": "Average",
    "AVERAGE": "Average",
    "AVG": "Average",
    "ELEVATED": "Good",
    "GOOD": "Good",
    "RICH": "Good",
    "EXCELLENT": "Good",
}

_LIQUIDITY_UPGRADE: dict[str, str] = {
    "POOR": "Poor",
    "FAIR": "Average",
    "AVERAGE": "Average",
    "AVG": "Average",
    "GOOD": "Good",
    "EXCELLENT": "Good",
}


def _coerce(value: Any, table: dict[str, str], default: str | None = None) -> Any:
    if not isinstance(value, str):
        return value
    upper = value.strip().upper()
    mapped = table.get(upper)
    if mapped is not None:
        return mapped
    if default is not None:
        return default
    return value


def normalize_liquidity(value: Any) -> LiquidityLabel:
    """Coerce legacy/extractor liquidity labels into the dashboard vocabulary."""

    return _coerce(value, _LIQUIDITY_UPGRADE, default="Average")  # type: ignore[return-value]


def normalize_summary_dict(payload: dict[str, Any]) -> dict[str, Any]:
    """Coerce legacy stored values + LLM drift into the strict vocabulary.

    Called on every read-path summary load so unrefreshed DB rows that
    still hold ``SAFE``/``Cheap``/``Extreme``/etc. render under the new
    Pydantic ``Literal`` constraints.
    """

    fixed = dict(payload)
    if "decision" in fixed:
        fixed["decision"] = _coerce(fixed["decision"], _DECISION_UPGRADE, default="Wait")
    if "risk" in fixed:
        fixed["risk"] = _coerce(fixed["risk"], _RISK_UPGRADE, default="Medium")
    if "confidence" in fixed:
        fixed["confidence"] = _coerce(
            fixed["confidence"], _CONFIDENCE_UPGRADE, default="Medium"
        )
    if "today_outlook" in fixed:
        fixed["today_outlook"] = _coerce(
            fixed["today_outlook"], _TODAY_OUTLOOK_UPGRADE, default="Sideways"
        )
    if "next_3d_outlook" in fixed:
        fixed["next_3d_outlook"] = _coerce(
            fixed["next_3d_outlook"], _NEXT_OUTLOOK_UPGRADE, default="Sideways"
        )
    for chance_key in ("chance_up_2_3_pct", "chance_down_2_3_pct"):
        if chance_key in fixed:
            fixed[chance_key] = _coerce(
                fixed[chance_key], _CHANCE_UPGRADE, default="Low"
            )
    if "pin_risk" in fixed:
        fixed["pin_risk"] = _coerce(fixed["pin_risk"], _RISK_UPGRADE, default="Medium")
    if "event_risk" in fixed:
        fixed["event_risk"] = _coerce(
            fixed["event_risk"], _RISK_UPGRADE, default="Medium"
        )
    if "iv_quality" in fixed:
        fixed["iv_quality"] = _coerce(
            fixed["iv_quality"], _IV_QUALITY_UPGRADE, default="Average"
        )
    if "liquidity" in fixed:
        fixed["liquidity"] = normalize_liquidity(fixed["liquidity"])
    return fixed
