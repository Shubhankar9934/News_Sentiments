"""Tests for desk analysis adapters."""

from app.services.deliberation.analysis.adapters import (
    desk_report_to_opinion,
    opinion_to_desk_report,
)
from app.services.deliberation.schemas import DeskResearchReport, IndependentOpinion


def test_desk_report_to_opinion():
    report = DeskResearchReport(
        role_key="macro_desk",
        role_label="Macro Desk",
        model="gpt",
        key_findings=["Rates stable"],
        analytical_view="bullish",
        confidence_in_analysis=0.8,
        risks=["Fed surprise"],
    )
    op = desk_report_to_opinion(report)
    assert op.stance == "bullish"
    assert op.confidence == 0.8
    assert op.key_risks == ["Fed surprise"]
    assert op.role_key == "macro_desk"


def test_opinion_to_desk_report_roundtrip():
    op = IndependentOpinion(
        model="claude",
        stance="bearish",
        confidence=0.6,
        role_key="fundamental_desk",
        role_label="Fundamental Desk",
        key_risks=["margin pressure"],
    )
    report = opinion_to_desk_report(op)
    assert report.analytical_view == "bearish"
    assert report.confidence_in_analysis == 0.6
