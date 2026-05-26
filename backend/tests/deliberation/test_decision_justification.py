"""Tests for the decision justification builder (Phase 9)."""

from __future__ import annotations

from app.services.deliberation.council.justification import (
    build_decision_justification,
)


def _make_layer():
    return {
        "council_layer": {
            "round1": {
                "portfolio_manager": {
                    "model": "gpt",
                    "council_role": "portfolio_manager",
                    "council_label": "Portfolio Manager",
                    "decision": "AVOID",
                    "confidence": 0.72,
                    "reasoning_steps": [
                        {
                            "step": 1,
                            "title": "Elevated pin risk and poor body placement",
                            "analysis": "Body sits at the gamma pin.",
                        }
                    ],
                    "key_risks": ["pin risk", "poor body placement"],
                },
                "risk_manager": {
                    "model": "claude",
                    "council_role": "risk_manager",
                    "council_label": "Risk Manager",
                    "decision": "WAIT",
                    "confidence": 0.55,
                    "reasoning_steps": [
                        {
                            "step": 1,
                            "title": "Event uncertainty around FOMC",
                            "analysis": "Two binary events in window.",
                        }
                    ],
                    "key_risks": ["event uncertainty"],
                },
                "market_strategist": {
                    "model": "gemini",
                    "council_role": "market_strategist",
                    "council_label": "Market Strategist",
                    "decision": "AVOID",
                    "confidence": 0.66,
                    "reasoning_steps": [],
                    "key_risks": ["weak credit efficiency"],
                },
            },
            "round3": {
                "portfolio_manager": {
                    "revised_decision": "AVOID",
                    "revised_confidence": 0.78,
                    "revision_rationale": "Stronger pin risk read after critique",
                }
            },
            "consensus": {
                "decision": "AVOID",
                "support": {"AVOID": 2, "WAIT": 1},
                "confidence": 0.7,
                "main_conflict": "edge clarity vs timing",
            },
        },
        "mapped_decision": "Avoid",
    }


def test_decision_justification_extracts_votes():
    layer = _make_layer()
    out = build_decision_justification(
        ticker="SPY", deliberation_layer=layer, summary=None
    )
    assert out is not None
    assert out.consensus_decision == "AVOID"
    assert len(out.council_votes) == 3
    labels = [v.label for v in out.council_votes]
    assert "Portfolio Manager" in labels
    # primary reasons should include "pin risk" and "event uncertainty"
    themes = set(out.primary_reasons)
    assert "pin risk" in themes
    assert "event uncertainty" in themes


def test_decision_justification_dissent():
    layer = _make_layer()
    out = build_decision_justification(
        ticker="SPY", deliberation_layer=layer, summary=None
    )
    assert out is not None
    assert any("Risk Manager" in d for d in out.dissent)


def test_decision_justification_returns_none_without_layer():
    out = build_decision_justification(
        ticker="SPY", deliberation_layer=None, summary=None
    )
    assert out is None


def test_revised_decision_overrides_round1():
    layer = _make_layer()
    out = build_decision_justification(
        ticker="SPY", deliberation_layer=layer, summary=None
    )
    pm = next(v for v in out.council_votes if v.label == "Portfolio Manager")
    # Revised confidence should win over round1 confidence
    assert pm.confidence == 0.78
