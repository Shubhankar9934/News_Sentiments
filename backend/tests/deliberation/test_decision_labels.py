"""Tests for council ↔ dashboard label mapping."""

from app.services.deliberation.decision_labels import (
    council_to_dashboard,
    dashboard_to_council,
)


def test_council_to_dashboard():
    assert council_to_dashboard("ENTER") == "Enter"
    assert council_to_dashboard("WAIT") == "Wait"
    assert council_to_dashboard("AVOID") == "Avoid"
    assert council_to_dashboard("unknown") == "Wait"


def test_dashboard_to_council():
    assert dashboard_to_council("Enter") == "ENTER"
    assert dashboard_to_council("Wait") == "WAIT"
    assert dashboard_to_council("Avoid") == "AVOID"
    # Legacy dashboard labels still round-trip back to the council form.
    assert dashboard_to_council("SAFE") == "ENTER"
    assert dashboard_to_council("WATCH") == "WAIT"
