"""Tests for decision trigger evaluation."""

from app.core.config import Settings
from app.services.deliberation.intelligence.package_builder import build_intelligence_package
from app.services.deliberation.schemas import DeskResearchReport
from app.services.deliberation.triggers.decision_triggers import evaluate_decision_trigger


def _minimal_intel(report: dict):
    return build_intelligence_package(
        "AAPL",
        "test",
        "none",
        {},
        report,
    )


def test_reverse_bwb_trigger():
    report = {
        "options_intelligence": {
            "reverse_bwb": {"suitable": True},
            "credit_safety": {"score": 7.0},
        }
    }
    settings = Settings(dil_council_triggers="reverse_bwb")
    result = evaluate_decision_trigger(report, _minimal_intel(report), settings)
    assert result.should_run_council is True
    assert result.trigger == "reverse_bwb"
    assert "Reverse BWB" in result.question


def test_no_trigger_without_options():
    report = {"options_intelligence": {}}
    settings = Settings(dil_council_triggers="reverse_bwb")
    result = evaluate_decision_trigger(report, _minimal_intel(report), settings)
    assert result.should_run_council is False


def test_ticker_avoidance_trigger():
    report = {
        "options_intelligence": {
            "credit_safety": {"score": 2.5},
            "event_risk": {"level": "low"},
        }
    }
    settings = Settings(dil_council_triggers="ticker_avoidance")
    result = evaluate_decision_trigger(report, _minimal_intel(report), settings)
    assert result.should_run_council is True
    assert result.trigger == "ticker_avoidance"
