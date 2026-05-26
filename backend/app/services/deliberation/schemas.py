"""Pydantic schemas for multi-LLM deliberation."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ModelKey = Literal["gpt", "claude", "gemini", "deepseek", "groq"]
Stance = Literal["bullish", "bearish", "neutral", "mixed"]
TradeDecision = Literal["ENTER", "WAIT", "AVOID"]
DeliberationStatus = Literal["pending", "running", "complete", "failed", "skipped"]
CouncilRoleKey = Literal[
    "portfolio_manager",
    "risk_manager",
    "market_strategist",
    "quant_reviewer",
    "contrarian_investor",
]
AssessmentRoleKey = Literal[
    "openai_assessment_analyst",
    "claude_risk_assessment_analyst",
    "deepseek_quant_assessment_analyst",
]


class ReasoningStep(BaseModel):
    step: int
    title: str
    analysis: str


class DeskResearchReport(BaseModel):
    """Analysis-only desk output — not a trade decision."""

    role_key: str
    role_label: str
    model: ModelKey
    key_findings: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    risks: list[str] = Field(default_factory=list)
    invalidators: list[str] = Field(default_factory=list)
    analytical_view: Stance = "neutral"
    confidence_in_analysis: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning_steps: list[ReasoningStep] = Field(default_factory=list)
    provider_attempts: list[str] = Field(default_factory=list)
    error: str | None = None


class IntelligencePackage(BaseModel):
    ticker: str
    question: str
    trigger: str
    desks: dict[str, DeskResearchReport] = Field(default_factory=dict)
    options_snapshot: dict[str, Any] = Field(default_factory=dict)
    credit_safety: dict[str, Any] = Field(default_factory=dict)
    built_at: str = ""
    # Assessment Team consensus is attached AFTER the Assessment Team
    # runs (between desk analyses and the Decision Council). Council
    # members are instructed to treat this as the authoritative card
    # body when reasoning about Enter/Wait/Avoid.
    assessment_consensus: dict[str, Any] | None = None


class CouncilMemberDecision(BaseModel):
    model: ModelKey
    council_role: CouncilRoleKey
    council_label: str
    decision: TradeDecision
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning_steps: list[ReasoningStep] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    provider_attempts: list[str] = Field(default_factory=list)
    error: str | None = None


class CouncilCritique(BaseModel):
    model: ModelKey
    council_role: CouncilRoleKey
    council_label: str
    agrees_with: list[CouncilRoleKey] = Field(default_factory=list)
    disagrees_with: list[CouncilRoleKey] = Field(default_factory=list)
    strongest_counterargument: str = ""
    weakest_reasoning_detected: str = ""
    new_risks_identified: list[str] = Field(default_factory=list)
    error: str | None = None


class CouncilRevision(BaseModel):
    model: ModelKey
    council_role: CouncilRoleKey
    council_label: str
    prior_decision: TradeDecision
    revised_decision: TradeDecision
    prior_confidence: float = Field(ge=0.0, le=1.0)
    revised_confidence: float = Field(ge=0.0, le=1.0)
    revision_rationale: str = ""
    error: str | None = None


class CouncilConsensus(BaseModel):
    decision: TradeDecision
    support: dict[str, int] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    main_conflict: str = ""
    debate_summary: str = ""
    member_decisions: dict[str, CouncilMemberDecision] = Field(default_factory=dict)


class CouncilLayer(BaseModel):
    question: str = ""
    trigger: str = ""
    round1: dict[str, CouncilMemberDecision] = Field(default_factory=dict)
    round2: dict[str, CouncilCritique] = Field(default_factory=dict)
    round3: dict[str, CouncilRevision] = Field(default_factory=dict)
    consensus: CouncilConsensus | None = None
    degraded: bool = False
    quorum_meta: dict[str, Any] = Field(default_factory=dict)


class IndependentOpinion(BaseModel):
    model: ModelKey
    stance: Stance
    confidence: float = Field(ge=0.0, le=1.0)
    time_horizon: str = ""
    reasoning_steps: list[ReasoningStep] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    invalidators: list[str] = Field(default_factory=list)
    position_size_suggestion: str = ""
    hidden_assumptions: list[str] = Field(default_factory=list)
    error: str | None = None
    # PR-D additive — desk-role specialization metadata.
    role_key: str | None = None
    role_label: str | None = None
    provider_attempts: list[str] = Field(default_factory=list)


class ConfidenceRevision(BaseModel):
    old: float = Field(ge=0.0, le=1.0)
    new: float = Field(ge=0.0, le=1.0)


def _normalize_desk_ref_list(value: object) -> list[str]:
    """Coerce LLM desk references to plain desk_key strings."""
    if not value:
        return []
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str):
            key = item.strip()
            if key:
                out.append(key)
            continue
        if isinstance(item, dict):
            for field in ("desk", "desk_key", "model", "role_key"):
                raw = item.get(field)
                if isinstance(raw, str) and raw.strip():
                    out.append(raw.strip())
                    break
    return out


class DebateCritique(BaseModel):
    model: ModelKey
    role_key: str | None = None
    role_label: str | None = None
    agrees_with: list[str] = Field(default_factory=list)
    disagrees_with: list[str] = Field(default_factory=list)
    strongest_counterargument: str = ""
    weakest_reasoning_detected: str = ""
    new_risks_identified: list[str] = Field(default_factory=list)
    confidence_revision: ConfidenceRevision | None = None
    error: str | None = None

    @field_validator("agrees_with", "disagrees_with", mode="before")
    @classmethod
    def _coerce_desk_refs(cls, value: object) -> list[str]:
        return _normalize_desk_ref_list(value)


class DeliberationContext(BaseModel):
    ticker: str
    market_context: dict[str, Any] = Field(default_factory=dict)
    sentiment: dict[str, Any] = Field(default_factory=dict)
    narrative: dict[str, Any] = Field(default_factory=dict)
    key_events: list[dict[str, Any]] = Field(default_factory=list)
    source_reliability: list[dict[str, Any]] = Field(default_factory=list)
    historical_analogs: list[dict[str, Any]] = Field(default_factory=list)
    article_evidence: list[dict[str, Any]] = Field(default_factory=list)
    top_impact_events: list[dict[str, Any]] = Field(default_factory=list)
    evidence_summary: dict[str, Any] = Field(default_factory=dict)
    # PR-D additive — deterministic options-intelligence block (PR-A1).
    options_intelligence: dict[str, Any] | None = None
    technical_context: dict[str, Any] | None = None
    flow_context: dict[str, Any] | None = None
    liquidity_context: dict[str, Any] | None = None
    regime_context: dict[str, Any] | None = None
    news_momentum: dict[str, Any] | None = None
    # Phase 6 — macro transmission causal chain detected from key
    # events / dominant narrative. None when no shock matches the
    # topology table.
    macro_transmission_chain: dict[str, Any] | None = None


class CalibrationOutput(BaseModel):
    directional_conviction: float = Field(default=0.0, ge=0.0, le=1.0)
    consensus_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_quality: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_aggregate: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty: Literal["high", "medium", "low"] = "medium"


class ConsensusOutput(BaseModel):
    consensus: str
    agreement_score: float = Field(ge=0.0, le=1.0)
    uncertainty: Literal["high", "medium", "low"]
    main_conflicts: list[str] = Field(default_factory=list)
    hidden_risks: list[str] = Field(default_factory=list)
    recommended_positioning: str = ""
    debate_summary: str = ""
    dominant_thesis: str = ""
    conflicting_thesis: str = ""
    # PR1 additive — calibration & honest verdict
    reconciled_label: str | None = None
    support_counts: dict[str, list[str]] = Field(default_factory=dict)
    calibration: CalibrationOutput | None = None
    # PR4 additive — clustered/deduplicated risk objects.
    structured_risks: list[dict[str, Any]] = Field(default_factory=list)
    # PR6 additive — bull / bear / neutral thesis clusters.
    thesis_clusters: list[dict[str, Any]] = Field(default_factory=list)


class DeliberationMetrics(BaseModel):
    disagreement_matrix: dict[str, dict[str, str]] = Field(default_factory=dict)
    confidence_drift: list[dict[str, Any]] = Field(default_factory=list)
    model_divergence: float = 0.0
    confidence_spread: float = 0.0
    contradiction_density: float = 0.0
    reasoning_overlap: float = 0.0
    # PR3 additive — per-model round-2 novelty signal.
    round_novelty: list[dict[str, Any]] = Field(default_factory=list)
    # PR5/PR7 additive — disagreement topology, conviction heatmap, contradictions.
    disagreement_topology: dict[str, Any] | None = None
    conviction_heatmap: dict[str, Any] | None = None
    contradictions: list[dict[str, Any]] = Field(default_factory=list)


class DeliberationLayer(BaseModel):
    status: DeliberationStatus
    run_id: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    models_requested: list[str] = Field(default_factory=list)
    models_used: list[str] = Field(default_factory=list)
    desks_requested: list[str] = Field(default_factory=list)
    desks_used: list[str] = Field(default_factory=list)
    round1: dict[str, Any] = Field(default_factory=dict)
    debate_rounds: list[dict[str, Any]] = Field(default_factory=list)
    consensus: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None
    error: str | None = None
    skip_reason: str | None = None
    # PR2 additive — explicit debate routing assignments per round.
    debate_assignments: list[dict[str, Any]] = Field(default_factory=list)
    # PR9 additive — evidence verification stubs (off by default).
    evidence_verification: list[dict[str, Any]] = Field(default_factory=list)
    # Hybrid architecture — analysis + assessment + council layers.
    analysis_layer: dict[str, Any] | None = None
    intelligence_package: dict[str, Any] | None = None
    assessment_layer: dict[str, Any] | None = None
    assessment_triggered: bool = False
    council_layer: dict[str, Any] | None = None
    council_triggered: bool = False
    council_question: str | None = None
    mapped_decision: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)
