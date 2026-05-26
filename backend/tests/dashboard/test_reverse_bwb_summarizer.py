"""Deterministic-fallback tests for the legacy ReverseBwbSummarizer.

The summarizer no longer calls an LLM. It wraps the deterministic
``summary_projector`` and emits a ``ReverseBwbSummary`` that satisfies
the narrowed ``Enter / Wait / Avoid`` decision + ``Poor / Average /
Good`` IV / liquidity vocabulary. These tests exercise the projector
glue and config gates.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.config import Settings
from app.services.dashboard.reverse_bwb_summarizer import (
    ReverseBwbSummarizer,
    ReverseBwbSummaryError,
)


def _settings(enabled: bool = True) -> Settings:
    return Settings(
        ANTHROPIC_API_KEY="dummy",
        REVERSE_BWB_SUMMARY_ENABLED=enabled,
    )


@pytest.mark.asyncio
async def test_deterministic_summary_uses_new_vocabulary(sample_report: dict[str, Any]):
    summarizer = ReverseBwbSummarizer(_settings())
    out = await summarizer.summarize("NVDA", sample_report)

    assert out.ticker == "NVDA"
    assert out.decision in {"Enter", "Wait", "Avoid"}
    assert out.risk in {"Low", "Medium", "High"}
    assert out.confidence in {"Low", "Medium", "High"}
    assert out.iv_quality in {"Poor", "Average", "Good"}
    assert out.liquidity in {"Poor", "Average", "Good"}
    assert out.today_outlook in {"Bullish", "Bearish", "Sideways", "Choppy"}
    assert out.next_3d_outlook in {
        "Bullish",
        "Bearish",
        "Sideways",
        "Volatile",
    }
    assert out.chance_up_2_3_pct in {"Low", "Medium", "High"}
    assert out.chance_down_2_3_pct in {"Low", "Medium", "High"}
    assert 3 <= len(out.actual_dynamics_summary) <= 4


@pytest.mark.asyncio
async def test_summary_stable_across_runs(sample_report: dict[str, Any]):
    """Deterministic ⇒ identical output for identical inputs."""

    s1 = await ReverseBwbSummarizer(_settings()).summarize("NVDA", sample_report)
    s2 = await ReverseBwbSummarizer(_settings()).summarize("NVDA", sample_report)
    assert s1.model_dump() == s2.model_dump()


@pytest.mark.asyncio
async def test_disabled_via_settings_raises(sample_report: dict[str, Any]):
    summarizer = ReverseBwbSummarizer(_settings(enabled=False))
    with pytest.raises(ReverseBwbSummaryError):
        await summarizer.summarize("NVDA", sample_report)


@pytest.mark.asyncio
async def test_decision_follows_credit_safety_score():
    """Score >= 7 → Enter; 4..7 → Wait; else Avoid."""

    summarizer = ReverseBwbSummarizer(_settings())
    base: dict[str, Any] = {
        "ticker": "SPY",
        "options_intelligence": {
            "last_close": 100.0,
            "expected_range": {
                "low": 97.0,
                "high": 103.0,
                "sigma_pct": 1.5,
            },
            "horizon_days": 3,
            "credit_safety": {"score": 8.5, "label": "SAFE"},
        },
        "_pipeline_meta": {
            "price_snapshot": {"last_close": 100.0, "daily_change_pct": 0.0},
        },
    }
    assert (await summarizer.summarize("SPY", base)).decision == "Enter"

    base["options_intelligence"]["credit_safety"]["score"] = 5.0
    assert (await summarizer.summarize("SPY", base)).decision == "Wait"

    base["options_intelligence"]["credit_safety"]["score"] = 2.0
    assert (await summarizer.summarize("SPY", base)).decision == "Avoid"
