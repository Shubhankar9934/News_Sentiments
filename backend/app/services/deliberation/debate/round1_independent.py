"""Round 1: parallel independent reasoning."""

from __future__ import annotations

import asyncio
import json

import structlog

from app.services.deliberation.llm_clients.base import BaseDeliberationClient, load_prompt, parse_strict_json
from app.services.deliberation.schemas import DeliberationContext, IndependentOpinion, ModelKey

log = structlog.get_logger(__name__)


async def _run_one(
    client: BaseDeliberationClient,
    context: DeliberationContext,
) -> tuple[ModelKey, IndependentOpinion]:
    system = load_prompt("independent_analysis.txt")
    user = (
        f"Ticker: {context.ticker}\n\n"
        f"Structured research context:\n{json.dumps(context.model_dump(), indent=2)}\n\n"
        f'Return JSON with "model" set to "{client.model_key}".'
    )
    try:
        raw = await client.complete_json(system, user)
        opinion = parse_strict_json(raw, IndependentOpinion)
        opinion.model = client.model_key
        return client.model_key, opinion
    except Exception as e:
        log.warning("dil.round1.model_failed", model=client.model_key, error=str(e))
        return client.model_key, IndependentOpinion(
            model=client.model_key,
            stance="neutral",
            confidence=0.0,
            error=str(e),
        )


async def run_independent_round(
    clients: list[BaseDeliberationClient],
    context: DeliberationContext,
) -> dict[str, IndependentOpinion]:
    results = await asyncio.gather(*[_run_one(c, context) for c in clients])
    return dict(results)
