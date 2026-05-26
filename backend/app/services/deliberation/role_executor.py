"""Execute a desk role with ordered provider failover."""



from __future__ import annotations



from collections.abc import Awaitable, Callable

from typing import TypeVar



from app.services.deliberation.desk_config import DeskDefinition

from app.services.deliberation.llm_clients.base import BaseDeliberationClient

from app.services.deliberation.schemas import ModelKey

from app.services.dil_resilience.executor import execute_with_failover



T = TypeVar("T")





async def execute_desk(

    desk: DeskDefinition,

    client_map: dict[str, BaseDeliberationClient],

    prompt_fn: Callable[[BaseDeliberationClient], Awaitable[T]],

) -> tuple[ModelKey | None, list[str], T | None, str | None]:

    """Try each provider in the desk chain until one succeeds.



    Returns ``(provider_used, attempts, result, error)``.

    """

    return await execute_with_failover(

        desk.key,

        desk.provider_chain,

        client_map,

        prompt_fn,

        log_prefix="desk",

    )

