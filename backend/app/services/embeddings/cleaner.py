"""Embedding + deduplication (matrix or Qdrant ANN)."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import structlog

from app.core.config import Settings
from app.core.constants import SOURCE_RELIABILITY
from app.services.domain.models import ProcessedArticle, RawArticle

if TYPE_CHECKING:
    from app.services.qdrant.store import QdrantStoreService

log = structlog.get_logger(__name__)


class NewsCleanerService:
    def __init__(self, settings: Settings, qdrant: QdrantStoreService | None = None) -> None:
        self._settings = settings
        self._model = None
        self.qdrant = qdrant

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._settings.embed_model)
        return self._model

    def clean(self, articles: list[RawArticle]) -> list[ProcessedArticle]:
        valid = [a for a in articles if len(a.headline.strip()) > 10]
        seen_fps: set[str] = set()
        deduped: list[RawArticle] = []
        for a in valid:
            fp = hashlib.md5(f"{a.headline}{a.source}".encode()).hexdigest()
            if fp not in seen_fps:
                seen_fps.add(fp)
                deduped.append(a)

        processed = [
            ProcessedArticle(
                id=a.id,
                ticker=a.ticker,
                headline=a.headline,
                content=a.content,
                source=a.source,
                url=a.url,
                published_at=a.published_at,
                reliability_score=SOURCE_RELIABILITY.get(a.source, 60),
            )
            for a in deduped
        ]

        model = self._get_model()
        headlines = [a.headline for a in processed]
        embeddings = model.encode(headlines, normalize_embeddings=True, batch_size=32)
        for i, a in enumerate(processed):
            a.embedding = embeddings[i].tolist()

        thr = self._settings.dedupe_threshold
        if self.qdrant:
            self._dedupe_via_qdrant(processed, thr)
        else:
            self._dedupe_matrix(processed, embeddings, thr)

        unique = [a for a in processed if not a.is_duplicate]
        log.info(
            "cleaner.complete",
            raw=len(articles),
            valid=len(valid),
            unique=len(unique),
            dupes=len(processed) - len(unique),
        )
        return processed

    def _dedupe_matrix(
        self, processed: list[ProcessedArticle], embeddings, threshold: float
    ) -> None:

        emb = embeddings
        sim = emb @ emb.T
        ctr = 0
        for i in range(len(processed)):
            if processed[i].is_duplicate:
                continue
            cid = f"cluster-{ctr}"
            ctr += 1
            processed[i].cluster_id = cid
            for j in range(i + 1, len(processed)):
                if not processed[j].is_duplicate and sim[i, j] > threshold:
                    if processed[j].reliability_score > processed[i].reliability_score:
                        processed[i].is_duplicate = True
                        processed[j].cluster_id = cid
                    else:
                        processed[j].is_duplicate = True
                        processed[j].cluster_id = cid

    def _dedupe_via_qdrant(self, processed: list[ProcessedArticle], threshold: float) -> None:
        if not self.qdrant:
            return
        for article in processed:
            results = self.qdrant.search_similar(article.embedding[:384], limit=3)
            for r in results:
                if r.score > threshold and r.payload.get("article_id") != article.id:
                    article.is_duplicate = True
                    article.cluster_id = str(r.payload.get("article_id"))
                    break
