"""Tests for post-council dashboard decision mapping."""

from app.services.deliberation.decision_labels import council_to_dashboard


def test_council_maps_to_dashboard_for_patch():
    assert council_to_dashboard("ENTER") == "Enter"
    assert council_to_dashboard("WAIT") == "Wait"
    assert council_to_dashboard("AVOID") == "Avoid"
