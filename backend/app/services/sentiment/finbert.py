"""FinBERT sentiment scoring."""

from __future__ import annotations

import structlog

from app.core.config import Settings
from app.services.domain.models import ProcessedArticle

log = structlog.get_logger(__name__)


class SentimentService:
    LABEL_MAP = {
        "positive": ("Bullish", 1.0),
        "negative": ("Bearish", -1.0),
        "neutral": ("Neutral", 0.0),
    }

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = None
        self._tokenizer = None
        self._device: str = "cpu"

    def _load(self) -> None:
        if self._model is None:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            token = self._settings.hf_token or None
            self._tokenizer = AutoTokenizer.from_pretrained(self._settings.finbert_model, token=token)
            self._model = AutoModelForSequenceClassification.from_pretrained(
                self._settings.finbert_model, token=token
            )
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model.to(self._device).eval()
            log.info("finbert.loaded", device=self._device)

    def analyze(
        self, articles: list[ProcessedArticle], batch_size: int = 16
    ) -> list[ProcessedArticle]:
        import torch

        self._load()
        texts = [f"{a.headline}. {a.content[:300]}" for a in articles]
        all_preds: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            enc = self._tokenizer(
                batch, truncation=True, max_length=512, padding=True, return_tensors="pt"
            )
            enc = {k: v.to(self._device) for k, v in enc.items()}
            with torch.no_grad():
                logits = self._model(**enc).logits
            probs = torch.softmax(logits, dim=-1).cpu().tolist()
            all_preds.extend(probs)

        id2label = self._model.config.id2label
        for article, probs in zip(articles, all_preds, strict=True):
            best_idx = max(range(len(probs)), key=lambda j: probs[j])
            raw_label = id2label[best_idx].lower()
            label, direction = self.LABEL_MAP.get(raw_label, ("Neutral", 0.0))
            article.sentiment_label = label
            article.sentiment_score = round(probs[best_idx] * direction, 3)

        log.info("sentiment.complete", articles=len(articles))
        return articles
