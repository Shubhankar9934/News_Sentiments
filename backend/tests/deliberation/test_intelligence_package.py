"""Tests for intelligence package builder."""

from app.services.deliberation.intelligence.package_builder import build_intelligence_package
from app.services.deliberation.schemas import DeskResearchReport


def test_build_intelligence_package():
    report = {
        "options_intelligence": {
            "credit_safety": {"score": 8.0, "label": "SAFE"},
            "reverse_bwb": {"suitable": True},
            "expected_range": {"low": 100, "high": 110},
        }
    }
    desk_reports = {
        "options_desk": DeskResearchReport(
            role_key="options_desk",
            role_label="Options Desk",
            model="groq",
            key_findings=["IV elevated"],
            analytical_view="neutral",
            confidence_in_analysis=0.7,
        )
    }
    pkg = build_intelligence_package(
        "AAPL",
        "Should we enter?",
        "reverse_bwb",
        desk_reports,
        report,
    )
    assert pkg.ticker == "AAPL"
    assert pkg.question == "Should we enter?"
    assert "options_desk" in pkg.desks
    assert pkg.credit_safety.get("score") == 8.0
    assert pkg.options_snapshot.get("reverse_bwb") == {"suitable": True}
