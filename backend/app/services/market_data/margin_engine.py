"""Margin engine for Reverse BWB opportunities.

Two-tier margin computation that fits within IBKR's WhatIf pacing
budget (~10-20 round-trips per minute sustainable):

    1. Deterministic margin for ALL rows.
       ``init_margin = (WiderWing - NarrowerWing - Credit) * 100``
       This is the exact max theoretical loss of a Broken Wing Butterfly:
       the wider side caps the loss; the narrower wing and the credit
       received both reduce it. ``max(..., 0)`` guards the debit case.

    2. WhatIf refinement for the top-N ranked rows per side per ticker.
       Limited by ``OPP_WHATIF_TOP_N`` and a per-minute throttle
       (``OPP_WHATIF_MAX_PER_MIN``). The ``init_margin_source`` column
       reports which path produced each row so the UI can flag rows
       still on the deterministic estimate.

The engine never raises — every IBKR error is logged and the row keeps
its deterministic value. Callers should not branch on engine failure.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import structlog

from app.core.config import Settings
from app.services.market_data.market_data_service import (
    ComboLeg,
    MarketDataService,
)

log = structlog.get_logger(__name__)


@dataclass
class MarginRequest:
    """One row's input to the margin engine."""

    # Identity (carried through so callers can re-attach the result without
    # depending on list-position ordering).
    side: str  # "call" | "put"
    combo: str
    wing_left: float  # |body - long_wing_a|
    wing_right: float  # |long_wing_b - body|
    # Contract IDs in the order (long_wing_a, short_body, long_wing_b).
    leg_con_ids: tuple[int | None, int | None, int | None]
    # Pre-computed deterministic ranking score so the engine can decide
    # which rows deserve a WhatIf round-trip.
    ranking_score: float
    # Net per-share premium (negative = credit). Used by deterministic_margin.
    premium_per_share: float = 0.0


@dataclass
class MarginResult:
    init_margin: float
    maint_margin: float | None
    source: str  # "deterministic" | "whatif"


def deterministic_margin(
    *, wing_left: float, wing_right: float, premium_per_share: float = 0.0
) -> float:
    """Closed-form BWB margin = (WiderWing - NarrowerWing - Credit) × 100.

    For a Broken Wing Butterfly the maximum theoretical loss is the
    difference between the wider and the narrower wing widths, reduced by
    any credit received.  Both inputs are in strike-point dollars; the
    ×100 multiplier converts to per-contract dollars.
    """
    wider = max(float(wing_left), float(wing_right))
    narrower = min(float(wing_left), float(wing_right))
    credit = abs(min(float(premium_per_share), 0.0))  # 0 for debit combos
    max_loss = max(wider - narrower - credit, 0.0)
    return round(max_loss * 100.0, 2)


class WhatIfBudget:
    """Per-minute sliding window throttle for IBKR WhatIf orders.

    IBKR pacing-violates aggressively if WhatIf submissions burst — this
    enforces a soft cap so the worker never trips the 1/sec floor.
    """

    def __init__(self, max_per_min: int) -> None:
        self._max = max(0, int(max_per_min))
        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()

    @property
    def max_per_min(self) -> int:
        return self._max

    async def remaining(self) -> int:
        async with self._lock:
            self._prune()
            return max(0, self._max - len(self._timestamps))

    async def acquire(self) -> bool:
        async with self._lock:
            self._prune()
            if self._max <= 0:
                return False
            if len(self._timestamps) >= self._max:
                return False
            self._timestamps.append(time.monotonic())
            return True

    def _prune(self) -> None:
        cutoff = time.monotonic() - 60.0
        self._timestamps = [t for t in self._timestamps if t > cutoff]


class MarginEngine:
    """Two-tier margin computation: deterministic for all + WhatIf top-N."""

    def __init__(
        self,
        *,
        settings: Settings,
        market_data: MarketDataService,
        budget: WhatIfBudget | None = None,
    ) -> None:
        self._settings = settings
        self._market_data = market_data
        self._budget = budget or WhatIfBudget(settings.opp_whatif_max_per_min)

    @property
    def budget(self) -> WhatIfBudget:
        return self._budget

    async def compute_batch(
        self,
        requests: list[MarginRequest],
    ) -> list[MarginResult]:
        """Compute margin for every row, refining the top-N via WhatIf.

        ``requests`` may contain CALL and PUT rows mixed — the engine
        sorts by ``ranking_score`` and only refines the global top-N per
        side, capped by the remaining WhatIf budget.
        """
        if not requests:
            return []

        # 1. Seed everything with the deterministic value.
        results: list[MarginResult] = [
            MarginResult(
                init_margin=deterministic_margin(
                    wing_left=req.wing_left,
                    wing_right=req.wing_right,
                    premium_per_share=req.premium_per_share,
                ),
                maint_margin=None,
                source="deterministic",
            )
            for req in requests
        ]

        # 2. Pick the WhatIf candidates: top-N per side by ranking_score.
        top_n = max(0, int(self._settings.opp_whatif_top_n))
        if top_n <= 0 or self._budget.max_per_min <= 0:
            return results

        idxs_by_side: dict[str, list[int]] = {"call": [], "put": []}
        for i, req in enumerate(requests):
            idxs_by_side.setdefault(req.side, []).append(i)

        whatif_idxs: list[int] = []
        for side, idxs in idxs_by_side.items():
            idxs.sort(key=lambda i: requests[i].ranking_score, reverse=True)
            whatif_idxs.extend(idxs[:top_n])

        # 3. Issue WhatIf orders within the per-minute budget.
        refined = 0
        failed = 0
        for idx in whatif_idxs:
            if not await self._budget.acquire():
                log.info(
                    "margin_engine.whatif.budget_exhausted",
                    remaining=await self._budget.remaining(),
                )
                break
            req = requests[idx]
            margin_result = await self._whatif_one(req)
            if margin_result is None:
                failed += 1
                continue
            results[idx] = margin_result
            refined += 1

        log.info(
            "margin_engine.batch_complete",
            total=len(requests),
            whatif_attempts=len(whatif_idxs),
            whatif_refined=refined,
            whatif_failed=failed,
        )
        return results

    # ------------------------------------------------------------------ private
    async def _whatif_one(self, req: MarginRequest) -> MarginResult | None:
        leg_a, leg_b, leg_c = req.leg_con_ids
        if leg_a is None or leg_b is None or leg_c is None:
            return None

        # Reverse BWB legs: BUY wing A, SELL body x2, BUY wing B.
        legs = [
            ComboLeg(con_id=int(leg_a), ratio=1, action="BUY"),
            ComboLeg(con_id=int(leg_b), ratio=2, action="SELL"),
            ComboLeg(con_id=int(leg_c), ratio=1, action="BUY"),
        ]
        try:
            result = await self._market_data.what_if_margin(legs)
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("margin_engine.whatif.exception", error=str(exc))
            return None
        if result is None or result.init_margin is None:
            return None
        return MarginResult(
            init_margin=float(result.init_margin),
            maint_margin=(
                float(result.maint_margin)
                if result.maint_margin is not None
                else None
            ),
            source="whatif",
        )
