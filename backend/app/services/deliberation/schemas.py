"""Pydantic schemas for multi-LLM deliberation."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ModelKey = Literal["gpt", "claude", "gemini", "deepseek", "groq"]
Stance = Literal["bullish", "bearish", "neutral", "mixed"]
DeliberationStatus = Literal["pending", "running", "complete", "failed", "skipped"]


class ReasoningStep(BaseModel):
    step: int
    title: str
    analysis: str


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


class ConfidenceRevision(BaseModel):
    old: float = Field(ge=0.0, le=1.0)
    new: float = Field(ge=0.0, le=1.0)


class DebateCritique(BaseModel):
    model: ModelKey
    agrees_with: list[ModelKey] = Field(default_factory=list)
    disagrees_with: list[ModelKey] = Field(default_factory=list)
    strongest_counterargument: str = ""
    weakest_reasoning_detected: str = ""
    new_risks_identified: list[str] = Field(default_factory=list)
    confidence_revision: ConfidenceRevision | None = None
    error: str | None = None


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

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)
