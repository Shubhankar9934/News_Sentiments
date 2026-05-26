"""Deterministic Reverse BWB summarizer (legacy fallback).

The trader-spec ownership model puts the Reverse BWB Assessment Team in
charge of every card field except ``decision`` and the 5-member Decision
Council in charge of ``Enter / Wait / Avoid``. This module is the
fallback when neither the Assessment Team nor the Council can run
(missing API keys, all providers down, ``dil_enabled=false``).

It composes:

  * ``summary_projector.project_assessment_consensus`` — deterministic
    AssessmentConsensus body from the options-intelligence block.
  * ``summary_projector.fallback_decision_from_consensus`` — Enter /
    Wait / Avoid from the credit-safety score + risk bucket.

Together they emit the same strict ``ReverseBwbSummary`` contract the
LLM-based version used to return. There is no longer an LLM call here.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.core.config import Settings
from app.services.dashboard.schemas import ReverseBwbSummary
from app.services.dashboard.summary_projector import (
    fallback_decision_from_consensus,
    project_assessment_consensus,
)

log = structlog.get_logger(__name__)


class ReverseBwbSummaryError(RuntimeError):
    """Raised when the deterministic projector cannot satisfy the schema."""


class ReverseBwbSummarizer:
    """Deterministic Reverse BWB summarizer used as the legacy fallback."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def summarize(self, ticker: str, report: dict[str, Any]) -> ReverseBwbSummary:
        if not self._settings.reverse_bwb_summary_enabled:
            raise ReverseBwbSummaryError("Reverse BWB summary disabled by config")

        try:
            consensus = project_assessment_consensus(ticker, report)
        except Exception as exc:
            log.exception("reverse_bwb.deterministic_failed", ticker=ticker)
            raise ReverseBwbSummaryError(
                f"Deterministic projector failed: {exc}"
            ) from exc

        decision = fallback_decision_from_consensus(consensus)
        log.info(
            "reverse_bwb.deterministic_summary",
            ticker=ticker,
            decision=decision,
            credit_safety_score=consensus.credit_safety_score,
        )
        return _merge(ticker.upper(), consensus, decision)


def _merge(
    ticker: str,
    consensus: Any,
    decision: str,
) -> ReverseBwbSummary:
    return ReverseBwbSummary(
        ticker=ticker,
        decision=decision,  # type: ignore[arg-type]
        credit_safety_score=consensus.credit_safety_score,
        risk=consensus.risk,
        confidence=consensus.confidence,
        today_outlook=consensus.today_outlook,
        next_3d_outlook=consensus.next_3d_outlook,
        chance_up_2_3_pct=consensus.chance_up_2_3_pct,
        chance_down_2_3_pct=consensus.chance_down_2_3_pct,
        expected_range_today=consensus.expected_range_today,
        expected_range_next_3d=consensus.expected_range_next_3d,
        danger_zone=consensus.danger_zone,
        pin_risk=consensus.pin_risk,
        event_risk=consensus.event_risk,
        iv_quality=consensus.iv_quality,
        liquidity=consensus.liquidity,
        actual_dynamics_summary=consensus.actual_dynamics_summary,
    )
