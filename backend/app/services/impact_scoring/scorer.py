"""Event impact scoring (legacy formula)."""

from datetime import UTC, datetime

import structlog

from app.core.constants import EVENT_IMPACT_WEIGHTS
from app.services.domain.models import ProcessedArticle

log = structlog.get_logger(__name__)


class EventImpactScoringService:
    VOLATILITY_MULTIPLIER = {"high": 1.3, "medium": 1.0, "low": 0.75, "unknown": 1.0}

    def score(
        self,
        articles: list[ProcessedArticle],
        volatility_regime: str = "medium",
        now: datetime | None = None,
    ) -> list[ProcessedArticle]:
        if now is None:
            now = datetime.now(UTC)
        vol_mult = self.VOLATILITY_MULTIPLIER.get(volatility_regime, 1.0)

        for a in articles:
            sent_mag = abs(a.sentiment_score)
            rel_weight = a.reliability_score / 100.0
            pub = a.published_at
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=UTC)
            age_days = max(0, (now - pub).total_seconds() / 86400)
            recency = 2 ** (-age_days / 3.0)
            event_weight = EVENT_IMPACT_WEIGHTS.get(a.event_type or "", 0.5)
            raw_score = sent_mag * rel_weight * recency * event_weight * vol_mult
            a.impact_score = round(min(raw_score, 1.0), 4)

        log.info("impact_scoring.complete", articles=len(articles), vol_regime=volatility_regime)
        return articles
