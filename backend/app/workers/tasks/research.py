"""Celery tasks for long-running research."""

import asyncio

from app.workers.celery_app import celery_app


@celery_app.task(name="research.run_pipeline")
def run_research_task(ticker: str, days: int = 7) -> dict:
    async def _run() -> dict:
        from app.core.config import get_settings
        from app.db.session import SessionLocal
        from app.services.orchestration.pipeline import ResearchPipelineService
        from app.services.qdrant.store import QdrantStoreService

        settings = get_settings()
        qdrant = None
        try:
            qdrant = QdrantStoreService(settings)
        except Exception:
            pass
        async with SessionLocal() as session:
            pipeline = ResearchPipelineService(session=session, settings=settings, qdrant=qdrant)
            return await pipeline.run(ticker.upper(), days)

    return asyncio.run(_run())
