"""Projection-level tests for the ``/summaries`` route helpers.

A full end-to-end test of the route requires a live Postgres test DB; the
shape-level guarantees that downstream callers (the React grid) depend on
are concentrated in ``_project_row``, so we test that directly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.api.v1.routes.summaries import _project_row


def _make_row(report_json: dict, *, ticker: str = "NVDA") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        ticker=ticker,
        report_json=report_json,
        created_at=datetime(2026, 5, 24, 14, 33, tzinfo=UTC),
    )


def test_project_row_uses_pre_extracted_summary_if_present():
    row = _make_row(
        {
            "executive_summary": {
                "decision": "SAFE",
                "summary": "All good.",
            },
            "_pipeline_meta": {"price_snapshot": {"last_close": 100.0, "last_session_change_pct": 1.0}},
            "deliberation_layer": {"status": "complete"},
        }
    )
    out = _project_row(row)
    assert out["ticker"] == "NVDA"
    assert out["last_close"] == 100.0
    assert out["session_change_pct"] == 1.0
    assert out["deliberation_status"] == "complete"
    assert out["executive_summary"]["decision"] == "SAFE"
    assert out["last_run_at"].startswith("2026-05-24")


def test_project_row_derives_summary_when_missing():
    """Older reports persisted before this feature still light up the grid."""
    row = _make_row(
        {
            "options_intelligence": {
                "source": "realized_vol",
                "horizon_days": 3,
                "last_close": 100.0,
                "daily_vol_pct": 1.5,
                "expected_range": {"low": 96.0, "high": 104.0, "sigma_pct": 4.0, "confidence": 0.6},
                "move_probabilities": {
                    "p_up_2pct": 0.18,
                    "p_dn_2pct": 0.22,
                    "p_up_3pct": 0.05,
                    "p_dn_3pct": 0.06,
                    "p_in_range_1sigma": 0.68,
                },
                "pin_risk": {
                    "score": 0.2,
                    "label": "Low",
                    "nearest_round": 100.0,
                    "distance_pct": 0.0,
                },
                "body_danger": {
                    "short_body_lo": 99.0,
                    "short_body_hi": 101.0,
                    "distance_pct": 0.5,
                    "label": "Low",
                },
                "event_risk": {"score": 0.3, "label": "Low", "drivers": []},
                "credit_safety": {
                    "score": 7.5,
                    "label": "SAFE",
                    "components": {
                        "prob_block": 0.6,
                        "pin_risk": 0.2,
                        "body_danger": 0.3,
                        "event_risk": 0.3,
                        "vol_regime": 0.5,
                    },
                },
                "reverse_bwb": {
                    "score": 7.0,
                    "label": "SAFE",
                    "suggested_wing_width_pct": 2.5,
                    "suggested_dte": 5,
                    "rationale": "stable",
                },
            },
            "_pipeline_meta": {
                "volatility_regime": "low",
                "price_snapshot": {"last_close": 100.0, "last_session_change_pct": 0.5},
            },
        }
    )
    out = _project_row(row)
    assert out["executive_summary"] is not None
    assert out["executive_summary"]["decision"] == "SAFE"


def test_project_row_handles_missing_meta_gracefully():
    row = _make_row({})
    out = _project_row(row)
    assert out["last_close"] is None
    assert out["session_change_pct"] is None
    assert out["deliberation_status"] is None
    # Empty report still yields a fallback summary (neutrals).
    assert out["executive_summary"] is not None
    assert out["executive_summary"]["decision"] == "WATCH"
