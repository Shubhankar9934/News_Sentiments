"""Sequential ordering + failure-isolation tests for WatchlistBatchService.

The refactored ``_refresh_ticker`` runs:
    pipeline.run(persist=True, schedule_dil=False)
      → DeliberationOrchestrator(...).run(report, ticker)   # optional
      → _build_summary(assessment_layer + council_layer + fallback)
      → DashboardRepository.save_snapshot(... single write)

For tests we disable ``dil_enabled`` so the orchestrator never runs and
``_build_summary`` falls back to the deterministic projector. That keeps
this suite pinned to the deterministic merge path while the LLM stack
is exercised in ``backend/tests/assessment``.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.config import Settings
from app.services.dashboard import watchlist_batch as watchlist_batch_module
from app.services.dashboard.opportunity_generator import PlaceholderOpportunitySource
from app.services.dashboard.schemas import (
    OptionOpportunities,
    ReverseBwbSummary,
)
from app.services.dashboard.watchlist import ALL_WATCHLIST_TICKERS
from app.services.dashboard.watchlist_batch import WatchlistBatchService


def _options_intel(ticker: str) -> dict[str, Any]:
    """Fixture-shaped options intelligence consumed by the projector."""

    return {
        "ticker": ticker,
        "last_close": 100.0,
        "expected_range": {
            "low": 97.0,
            "high": 103.0,
            "sigma_pct": 1.5,
            "confidence": 0.6,
        },
        "horizon_days": 3,
        "credit_safety": {
            "label": "SAFE",
            "score": 7.2,
            "expected_range": {"low": 97.0, "high": 103.0},
        },
        "body": {"low": 99.0, "high": 101.0},
        "pin_risk": {"label": "Low"},
        "danger_zone": {"description": "Body 99-101 holds the structure."},
        "iv_intel": {"iv30": 18.0, "rv20": 14.0, "vol_regime": "low"},
        "liquidity": {"tier": "Good"},
    }


class _FakePipeline:
    """Minimal pipeline stub — returns an options-intelligence-shaped report."""

    instances: list["_FakePipeline"] = []

    def __init__(self, session, settings, qdrant, cache):
        type(self).instances.append(self)
        self.calls: list[tuple[str, bool]] = []

    async def run(
        self,
        ticker: str,
        days: int = 7,
        *,
        persist: bool = True,
        on_progress=None,
        schedule_dil: bool = True,
    ) -> dict[str, Any]:
        self.calls.append((ticker.upper(), schedule_dil))
        return {
            "ticker": ticker,
            "options_intelligence": _options_intel(ticker),
            "_pipeline_meta": {
                "price_snapshot": {"last_close": 100.0, "daily_change_pct": 0.5},
                "report_id": "00000000-0000-0000-0000-000000000123",
            },
        }


class _FakeRepository:
    """Repository stub that captures save_snapshot calls."""

    instances: list["_FakeRepository"] = []

    def __init__(self, _session):
        type(self).instances.append(self)
        self.saved: list[
            tuple[str, ReverseBwbSummary, dict[str, Any] | None, dict[str, Any] | None]
        ] = []
        self.failed: list[tuple[str, str]] = []

    async def save_snapshot(
        self,
        ticker: str,
        report_json: dict[str, Any],
        summary: ReverseBwbSummary,
        opportunities: OptionOpportunities,
        *,
        research_report_id=None,
        assessment_layer: dict[str, Any] | None = None,
        council_layer: dict[str, Any] | None = None,
        explainability: dict[str, Any] | None = None,
    ):
        self.saved.append(
            (ticker.upper(), summary, assessment_layer, council_layer)
        )
        # Explainability accepted but unused by these batch-flow tests;
        # contract is verified separately in
        # tests/dashboard/test_explainability_in_report.py.
        _ = explainability
        return None

    async def mark_failed(self, ticker: str, error_message: str):
        self.failed.append((ticker.upper(), error_message))


class _FakeSessionCtx:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *_args):
        return False


@pytest.fixture
def patched_module(monkeypatch):
    """Patch the symbols the batch service imports at module level."""

    _FakePipeline.instances.clear()
    _FakeRepository.instances.clear()

    monkeypatch.setattr(
        watchlist_batch_module, "ResearchPipelineService", _FakePipeline
    )
    monkeypatch.setattr(watchlist_batch_module, "DashboardRepository", _FakeRepository)
    monkeypatch.setattr(
        watchlist_batch_module, "_session_scope", lambda: _FakeSessionCtx()
    )

    async def _no_redis(_self):
        return None

    async def _noop(_self, _cache):
        return None

    monkeypatch.setattr(WatchlistBatchService, "_build_redis_cache", _no_redis)
    monkeypatch.setattr(WatchlistBatchService, "_dispose_redis_cache", _noop)


def _make_service() -> WatchlistBatchService:
    # ``dil_enabled=False`` keeps the orchestrator out of the loop so the
    # deterministic projector owns the card body in tests.
    return WatchlistBatchService(
        settings=Settings(
            ANTHROPIC_API_KEY="dummy",
            DIL_ENABLED=False,
        ),
        qdrant=None,
        opportunity_source=PlaceholderOpportunitySource(),
    )


@pytest.mark.asyncio
async def test_run_once_processes_tickers_in_tier_order(patched_module):
    service = _make_service()
    status = await service.run_once()

    pipelines = _FakePipeline.instances
    seen = [t for p in pipelines for (t, _) in p.calls]
    assert seen == list(ALL_WATCHLIST_TICKERS)

    # Watchlist batch must always suppress the async DIL kick-off.
    schedule_flags = {flag for p in pipelines for (_, flag) in p.calls}
    assert schedule_flags == {False}

    assert status.state == "completed"
    assert status.completed == list(ALL_WATCHLIST_TICKERS)
    assert status.failed == []
    assert status.current_ticker is None
    assert status.started_at is not None and status.finished_at is not None


@pytest.mark.asyncio
async def test_single_write_per_ticker_with_canonical_decision(patched_module):
    service = _make_service()
    await service.run_single("AAPL")
    await service.wait_idle()

    repos = _FakeRepository.instances
    saves = [s for repo in repos for s in repo.saved]
    assert len(saves) == 1
    ticker, summary, assessment, council = saves[0]
    assert ticker == "AAPL"
    # Without an LLM layer there is no assessment / council JSON to
    # persist — the projector still owns the card body.
    assert assessment is None
    assert council is None
    # Decision vocabulary must be the new Enter / Wait / Avoid set.
    assert summary.decision in {"Enter", "Wait", "Avoid"}
    assert summary.iv_quality in {"Poor", "Average", "Good"}
    assert summary.liquidity in {"Poor", "Average", "Good"}
    assert summary.today_outlook in {
        "Bullish",
        "Bearish",
        "Sideways",
        "Choppy",
    }
    assert summary.next_3d_outlook in {
        "Bullish",
        "Bearish",
        "Sideways",
        "Volatile",
    }


@pytest.mark.asyncio
async def test_run_single_rejects_non_watchlist(patched_module):
    service = _make_service()
    with pytest.raises(ValueError):
        await service.run_single("XYZ")


@pytest.mark.asyncio
async def test_enqueue_multiple_tickers_processes_in_order(patched_module):
    service = _make_service()
    await service.enqueue_ticker("SPY")
    await service.enqueue_ticker("AAPL")
    await service.wait_idle()
    status = service.status

    pipelines = _FakePipeline.instances
    seen = [t for p in pipelines for (t, _) in p.calls]
    assert seen == ["SPY", "AAPL"]
    assert status.completed == ["SPY", "AAPL"]
    assert status.queued == []


@pytest.mark.asyncio
async def test_enqueue_skips_duplicate_tickers(patched_module):
    service = _make_service()
    await service.enqueue_ticker("SPY")
    await service.enqueue_ticker("SPY")
    await service.wait_idle()
    pipelines = _FakePipeline.instances
    seen = [t for p in pipelines for (t, _) in p.calls]
    assert seen == ["SPY"]
