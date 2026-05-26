"""Static watchlist tier definitions for the Reverse BWB dashboard.

This is the authoritative server-side mirror of
``frontend/src/config/watchlist.ts``. Both files must move together when the
watchlist is rebalanced. The order of ``WATCHLIST_TIERS`` defines the
sequential execution order enforced by ``WatchlistBatchService``:

    SPY -> QQQ -> IWM -> DIA -> AAPL -> MSFT -> AMZN -> GOOGL
        -> NVDA -> TSLA -> AMD -> META
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WatchlistTicker:
    symbol: str
    company: str


@dataclass(frozen=True)
class WatchlistTier:
    key: str
    name: str
    description: str
    tickers: tuple[WatchlistTicker, ...]


WATCHLIST_TIERS: tuple[WatchlistTier, ...] = (
    WatchlistTier(
        key="tier-1",
        name="Tier 1",
        description="Index ETFs",
        tickers=(
            WatchlistTicker("SPY", "SPDR S&P 500 ETF Trust"),
            WatchlistTicker("QQQ", "Invesco QQQ Trust"),
            WatchlistTicker("IWM", "iShares Russell 2000 ETF"),
            WatchlistTicker("DIA", "SPDR Dow Jones Industrial Average ETF"),
        ),
    ),
    WatchlistTier(
        key="tier-2",
        name="Tier 2",
        description="Mega-cap tech",
        tickers=(
            WatchlistTicker("AAPL", "Apple Inc."),
            WatchlistTicker("MSFT", "Microsoft Corporation"),
            WatchlistTicker("AMZN", "Amazon.com, Inc."),
            WatchlistTicker("GOOGL", "Alphabet Inc."),
        ),
    ),
    WatchlistTier(
        key="tier-3",
        name="Tier 3",
        description="High-beta growth",
        tickers=(
            WatchlistTicker("NVDA", "NVIDIA Corporation"),
            WatchlistTicker("TSLA", "Tesla, Inc."),
            WatchlistTicker("AMD", "Advanced Micro Devices, Inc."),
            WatchlistTicker("META", "Meta Platforms, Inc."),
        ),
    ),
)


ALL_WATCHLIST_TICKERS: tuple[str, ...] = tuple(
    t.symbol for tier in WATCHLIST_TIERS for t in tier.tickers
)


WATCHLIST_COMPANY_BY_SYMBOL: dict[str, str] = {
    t.symbol: t.company for tier in WATCHLIST_TIERS for t in tier.tickers
}


WATCHLIST_TIER_KEY_BY_SYMBOL: dict[str, str] = {
    t.symbol: tier.key for tier in WATCHLIST_TIERS for t in tier.tickers
}


def is_watchlist_ticker(ticker: str) -> bool:
    return ticker.upper() in WATCHLIST_COMPANY_BY_SYMBOL


def tier_for(ticker: str) -> str | None:
    return WATCHLIST_TIER_KEY_BY_SYMBOL.get(ticker.upper())
