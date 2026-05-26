"""Build unified intelligence package from desk research reports."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.services.deliberation.schemas import DeskResearchReport, IntelligencePackage


def build_intelligence_package(
    ticker: str,
    question: str,
    trigger: str,
    desk_reports: dict[str, DeskResearchReport],
    report: dict[str, Any],
    *,
    assessment_consensus: dict[str, Any] | None = None,
) -> IntelligencePackage:
    oi = report.get("options_intelligence") or {}
    credit = oi.get("credit_safety") or {}
    meta = report.get("_pipeline_meta") or {}
    explain = report.get("explainability") or {}

    options_snapshot: dict[str, Any] = {
        "credit_safety": credit,
        "reverse_bwb": oi.get("reverse_bwb") or {},
        "expected_range": oi.get("expected_range") or {},
        "pin_risk": oi.get("pin_risk") or {},
        "body_danger": oi.get("body_danger") or {},
        "event_risk": oi.get("event_risk") or {},
        "move_probabilities": oi.get("move_probabilities") or {},
        # Phase 4a + 5: new deterministic decompositions used by the
        # Assessment Team and Decision Council.
        "structure_geometry": oi.get("structure_geometry") or {},
        "position_risk": oi.get("position_risk") or {},
    }

    # Phase 7: historical analogs aggregates as a *risk lens* input,
    # not part of the options snapshot per se, but lives here so the
    # assessment round1 message-builder can surface them without us
    # changing the IntelligencePackage schema.
    if meta.get("historical_analog_aggregates") or meta.get("historical_analogs"):
        options_snapshot["historical_analogs"] = {
            "aggregates": meta.get("historical_analog_aggregates") or {},
            "matches": (meta.get("historical_analogs") or [])[:5],
        }

    # Phase 6: macro transmission chain — only the deterministic
    # skeleton, no LLM narrative, so the assessment team can reason
    # about it without prompting the macro_desk LLM in the same call.
    if isinstance(explain, dict) and explain.get("macro_transmission"):
        options_snapshot["macro_transmission"] = explain.get("macro_transmission")

    return IntelligencePackage(
        ticker=ticker,
        question=question,
        trigger=trigger,
        desks=desk_reports,
        options_snapshot=options_snapshot,
        credit_safety=credit,
        built_at=datetime.now(UTC).isoformat(),
        assessment_consensus=assessment_consensus,
    )
