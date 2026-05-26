"""Round 1: backward-compatible re-export of desk analysis layer."""

from __future__ import annotations

from app.services.deliberation.analysis.adapters import desk_report_to_opinion
from app.services.deliberation.analysis.run_desk_analysis import (
    client_for_desk_report,
    run_desk_analysis,
)
from app.services.deliberation.desk_config import DeskDefinition
from app.services.deliberation.llm_clients.base import BaseDeliberationClient
from app.services.deliberation.schemas import DeliberationContext, IndependentOpinion


async def run_independent_round(
    desks: list[DeskDefinition],
    client_map: dict[str, BaseDeliberationClient],
    context: DeliberationContext,
    *,
    regime_hint: dict | None = None,
) -> dict[str, IndependentOpinion]:
    reports = await run_desk_analysis(
        desks, client_map, context, regime_hint=regime_hint
    )
    return {k: desk_report_to_opinion(v) for k, v in reports.items()}


def client_for_desk(
    opinion: IndependentOpinion,
    client_map: dict[str, BaseDeliberationClient],
    desk: DeskDefinition | None = None,
) -> BaseDeliberationClient | None:
    from app.services.deliberation.analysis.adapters import opinion_to_desk_report

    return client_for_desk_report(
        opinion_to_desk_report(opinion), client_map, desk
    )
