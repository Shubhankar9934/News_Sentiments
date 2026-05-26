"""Composes the ``report_json.explainability`` payload from existing layers.

The assembler is a pure orchestrator: it pulls data already on the
research report + deliberation layer + options-intelligence block, runs
each phase builder, and produces an :class:`ExplainabilityLayer`. No
LLM calls are made here; the assessment / council layers are read as-is
from the report.

Every sub-block is best-effort: a single builder failing only nulls
its own slot and the rest of the layer still renders.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from app.services.dashboard.schemas import (
    EXPLAINABILITY_LAYER_VERSION,
    ExplainabilityLayer,
    ReverseBwbSummary,
)

log = structlog.get_logger(__name__)


class ExplainabilityAssembler:
    """Single entry point for building the explainability payload.

    Stateless — instantiated per refresh by the watchlist batch.
    """

    def build(
        self,
        *,
        ticker: str,
        report: dict[str, Any],
        deliberation_layer: dict[str, Any] | None,
        summary: ReverseBwbSummary | None,
    ) -> ExplainabilityLayer:
        layer = ExplainabilityLayer(
            version=EXPLAINABILITY_LAYER_VERSION,
            generated_at=datetime.now(UTC),
        )

        options_intel = report.get("options_intelligence") if isinstance(report, dict) else None

        layer.credit_safety_breakdown = self._safe(
            "credit_safety_breakdown",
            self._build_credit_safety_breakdown,
            ticker=ticker,
            report=report,
            options_intel=options_intel,
            summary=summary,
        )

        layer.confidence_calibration = self._safe(
            "confidence_calibration",
            self._build_confidence_calibration,
            ticker=ticker,
            deliberation_layer=deliberation_layer,
            summary=summary,
        )

        layer.liquidity_assessment = self._safe(
            "liquidity_assessment",
            self._build_liquidity_assessment,
            ticker=ticker,
            report=report,
            options_intel=options_intel,
            deliberation_layer=deliberation_layer,
            summary=summary,
        )

        layer.structure_analysis = self._safe(
            "structure_analysis",
            self._build_structure_analysis,
            ticker=ticker,
            options_intel=options_intel,
            deliberation_layer=deliberation_layer,
        )

        layer.position_risk = self._safe(
            "position_risk",
            self._build_position_risk,
            ticker=ticker,
            options_intel=options_intel,
        )

        layer.macro_transmission = self._safe(
            "macro_transmission",
            self._build_macro_transmission,
            ticker=ticker,
            report=report,
            deliberation_layer=deliberation_layer,
        )

        layer.historical_analogs = self._safe(
            "historical_analogs",
            self._build_historical_analogs,
            ticker=ticker,
            report=report,
        )

        layer.assessment_reasoning = self._safe(
            "assessment_reasoning",
            self._build_assessment_reasoning,
            ticker=ticker,
            deliberation_layer=deliberation_layer,
        )

        layer.decision_justification = self._safe(
            "decision_justification",
            self._build_decision_justification,
            ticker=ticker,
            deliberation_layer=deliberation_layer,
            summary=summary,
        )

        layer.decision_sensitivity = self._safe(
            "decision_sensitivity",
            self._build_decision_sensitivity,
            ticker=ticker,
            report=report,
            deliberation_layer=deliberation_layer,
            summary=summary,
        )

        return layer

    # ------------------------------------------------------------------
    # Failure isolation — a single builder error never breaks the layer.
    # ------------------------------------------------------------------

    @staticmethod
    def _safe(slot: str, fn, **kwargs):  # type: ignore[no-untyped-def]
        try:
            return fn(**kwargs)
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("explainability.builder_failed", slot=slot, error=str(exc))
            return None

    # ------------------------------------------------------------------
    # Phase builders are imported lazily so a missing import never
    # cascades into the whole layer being skipped.
    # ------------------------------------------------------------------

    def _build_credit_safety_breakdown(self, **kwargs):  # type: ignore[no-untyped-def]
        from app.services.explainability.credit_safety_breakdown import (
            build_credit_safety_breakdown,
        )

        return build_credit_safety_breakdown(**kwargs)

    def _build_confidence_calibration(self, **kwargs):  # type: ignore[no-untyped-def]
        from app.services.deliberation.scoring.confidence_explain import (
            build_confidence_calibration,
        )

        return build_confidence_calibration(**kwargs)

    def _build_liquidity_assessment(self, **kwargs):  # type: ignore[no-untyped-def]
        from app.services.explainability.liquidity_assessment import (
            build_liquidity_assessment,
        )

        return build_liquidity_assessment(**kwargs)

    def _build_structure_analysis(self, **kwargs):  # type: ignore[no-untyped-def]
        from app.services.explainability.structure_analysis import (
            build_structure_analysis,
        )

        return build_structure_analysis(**kwargs)

    def _build_position_risk(self, **kwargs):  # type: ignore[no-untyped-def]
        from app.services.explainability.position_risk_explain import (
            build_position_risk_explain,
        )

        return build_position_risk_explain(**kwargs)

    def _build_macro_transmission(self, **kwargs):  # type: ignore[no-untyped-def]
        from app.services.explainability.macro_transmission_explain import (
            build_macro_transmission,
        )

        return build_macro_transmission(**kwargs)

    def _build_historical_analogs(self, **kwargs):  # type: ignore[no-untyped-def]
        from app.services.explainability.historical_analogs_explain import (
            build_historical_analogs_explain,
        )

        return build_historical_analogs_explain(**kwargs)

    def _build_assessment_reasoning(self, **kwargs):  # type: ignore[no-untyped-def]
        from app.services.explainability.assessment_reasoning import (
            build_assessment_reasoning,
        )

        return build_assessment_reasoning(**kwargs)

    def _build_decision_justification(self, **kwargs):  # type: ignore[no-untyped-def]
        from app.services.deliberation.council.justification import (
            build_decision_justification,
        )

        return build_decision_justification(**kwargs)

    def _build_decision_sensitivity(self, **kwargs):  # type: ignore[no-untyped-def]
        from app.services.explainability.decision_sensitivity import (
            build_decision_sensitivity,
        )

        return build_decision_sensitivity(**kwargs)


def assemble_explainability(
    *,
    ticker: str,
    report: dict[str, Any],
    deliberation_layer: dict[str, Any] | None,
    summary: ReverseBwbSummary | None,
) -> ExplainabilityLayer:
    """Convenience function used by the watchlist batch."""

    return ExplainabilityAssembler().build(
        ticker=ticker,
        report=report,
        deliberation_layer=deliberation_layer,
        summary=summary,
    )
