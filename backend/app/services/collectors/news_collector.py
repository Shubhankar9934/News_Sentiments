"""Multi-source news collector with retries."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta

import aiohttp
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import Settings
from app.services.domain.models import RawArticle

log = structlog.get_logger(__name__)


class NewsCollectorService:
    def __init__(self, settings: Settings, ticker: str, days: int) -> None:
        self._settings = settings
        self.ticker = ticker
        self.days = days
        self.from_date = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
        self.to_date = datetime.now(UTC).strftime("%Y-%m-%d")

    async def collect(self) -> list[RawArticle]:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=10),
        ) as session:
            results = await asyncio.gather(
                self._fetch_finnhub(session),
                self._fetch_newsapi(session),
                self._fetch_polygon_news(session),
                return_exceptions=True,
            )
        articles: list[RawArticle] = []
        for r in results:
            if isinstance(r, BaseException):
                log.warning("collector.source_failed", error=str(r))
            else:
                articles.extend(r)
        log.info("collector.complete", ticker=self.ticker, total=len(articles))
        return articles

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=8),
        retry=retry_if_exception_type(aiohttp.ClientError),
    )
    async def _fetch_finnhub(self, session: aiohttp.ClientSession) -> list[RawArticle]:
        async with session.get(
            "https://finnhub.io/api/v1/company-news",
            params={
                "symbol": self.ticker,
                "from": self.from_date,
                "to": self.to_date,
                "token": self._settings.finnhub_api_key,
            },
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
        out: list[RawArticle] = []
        for item in data[:60]:
            if not item.get("headline"):
                continue
            aid = item.get("id") or hashlib.md5(item.get("headline", "").encode()).hexdigest()[:8]
            out.append(
                RawArticle(
                    id=f"fh-{aid}",
                    ticker=self.ticker,
                    headline=item.get("headline", ""),
                    content=item.get("summary", ""),
                    source=item.get("source", "Unknown"),
                    url=item.get("url", ""),
                    published_at=datetime.fromtimestamp(item.get("datetime", 0), tz=UTC),
                    raw_json=item,
                )
            )
        return out

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=8),
        retry=retry_if_exception_type(aiohttp.ClientError),
    )
    async def _fetch_newsapi(self, session: aiohttp.ClientSession) -> list[RawArticle]:
        async with session.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": f'"{self.ticker}" stock OR "{self.ticker}" earnings',
                "from": self.from_date,
                "to": self.to_date,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 30,
                "apiKey": self._settings.newsapi_key,
            },
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
        out: list[RawArticle] = []
        for item in data.get("articles", []):
            if not item.get("title"):
                continue
            pid = hashlib.md5(item.get("url", "").encode()).hexdigest()[:8]
            pub = item.get("publishedAt", datetime.now(UTC).isoformat()).replace("Z", "+00:00")
            out.append(
                RawArticle(
                    id=f"na-{pid}",
                    ticker=self.ticker,
                    headline=item.get("title", ""),
                    content=item.get("description", "") or "",
                    source=item.get("source", {}).get("name", "Unknown"),
                    url=item.get("url", ""),
                    published_at=datetime.fromisoformat(pub),
                    raw_json=item,
                )
            )
        return out

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=8),
        retry=retry_if_exception_type(aiohttp.ClientError),
    )
    async def _fetch_polygon_news(self, session: aiohttp.ClientSession) -> list[RawArticle]:
        async with session.get(
            "https://api.polygon.io/v2/reference/news",
            params={
                "ticker": self.ticker,
                "published_utc.gte": self.from_date,
                "limit": 25,
                "apiKey": self._settings.polygon_api_key,
            },
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
        out: list[RawArticle] = []
        for item in data.get("results", []):
            if not item.get("title"):
                continue
            pub = item.get("published_utc", datetime.now(UTC).isoformat()).replace("Z", "+00:00")
            out.append(
                RawArticle(
                    id=f"pg-{item.get('id', '')}",
                    ticker=self.ticker,
                    headline=item.get("title", ""),
                    content=item.get("description", ""),
                    source=item.get("publisher", {}).get("name", "Unknown"),
                    url=item.get("article_url", ""),
                    published_at=datetime.fromisoformat(pub),
                    raw_json=item,
                )
            )
        return out
