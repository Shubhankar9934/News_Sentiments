"""MarginEngine tests.

The engine has three contracts:
    1. Every row gets the deterministic margin estimate.
    2. The top-N rows per side (sorted by ranking_score) get refined via
       a WhatIf round-trip.
    3. The WhatIf budget is a sliding 60-second window — once exhausted,
       the rest of the rows keep their deterministic value.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services.market_data.margin_engine import (
    MarginEngine,
    MarginRequest,
    WhatIfBudget,
    deterministic_margin,
)


def _settings(top_n: int = 2, per_min: int = 10) -> Settings:
    return Settings(
        OPP_WHATIF_TOP_N=top_n,
        OPP_WHATIF_MAX_PER_MIN=per_min,
    )


def _req(
    *,
    side: str,
    score: float,
    wing_left: float = 5.0,
    wing_right: float = 5.0,
    leg_ids: tuple[int, int, int] = (1, 2, 3),
) -> MarginRequest:
    return MarginRequest(
        side=side,
        combo="750/755/760",
        wing_left=wing_left,
        wing_right=wing_right,
        leg_con_ids=leg_ids,
        ranking_score=score,
    )


def test_deterministic_margin_uses_wider_wing() -> None:
    assert deterministic_margin(wing_left=5.0, wing_right=10.0) == pytest.approx(
        10.0 * 100 * 1.05
    )


class _StubMarketData:
    def __init__(self, init_margin: float | None = 480.0) -> None:
        self.calls = 0
        self.init_margin = init_margin

    async def what_if_margin(self, legs):
        self.calls += 1
        if self.init_margin is None:
            return None
        from app.services.market_data.market_data_service import WhatIfResult

        return WhatIfResult(init_margin=self.init_margin, maint_margin=420.0)


@pytest.mark.asyncio
async def test_deterministic_for_all_rows_when_budget_zero() -> None:
    engine = MarginEngine(
        settings=_settings(top_n=5, per_min=0),
        market_data=_StubMarketData(),  # type: ignore[arg-type]
    )
    requests = [
        _req(side="call", score=0.5),
        _req(side="call", score=0.7),
        _req(side="put", score=0.6),
    ]
    results = await engine.compute_batch(requests)
    assert all(r.source == "deterministic" for r in results)
    assert all(r.init_margin > 0 for r in results)


@pytest.mark.asyncio
async def test_whatif_refines_top_n_per_side() -> None:
    md = _StubMarketData(init_margin=480.0)
    engine = MarginEngine(
        settings=_settings(top_n=1, per_min=10),
        market_data=md,  # type: ignore[arg-type]
    )
    requests = [
        _req(side="call", score=0.5),  # not refined
        _req(side="call", score=0.9),  # refined
        _req(side="put", score=0.4),   # not refined
        _req(side="put", score=0.8),   # refined
    ]
    results = await engine.compute_batch(requests)
    assert md.calls == 2  # one per side
    sources = [r.source for r in results]
    # The two highest-score rows (idx 1 and idx 3) should be the whatif ones.
    assert sources[1] == "whatif"
    assert sources[3] == "whatif"
    assert sources[0] == "deterministic"
    assert sources[2] == "deterministic"
    assert results[1].init_margin == pytest.approx(480.0)


@pytest.mark.asyncio
async def test_whatif_failure_falls_back_to_deterministic() -> None:
    md = _StubMarketData(init_margin=None)
    engine = MarginEngine(
        settings=_settings(top_n=2, per_min=10),
        market_data=md,  # type: ignore[arg-type]
    )
    requests = [_req(side="call", score=0.9), _req(side="put", score=0.8)]
    results = await engine.compute_batch(requests)
    assert all(r.source == "deterministic" for r in results)
    assert md.calls == 2


@pytest.mark.asyncio
async def test_whatif_budget_enforces_per_minute_cap() -> None:
    budget = WhatIfBudget(max_per_min=2)
    assert await budget.acquire() is True
    assert await budget.acquire() is True
    assert await budget.acquire() is False
    assert await budget.remaining() == 0


@pytest.mark.asyncio
async def test_engine_handles_empty_request_set() -> None:
    engine = MarginEngine(
        settings=_settings(),
        market_data=_StubMarketData(),  # type: ignore[arg-type]
    )
    assert await engine.compute_batch([]) == []
