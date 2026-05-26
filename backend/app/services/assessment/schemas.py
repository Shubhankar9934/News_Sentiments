"""Pydantic schemas for the Reverse BWB Assessment Team."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.services.dashboard.schemas import (
    AssessmentConsensus,
    ChanceLabel,
    ConfidenceLevel,
    ExpectedRange,
    IvQualityLabel,
    LiquidityLabel,
    NextOutlook,
    RiskLevel,
    TodayOutlook,
)
from app.services.deliberation.schemas import AssessmentRoleKey, ModelKey, ReasoningStep


class AssessmentMemberOpinion(BaseModel):
    """Round 1: one member's full Reverse BWB card.

    Every field that the final ``ReverseBwbSummary`` exposes — except
    ``decision`` — is generated here. The 4-round debate refines these
    independently per member; the consensus synthesizer merges them
    deterministically.
    """

    model: ModelKey
    assessment_role: AssessmentRoleKey
    assessment_label: str

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

    reasoning_steps: list[ReasoningStep] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    # Phase 8 — explicit per-lens commentary used by the explainability
    # layer. Optional so older runs continue to validate. Keys are the
    # 5 risk lenses; each value is a 1–3 sentence string. The card body
    # fields above are unaffected by this addition.
    risk_lenses: dict[str, str] | None = None
    provider_attempts: list[str] = Field(default_factory=list)
    error: str | None = None

    model_config = ConfigDict(extra="forbid")


class AssessmentCritique(BaseModel):
    """Round 2: peer critique focused on numeric / enum disagreements."""

    model: ModelKey
    assessment_role: AssessmentRoleKey
    assessment_label: str

    agrees_with: list[AssessmentRoleKey] = Field(default_factory=list)
    disagrees_with: list[AssessmentRoleKey] = Field(default_factory=list)
    numeric_disagreements: list[str] = Field(default_factory=list)
    enum_disagreements: list[str] = Field(default_factory=list)
    missed_risks: list[str] = Field(default_factory=list)
    summary: str = ""
    provider_attempts: list[str] = Field(default_factory=list)
    error: str | None = None


class AssessmentRevision(BaseModel):
    """Round 3: member's revised card after peer critique."""

    model: ModelKey
    assessment_role: AssessmentRoleKey
    assessment_label: str

    revised_opinion: AssessmentMemberOpinion | None = None
    revision_rationale: str = ""
    provider_attempts: list[str] = Field(default_factory=list)
    error: str | None = None


class AssessmentLayer(BaseModel):
    """Full Assessment Team output — debate rounds + deterministic consensus."""

    question: str = ""
    trigger: str = ""
    round1: dict[str, AssessmentMemberOpinion] = Field(default_factory=dict)
    round2: dict[str, AssessmentCritique] = Field(default_factory=dict)
    round3: dict[str, AssessmentRevision] = Field(default_factory=dict)
    consensus: AssessmentConsensus | None = None
    consensus_meta: dict[str, Any] = Field(default_factory=dict)
    degraded: bool = False
    quorum_meta: dict[str, Any] = Field(default_factory=dict)
