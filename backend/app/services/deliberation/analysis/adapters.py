"""Convert between DeskResearchReport and legacy IndependentOpinion."""

from __future__ import annotations

from app.services.deliberation.schemas import DeskResearchReport, IndependentOpinion


def desk_report_to_opinion(report: DeskResearchReport) -> IndependentOpinion:
    """Legacy adapter for consensus, metrics, and deprecated round1 mirror."""
    return IndependentOpinion(
        model=report.model,
        stance=report.analytical_view,
        confidence=report.confidence_in_analysis,
        reasoning_steps=report.reasoning_steps,
        key_risks=report.risks,
        invalidators=report.invalidators,
        role_key=report.role_key,
        role_label=report.role_label,
        provider_attempts=report.provider_attempts,
        error=report.error,
    )


def opinion_to_desk_report(opinion: IndependentOpinion) -> DeskResearchReport:
    """Best-effort reverse adapter for migration."""
    return DeskResearchReport(
        role_key=opinion.role_key or "unknown",
        role_label=opinion.role_label or "Unknown Desk",
        model=opinion.model,
        key_findings=[s.analysis for s in opinion.reasoning_steps[:3]],
        metrics={},
        risks=opinion.key_risks,
        invalidators=opinion.invalidators,
        analytical_view=opinion.stance,
        confidence_in_analysis=opinion.confidence,
        reasoning_steps=opinion.reasoning_steps,
        provider_attempts=opinion.provider_attempts,
        error=opinion.error,
    )
