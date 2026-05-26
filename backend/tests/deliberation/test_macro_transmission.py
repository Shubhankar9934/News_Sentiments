"""Tests for the macro transmission chain (Phase 6)."""

from __future__ import annotations

from app.services.deliberation.context.macro_transmission import (
    build_macro_transmission_chain,
)
from app.services.explainability.macro_transmission_explain import (
    build_macro_transmission,
)


def test_iran_peace_yields_supportive_chain():
    chain = build_macro_transmission_chain(
        ticker="SPY",
        dominant_narrative="Iran peace deal announced; ceasefire holding.",
        key_events=[],
        event_risk_drivers=[],
    )
    assert chain is not None
    assert chain["primary_shock"] == "iran_peace"
    assert chain["ticker_impact"] == "supportive"
    labels = [node["label"] for node in chain["chain"]]
    assert "Oil Down" in labels
    assert any("Supportive" in label for label in labels)


def test_iran_conflict_yields_bearish_chain():
    chain = build_macro_transmission_chain(
        ticker="SPY",
        dominant_narrative="Iran conflict escalating; missile strike on Strait of Hormuz.",
        key_events=[],
        event_risk_drivers=[],
    )
    assert chain is not None
    assert chain["primary_shock"] == "iran_conflict"
    assert chain["ticker_impact"] == "bearish"


def test_no_shock_returns_none():
    chain = build_macro_transmission_chain(
        ticker="SPY",
        dominant_narrative="Calm tape, no major catalysts pending.",
        key_events=[],
        event_risk_drivers=[],
    )
    assert chain is None


def test_fed_hawkish_classified():
    chain = build_macro_transmission_chain(
        ticker="SPY",
        dominant_narrative=None,
        key_events=[
            {
                "event_type": "FOMC",
                "title": "Powell hawkish on rates higher for longer",
            }
        ],
        event_risk_drivers=["FOMC"],
    )
    assert chain is not None
    assert chain["primary_shock"] == "fed_hawkish"


def test_builder_uses_report_when_dil_layer_absent():
    out = build_macro_transmission(
        ticker="SPY",
        report={"dominant_narrative": "Iran peace deal announced"},
        deliberation_layer=None,
    )
    assert out is not None
    assert out.ticker_impact == "supportive"
    assert len(out.chain) > 0


def test_builder_returns_none_when_no_chain():
    out = build_macro_transmission(
        ticker="SPY",
        report={"dominant_narrative": "Boring day"},
        deliberation_layer=None,
    )
    assert out is None
