"""Acceptance test: explainability layer never alters the frozen card.

This is the contractual proof that the explainability rollout is
purely additive. The test:

1. Builds a sample report + deliberation layer.
2. Builds a ReverseBwbSummary (card body) with explainability disabled.
3. Runs the full :class:`ExplainabilityAssembler` against the same
   inputs.
4. Builds the same ReverseBwbSummary again (explainability present).
5. Asserts both summaries are byte-for-byte identical.

Any drift here means the assembler is mutating ``report`` in place or
the card builder is reading from a field the assembler wrote — both of
which would violate the "card frozen" guarantee.
"""

from __future__ import annotations

import json

import pytest

from app.services.dashboard.schemas import (
    AssessmentConsensus,
    ExpectedRange,
    ExplainabilityLayer,
    ReverseBwbSummary,
)
from app.services.dashboard.summary_projector import (
    fallback_decision_from_consensus,
    project_assessment_consensus,
)
from app.services.explainability import assemble_explainability


@pytest.fixture
def deliberation_layer():
    return {
        "consensus": {
            "calibration": {
                "confidence_aggregate": 0.7,
                "consensus_strength": 0.6,
                "evidence_quality": 0.55,
            }
        },
        "metrics": {"contradiction_density": 0.2},
        "council_layer": {
            "round1": {
                "portfolio_manager": {
                    "model": "gpt",
                    "council_role": "portfolio_manager",
                    "council_label": "Portfolio Manager",
                    "decision": "WAIT",
                    "confidence": 0.65,
                    "reasoning_steps": [
                        {
                            "step": 1,
                            "title": "Body placement is acceptable",
                            "analysis": "Body sits 1σ away from spot.",
                        }
                    ],
                    "key_risks": ["pin risk"],
                }
            },
            "consensus": {
                "decision": "WAIT",
                "support": {"WAIT": 1},
                "confidence": 0.65,
                "main_conflict": "edge clarity vs timing",
            },
        },
        "assessment_layer": {
            "round1": {
                "openai_assessment_analyst": {
                    "assessment_label": "OpenAI Assessment Analyst",
                    "risk_lenses": {"ticker_risk": "SPY is broadly liquid."},
                }
            }
        },
        "mapped_decision": "Wait",
    }


def _build_card(report: dict, layer: dict | None) -> ReverseBwbSummary:
    """Mini reimplementation of WatchlistBatchService._build_summary's path.

    The full path requires a DB session; we exercise the deterministic
    projector + decision fallback here because the explainability
    assembler is the only thing under test.
    """

    consensus: AssessmentConsensus | None = None
    if layer:
        raw_consensus = (layer.get("assessment_layer") or {}).get("consensus")
        if raw_consensus:
            try:
                consensus = AssessmentConsensus.model_validate(raw_consensus)
            except Exception:
                consensus = None
    if consensus is None:
        consensus = project_assessment_consensus("SPY", report)

    decision = None
    if layer:
        if layer.get("mapped_decision"):
            decision = layer["mapped_decision"]
        else:
            raw = ((layer.get("council_layer") or {}).get("consensus") or {}).get(
                "decision"
            )
            if raw:
                from app.services.deliberation.decision_labels import (
                    council_to_dashboard,
                )

                decision = council_to_dashboard(raw)
    if not decision:
        decision = fallback_decision_from_consensus(consensus)

    return ReverseBwbSummary(
        ticker="SPY",
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
        actual_dynamics_summary=list(consensus.actual_dynamics_summary),
    )


def test_card_byte_identical_with_and_without_explainability(
    sample_report, deliberation_layer
):
    # Build the card with explainability disabled.
    baseline_report = json.loads(json.dumps(sample_report))
    baseline_card = _build_card(baseline_report, deliberation_layer)

    # Build the card after running the explainability assembler.
    enriched_report = json.loads(json.dumps(sample_report))
    summary_for_assembler = _build_card(enriched_report, deliberation_layer)
    explain_layer = assemble_explainability(
        ticker="SPY",
        report=enriched_report,
        deliberation_layer=deliberation_layer,
        summary=summary_for_assembler,
    )
    assert isinstance(explain_layer, ExplainabilityLayer)
    enriched_report["explainability"] = explain_layer.model_dump(
        mode="json", exclude_none=True
    )
    enriched_card = _build_card(enriched_report, deliberation_layer)

    assert baseline_card.model_dump() == enriched_card.model_dump()


def test_explainability_layer_has_at_least_one_block(
    sample_report, deliberation_layer
):
    summary = _build_card(sample_report, deliberation_layer)
    layer = assemble_explainability(
        ticker="SPY",
        report=sample_report,
        deliberation_layer=deliberation_layer,
        summary=summary,
    )
    populated = [
        getattr(layer, slot)
        for slot in (
            "credit_safety_breakdown",
            "confidence_calibration",
            "liquidity_assessment",
            "structure_analysis",
            "position_risk",
            "macro_transmission",
            "historical_analogs",
            "assessment_reasoning",
            "decision_justification",
        )
    ]
    assert any(p is not None for p in populated)


def test_explainability_layer_dump_is_jsonable(
    sample_report, deliberation_layer
):
    summary = _build_card(sample_report, deliberation_layer)
    layer = assemble_explainability(
        ticker="SPY",
        report=sample_report,
        deliberation_layer=deliberation_layer,
        summary=summary,
    )
    dumped = layer.model_dump(mode="json", exclude_none=True)
    json.dumps(dumped)  # must round-trip without raising
