"""Celery task: async multi-LLM deliberation post-step."""

from __future__ import annotations

import asyncio

from app.workers.celery_app import celery_app


@celery_app.task(name="deliberation.run", bind=True, max_retries=1)
def run_deliberation_task(self, report_id: str) -> dict:
    from app.services.deliberation.runner import execute_deliberation

    return asyncio.run(execute_deliberation(report_id))
