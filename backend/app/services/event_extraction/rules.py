"""Rule-based event extraction."""

import structlog

from app.services.domain.models import ProcessedArticle

log = structlog.get_logger(__name__)


class EventExtractionService:
    PATTERNS = {
        "Earnings": [
            "earnings",
            "revenue",
            "eps",
            "beat",
            "miss",
            "guidance",
            "q1",
            "q2",
            "q3",
            "q4",
            "annual",
            "quarterly",
            "profit",
            "loss",
        ],
        "Regulation": [
            "sec",
            "ftc",
            "doj",
            "antitrust",
            "ban",
            "sanction",
            "regulation",
            "fine",
            "penalty",
            "export control",
            "subpoena",
        ],
        "Supply Chain": [
            "tsmc",
            "supply",
            "shortage",
            "production",
            "manufacturing",
            "inventory",
            "fab",
            "wafer",
            "foundry",
        ],
        "Product": [
            "launch",
            "release",
            "unveil",
            "announce",
            "chip",
            "gpu",
            "model",
            "platform",
            "software",
            "hardware",
            "next-gen",
        ],
        "Partnership": [
            "partnership",
            "deal",
            "agreement",
            "collaborate",
            "invest",
            "acquire",
            "merger",
            "acquisition",
            "joint venture",
        ],
        "Macro": [
            "fed",
            "interest rate",
            "inflation",
            "recession",
            "gdp",
            "tariff",
            "china",
            "macro",
            "rate hike",
            "rate cut",
            "cpi",
        ],
        "Analyst": [
            "upgrade",
            "downgrade",
            "price target",
            "buy",
            "sell",
            "neutral",
            "outperform",
            "underperform",
            "initiate",
            "coverage",
        ],
    }

    def extract(self, articles: list[ProcessedArticle]) -> list[ProcessedArticle]:
        for a in articles:
            text = (a.headline + " " + a.content).lower()
            scores = {et: sum(1 for kw in kws if kw in text) for et, kws in self.PATTERNS.items()}
            best = max(scores, key=scores.get)
            if scores[best] > 0:
                a.event_type = best
        log.info("events.extracted", articles=len(articles))
        return articles
