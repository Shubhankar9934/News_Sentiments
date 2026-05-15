"""Domain dataclasses (legacy-compatible)."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class RawArticle:
    id: str
    ticker: str
    headline: str
    content: str
    source: str
    url: str
    published_at: datetime
    raw_json: dict = field(default_factory=dict)


@dataclass
class ProcessedArticle:
    id: str
    ticker: str
    headline: str
    content: str
    source: str
    url: str
    published_at: datetime
    sentiment_score: float = 0.0
    sentiment_label: str = "Neutral"
    event_type: str | None = None
    embedding: list = field(default_factory=list)
    cluster_id: str | None = None
    reliability_score: int = 60
    is_duplicate: bool = False
    impact_score: float = 0.0
    abnormal_return: float | None = None


@dataclass
class OHLCVBar:
    ticker: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class EventImpactScore:
    article_id: str
    ticker: str
    impact_score: float
    components: dict[str, Any]
    computed_at: datetime = field(default_factory=lambda: datetime.now())
