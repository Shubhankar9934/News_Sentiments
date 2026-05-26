"""Ticker-relevance scoring for news articles.

Drops noise (Cava, Workday, BJ's …) from a single-ticker report by classifying
each article as ``direct``, ``related_sector``, ``macro``, or ``unrelated``.
"""

from app.services.relevance.sector_map import SECTOR_PEERS, TICKER_ALIASES
from app.services.relevance.ticker_relevance import (
    RelevanceResult,
    RelevanceTier,
    classify_article,
    classify_many,
)

__all__ = [
    "RelevanceTier",
    "RelevanceResult",
    "classify_article",
    "classify_many",
    "SECTOR_PEERS",
    "TICKER_ALIASES",
]
