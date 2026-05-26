"""Reverse BWB Trading Workstation opportunity engine.

For each watchlist ticker, this service:

    1. Reads the latest stored ``last_price`` from ``ticker_market_data``.
    2. Pulls the SMART option chain via IBKR ``reqSecDefOptParams``.
    3. Filters expirations to the configured DTE window
       (``OPP_DTE_MIN`` .. ``OPP_DTE_MAX``).
    4. Enumerates EVERY valid Reverse BWB triplet via
       ``combo_geometry.enumerate_candidates`` (no top-N cap).
    5. Snapshots quotes (bid/ask/OI/vol/IV) for every distinct contract
       across all expirations in a single batched ``reqMktData(snapshot=True)``.
    6. Filters by minimum leg OI (``OPP_MIN_LEG_OI``).
    7. Computes per-combo premium (sign-preserved), numeric liquidity,
       credit efficiency, delta %, and ranking score.
    8. Hands the full batch to :class:`MarginEngine` which deterministically
       margins every row and refines the top-N per side via IBKR WhatIf.
    9. Emits the final list of :class:`LiveOpportunity` rows tagged with a
       single ``opportunity_version`` UUID per cycle.

Returns an ``OpportunityResult`` per ticker. Persistence is the worker's
responsibility — this service is pure compute.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import structlog

from app.core.config import Settings
from app.services.market_data.combo_geometry import (
    ReverseBwbCandidate,
    enumerate_candidates,
)
from app.services.market_data.ibkr_connection import IbkrConnection
from app.services.market_data.liquidity_engine import (
    LiquidityProfile,
    compute_liquidity_profile,
    meets_liquidity_floor,
)
from app.services.market_data.margin_engine import (
    MarginEngine,
    MarginRequest,
    MarginResult,
    deterministic_margin,
)
from app.services.market_data.market_data_service import (
    MarketDataService,
    OptionContractInfo,
    OptionQuote,
)
from app.services.market_data.ranking_engine import (
    RankingInput,
    score_candidates,
)
from app.services.market_data.schemas import LiveOpportunity, SideLiteral

log = structlog.get_logger(__name__)


@dataclass
class OpportunityResult:
    """Per-ticker output of one ``generate()`` call."""

    ticker: str
    calls: list[LiveOpportunity] = field(default_factory=list)
    puts: list[LiveOpportunity] = field(default_factory=list)
    opportunity_version: uuid.UUID | None = None
    underlying_price: float | None = None
    atm_iv: float | None = None
    skipped_reason: str | None = None


@dataclass
class _PricedCandidate:
    """Internal candidate after pricing/liquidity scoring."""

    candidate: ReverseBwbCandidate
    side: SideLiteral
    expiration: str
    expiry_days: int
    legs: tuple[OptionContractInfo, OptionContractInfo, OptionContractInfo]
    leg_quotes: tuple[OptionQuote, OptionQuote, OptionQuote]
    premium: float  # sign-preserved per-share (negative = credit)
    liquidity: LiquidityProfile
    delta_pct: float


class OptionsOpportunityService:
    """End-to-end Workstation Reverse-BWB enumeration per ticker."""

    def __init__(
        self,
        settings: Settings,
        connection: IbkrConnection,
        market_data: MarketDataService,
        repository_factory,
        margin_engine: MarginEngine | None = None,
    ) -> None:
        self._settings = settings
        self._connection = connection
        self._market_data = market_data
        self._repository_factory = repository_factory
        self._margin_engine = margin_engine or MarginEngine(
            settings=settings,
            market_data=market_data,
        )

    @property
    def margin_engine(self) -> MarginEngine:
        return self._margin_engine

    async def generate(
        self,
        ticker: str,
        last_price: float | None,
    ) -> OpportunityResult:
        """Build and return every valid Reverse BWB opportunity for one ticker.

        Returns an empty result (with ``skipped_reason``) when:
            - IBKR is offline
            - No live price is available
            - The chain has no expirations in the configured DTE window
            - No same-side strikes exist within the wing-width bounds
        """
        if not self._connection.is_connected:
            return OpportunityResult(ticker=ticker, skipped_reason="not_connected")

        if last_price is None or last_price <= 0:
            return OpportunityResult(ticker=ticker, skipped_reason="no_last_price")

        chain = await self._market_data.snapshot_chain(
            ticker,
            dte_min=self._settings.opp_dte_min,
            dte_max=self._settings.opp_dte_max,
        )
        if chain is None:
            return OpportunityResult(ticker=ticker, skipped_reason="chain_unavailable")

        expirations, available_strikes = chain
        if not expirations or not available_strikes:
            return OpportunityResult(
                ticker=ticker, skipped_reason="empty_chain"
            )

        # Filter strikes to ±OPP_MAX_STRIKE_DIST_PCT of spot so we only
        # enumerate near-ATM combos. Deep-OTM strikes produce negligible
        # premium and explode the candidate count into the thousands.
        max_dist = self._settings.opp_max_strike_dist_pct / 100.0
        all_strikes_count = len(available_strikes)
        available_strikes = [
            s for s in available_strikes
            if abs(s - float(last_price)) / float(last_price) <= max_dist
        ]
        log.info(
            "opp.strikes_filtered",
            ticker=ticker,
            total_chain_strikes=all_strikes_count,
            after_dist_filter=len(available_strikes),
            max_dist_pct=self._settings.opp_max_strike_dist_pct,
            last_price=last_price,
        )
        if not available_strikes:
            return OpportunityResult(ticker=ticker, skipped_reason="no_strikes_in_range")

        today = datetime.now(UTC).date()

        # 1. Enumerate every candidate per side, deduped.
        candidates_by_side: dict[SideLiteral, list[ReverseBwbCandidate]] = {
            "call": enumerate_candidates(
                side="CALL",
                strikes=available_strikes,
                last_close=float(last_price),
                wing_min_strikes=self._settings.opp_wing_min_strikes,
                wing_max_strikes=self._settings.opp_wing_max_strikes,
            ),
            "put": enumerate_candidates(
                side="PUT",
                strikes=available_strikes,
                last_close=float(last_price),
                wing_min_strikes=self._settings.opp_wing_min_strikes,
                wing_max_strikes=self._settings.opp_wing_max_strikes,
            ),
        }
        if not candidates_by_side["call"] and not candidates_by_side["put"]:
            return OpportunityResult(
                ticker=ticker, skipped_reason="no_candidates_in_strike_window"
            )

        # 2. Build the full set of distinct (expiration, strike, right) leg
        # contracts we need to price. Batch into one IBKR call.
        leg_keys: dict[str, OptionContractInfo] = {}
        all_legs: list[OptionContractInfo] = []
        per_side_per_expiration: dict[
            tuple[SideLiteral, str], list[ReverseBwbCandidate]
        ] = {}

        for side, side_candidates in candidates_by_side.items():
            right = "C" if side == "call" else "P"
            for expiration in expirations:
                bucket = per_side_per_expiration.setdefault((side, expiration), [])
                bucket.extend(side_candidates)
                for cand in side_candidates:
                    for strike in cand.strikes:
                        info = OptionContractInfo(
                            symbol=ticker.upper(),
                            strike=float(strike),
                            right=right,
                            expiry=expiration,
                        )
                        key = MarketDataService.opt_key(info)
                        if key not in leg_keys:
                            leg_keys[key] = info
                            all_legs.append(info)

        if not all_legs:
            return OpportunityResult(
                ticker=ticker, skipped_reason="no_legs_to_price"
            )

        # Cap distinct legs to avoid exhausting IBKR pacing limits.
        # reqSecDefOptParams returns every theoretically possible strike, but
        # many (expiry, strike) combinations don't have listed contracts —
        # qualifying 5000+ legs causes minutes of IBKR traffic and floods logs
        # with "No security definition" errors. Prioritise near-ATM legs where
        # market data is most reliable and the strategy is most valuable.
        _MAX_LEGS = self._settings.opp_max_distinct_legs
        if len(all_legs) > _MAX_LEGS:
            all_legs = sorted(
                all_legs, key=lambda info: abs(info.strike - float(last_price))
            )[:_MAX_LEGS]

        log.info(
            "opp.candidates_built",
            ticker=ticker,
            calls=len(candidates_by_side["call"]),
            puts=len(candidates_by_side["put"]),
            expirations=len(expirations),
            distinct_legs=len(all_legs),
        )

        quotes = await self._market_data.snapshot_option_quotes(all_legs)
        if not quotes:
            return OpportunityResult(
                ticker=ticker, skipped_reason="quote_snapshot_failed"
            )

        # 3. Price + liquidity-screen every candidate at every expiration.
        # Compute the per-share credit threshold once outside the inner loop.
        min_credit_per_share = -(self._settings.opp_min_credit_usd / 100.0)
        priced: list[_PricedCandidate] = []
        atm_iv: float | None = None
        for (side, expiration), side_cands in per_side_per_expiration.items():
            right = "C" if side == "call" else "P"
            try:
                exp_date = datetime.strptime(expiration, "%Y%m%d").date()
                dte = max(0, (exp_date - today).days)
            except ValueError:
                dte = 0

            for cand in side_cands:
                legs = (
                    OptionContractInfo(
                        symbol=ticker.upper(),
                        strike=float(cand.long_wing_a),
                        right=right,
                        expiry=expiration,
                    ),
                    OptionContractInfo(
                        symbol=ticker.upper(),
                        strike=float(cand.short_body),
                        right=right,
                        expiry=expiration,
                    ),
                    OptionContractInfo(
                        symbol=ticker.upper(),
                        strike=float(cand.long_wing_b),
                        right=right,
                        expiry=expiration,
                    ),
                )
                qa = quotes.get(MarketDataService.opt_key(legs[0]))
                qb = quotes.get(MarketDataService.opt_key(legs[1]))
                qc = quotes.get(MarketDataService.opt_key(legs[2]))
                if qa is None or qb is None or qc is None:
                    continue
                premium = self._compute_premium(qa, qb, qc)
                if premium is None:
                    continue

                # Only keep credit combos that clear the minimum threshold.
                if premium > min_credit_per_share:
                    continue

                profile = compute_liquidity_profile(
                    oi_legs=(qa.open_interest, qb.open_interest, qc.open_interest),
                    vol_legs=(qa.volume, qb.volume, qc.volume),
                )
                if not meets_liquidity_floor(
                    profile, min_leg_oi=self._settings.opp_min_leg_oi
                ):
                    continue

                # Capture ATM IV opportunistically — the body leg closest
                # to spot is the best proxy.
                if (
                    qb.implied_vol is not None
                    and abs(cand.short_body - last_price)
                    < (atm_iv_threshold(last_price))
                ):
                    atm_iv = qb.implied_vol

                delta_pct = ((cand.long_wing_a - last_price) / last_price) * 100.0

                priced.append(
                    _PricedCandidate(
                        candidate=cand,
                        side=side,
                        expiration=expiration,
                        expiry_days=int(dte),
                        legs=legs,
                        leg_quotes=(qa, qb, qc),
                        premium=premium,
                        liquidity=profile,
                        delta_pct=round(delta_pct, 4),
                    )
                )

        if not priced:
            return OpportunityResult(
                ticker=ticker,
                skipped_reason="no_priced_candidates",
                underlying_price=float(last_price),
            )

        # 4. Deterministic margin for every row -> credit efficiency ->
        # ranking score. Margin engine then refines top-N per side via WhatIf.
        det_margins = [
            deterministic_margin(
                wing_left=p.candidate.wing_left,
                wing_right=p.candidate.wing_right,
            )
            for p in priced
        ]

        ranking_inputs: list[RankingInput] = []
        for priced_one, det_margin in zip(priced, det_margins):
            ce = _credit_efficiency(priced_one.premium, det_margin)
            ranking_inputs.append(
                RankingInput(
                    credit_efficiency=ce,
                    liquidity=priced_one.liquidity.liquidity,
                    margin=det_margin,
                    body_strike=priced_one.candidate.short_body,
                    underlying_price=float(last_price),
                )
            )
        ranking_scores = score_candidates(ranking_inputs)

        margin_requests = []
        for priced_one, det_margin, rscore in zip(
            priced, det_margins, ranking_scores
        ):
            margin_requests.append(
                MarginRequest(
                    side=priced_one.side,
                    combo=priced_one.candidate.combo_label(),
                    wing_left=priced_one.candidate.wing_left,
                    wing_right=priced_one.candidate.wing_right,
                    leg_con_ids=(
                        priced_one.leg_quotes[0].con_id,
                        priced_one.leg_quotes[1].con_id,
                        priced_one.leg_quotes[2].con_id,
                    ),
                    ranking_score=rscore,
                )
            )

        margin_results: list[MarginResult] = await self._margin_engine.compute_batch(
            margin_requests
        )

        # 5. Materialize the final LiveOpportunity rows. Re-score with the
        # refined margins so the ranking actually reflects WhatIf numbers
        # for the top-N — everything below uses the deterministic value.
        final_inputs: list[RankingInput] = []
        for priced_one, margin in zip(priced, margin_results):
            ce = _credit_efficiency(priced_one.premium, margin.init_margin)
            final_inputs.append(
                RankingInput(
                    credit_efficiency=ce,
                    liquidity=priced_one.liquidity.liquidity,
                    margin=margin.init_margin,
                    body_strike=priced_one.candidate.short_body,
                    underlying_price=float(last_price),
                )
            )
        final_scores = score_candidates(final_inputs)

        now = datetime.now(UTC)
        version = uuid.uuid4()

        live_rows: list[LiveOpportunity] = []
        for priced_one, margin, rscore in zip(priced, margin_results, final_scores):
            premium_dollars = priced_one.premium * 100.0
            credit_efficiency = _credit_efficiency(
                priced_one.premium, margin.init_margin
            )
            live_rows.append(
                LiveOpportunity(
                    ticker=ticker.upper(),
                    side=priced_one.side,
                    rank=0,  # filled in after sort
                    combo=priced_one.candidate.combo_label(),
                    strike_long_wing_a=priced_one.candidate.long_wing_a,
                    strike_short_body=priced_one.candidate.short_body,
                    strike_long_wing_b=priced_one.candidate.long_wing_b,
                    expiration=_expiry_label(priced_one.expiry_days),
                    expiry_days=priced_one.expiry_days,
                    delta_pct=priced_one.delta_pct,
                    premium=round(priced_one.premium, 4),
                    init_margin=round(margin.init_margin, 2),
                    maint_margin=(
                        round(margin.maint_margin, 2)
                        if margin.maint_margin is not None
                        else None
                    ),
                    init_margin_source=margin.source,  # type: ignore[arg-type]
                    liquidity=priced_one.liquidity.liquidity,
                    minimum_open_interest=priced_one.liquidity.minimum_open_interest,
                    minimum_volume=priced_one.liquidity.minimum_volume,
                    oi_leg1=priced_one.liquidity.oi_legs[0],
                    oi_leg2=priced_one.liquidity.oi_legs[1],
                    oi_leg3=priced_one.liquidity.oi_legs[2],
                    vol_leg1=priced_one.liquidity.vol_legs[0],
                    vol_leg2=priced_one.liquidity.vol_legs[1],
                    vol_leg3=priced_one.liquidity.vol_legs[2],
                    iv_leg1=priced_one.leg_quotes[0].implied_vol,
                    iv_leg2=priced_one.leg_quotes[1].implied_vol,
                    iv_leg3=priced_one.leg_quotes[2].implied_vol,
                    mid_leg1=priced_one.leg_quotes[0].mid,
                    mid_leg2=priced_one.leg_quotes[1].mid,
                    mid_leg3=priced_one.leg_quotes[2].mid,
                    credit_efficiency=round(credit_efficiency, 4),
                    ranking_score=rscore,
                    underlying_price=float(last_price),
                    iv=atm_iv,
                    opportunity_version=version,
                    generated_at=now,
                    updated_at=now,
                )
            )
            # Suppress unused-var lint for premium_dollars (kept readable
            # for log statements; intentional).
            _ = premium_dollars

        # Sort each side by ranking_score desc and assign rank.
        calls = sorted(
            (r for r in live_rows if r.side == "call"),
            key=lambda r: -(r.ranking_score or 0),
        )
        puts = sorted(
            (r for r in live_rows if r.side == "put"),
            key=lambda r: -(r.ranking_score or 0),
        )
        for i, row in enumerate(calls):
            row.rank = i
        for i, row in enumerate(puts):
            row.rank = i

        log.info(
            "opp.cycle_complete",
            ticker=ticker,
            version=str(version),
            calls=len(calls),
            puts=len(puts),
            whatif_refined=sum(1 for m in margin_results if m.source == "whatif"),
        )

        return OpportunityResult(
            ticker=ticker.upper(),
            calls=calls,
            puts=puts,
            opportunity_version=version,
            underlying_price=float(last_price),
            atm_iv=atm_iv,
        )

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def _compute_premium(
        long_wing_a: OptionQuote,
        short_body: OptionQuote,
        long_wing_b: OptionQuote,
    ) -> float | None:
        """Net premium for the 4-leg BWB.

        ``net = mid(wing_a) + mid(wing_b) - 2 * mid(body)`` — negative is
        a credit (the BWB's typical case), positive is a debit. The
        opportunity is kept regardless of sign; the trader sees the raw
        number with credit/debit color in the UI.
        """
        wa = long_wing_a.mid
        sb = short_body.mid
        wb = long_wing_b.mid
        if wa is None or sb is None or wb is None:
            return None
        net = wa + wb - 2.0 * sb
        return round(net, 4)


def atm_iv_threshold(price: float) -> float:
    """Strike distance considered 'near' spot for ATM-IV capture."""

    if price >= 500:
        return 5.0
    if price >= 100:
        return 2.5
    return 1.0


def _credit_efficiency(premium_per_share: float, init_margin: float) -> float:
    """Credit efficiency = |credit_dollars| / init_margin * 100.

    Returns 0.0 for non-credit rows (positive premium = debit) so the
    metric stays meaningful as a single column.
    """
    if init_margin <= 0:
        return 0.0
    credit_dollars = abs(premium_per_share) * 100.0
    if premium_per_share >= 0:
        # Debit case — credit efficiency is conventionally 0.
        return 0.0
    return round(credit_dollars / init_margin * 100.0, 4)


def _expiry_label(dte: int) -> str:
    if dte <= 0:
        return "0D"
    return f"{int(dte)}D"
