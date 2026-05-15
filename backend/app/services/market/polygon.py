"""Polygon OHLCV and price-article join."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import aiohttp
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import Settings
from app.services.domain.models import OHLCVBar, ProcessedArticle

log = structlog.get_logger(__name__)


class MarketDataService:
    def __init__(self, settings: Settings, ticker: str) -> None:
        self._settings = settings
        self.ticker = ticker

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(aiohttp.ClientError),
    )
    async def fetch_ohlcv(self, days: int) -> list[OHLCVBar]:
        from_date = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
        to_date = datetime.now(UTC).strftime("%Y-%m-%d")
        url = (
            f"https://api.polygon.io/v2/aggs/ticker/{self.ticker}/range/1/day/{from_date}/{to_date}"
        )
        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 120,
            "apiKey": self._settings.polygon_api_key,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                resp.raise_for_status()
                data = await resp.json()

        bars: list[OHLCVBar] = []
        for r in data.get("results", []):
            bars.append(
                OHLCVBar(
                    ticker=self.ticker,
                    timestamp=datetime.fromtimestamp(r["t"] / 1000, tz=UTC),
                    open=r["o"],
                    high=r["h"],
                    low=r["l"],
                    close=r["c"],
                    volume=r["v"],
                )
            )
        log.info("market.ohlcv_fetched", ticker=self.ticker, bars=len(bars))
        return bars

    @staticmethod
    def compute_daily_returns(bars: list[OHLCVBar]) -> dict[str, float]:
        returns: dict[str, float] = {}
        for i in range(1, len(bars)):
            prev, curr = bars[i - 1], bars[i]
            if prev.close and prev.close != 0:
                ret = (curr.close - prev.close) / prev.close * 100
                returns[curr.timestamp.date().isoformat()] = round(ret, 4)
        return returns

    @staticmethod
    def compute_intraday_volatility(bars: list[OHLCVBar]) -> dict[str, float]:
        vol: dict[str, float] = {}
        for b in bars:
            if b.open and b.open != 0:
                v = (b.high - b.low) / b.open * 100
                vol[b.timestamp.date().isoformat()] = round(v, 4)
        return vol

    @staticmethod
    def join_price_to_articles(
        articles: list[ProcessedArticle],
        returns: dict[str, float],
        vol: dict[str, float],
    ) -> list[ProcessedArticle]:
        del vol  # reserved for future use
        for a in articles:
            date_str = a.published_at.date().isoformat()
            ret = returns.get(date_str)
            if ret is not None:
                a.abnormal_return = ret
        return articles

    @staticmethod
    def get_current_price(bars: list[OHLCVBar]) -> float | None:
        return bars[-1].close if bars else None

    @staticmethod
    def get_volatility_regime(bars: list[OHLCVBar], window: int = 10) -> str:
        if len(bars) < 2:
            return "unknown"
        recent = bars[-min(window, len(bars)) :]
        moves: list[float] = []
        for i in range(1, len(recent)):
            if recent[i - 1].close:
                moves.append(abs(recent[i].close - recent[i - 1].close) / recent[i - 1].close * 100)
        if not moves:
            return "unknown"
        avg = sum(moves) / len(moves)
        return "high" if avg > 3 else "medium" if avg > 1.5 else "low"
