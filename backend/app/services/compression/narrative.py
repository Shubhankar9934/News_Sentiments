"""Narrative compression into clusters for LLM."""

from itertools import groupby

import structlog

from app.core.config import Settings
from app.services.domain.models import ProcessedArticle

log = structlog.get_logger(__name__)


class NarrativeCompressionService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def compress(
        self, articles: list[ProcessedArticle], max_clusters: int | None = None
    ) -> list[dict]:
        max_c = max_clusters or self._settings.max_articles_claude
        unique = [a for a in articles if not a.is_duplicate]
        sorted_arts = sorted(unique, key=lambda a: (a.event_type or "ZZZ", a.sentiment_label))

        clusters: list[dict] = []
        for _key, group in groupby(sorted_arts, key=lambda a: (a.event_type, a.sentiment_label)):
            grp = sorted(group, key=lambda a: a.impact_score, reverse=True)
            rep = grp[0]
            clusters.append(
                {
                    "event_type": rep.event_type,
                    "sentiment": rep.sentiment_label,
                    "sentiment_score": round(sum(a.sentiment_score for a in grp) / len(grp), 3),
                    "article_count": len(grp),
                    "impact_score": round(max(a.impact_score for a in grp), 4),
                    "top_headline": rep.headline,
                    "top_source": rep.source,
                    "published_at": rep.published_at.isoformat(),
                    "reliability": rep.reliability_score,
                    "abnormal_return": rep.abnormal_return,
                    "headlines": [a.headline for a in grp[:3]],
                }
            )

        clusters.sort(key=lambda c: c["impact_score"], reverse=True)
        log.info("narrative.compressed", clusters=len(clusters), max=max_c)
        return clusters[:max_c]
