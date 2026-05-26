"""Execute a council member with ordered provider failover."""



from __future__ import annotations



from collections.abc import Awaitable, Callable

from typing import TypeVar



from app.services.deliberation.council.council_config import CouncilMemberDefinition

from app.services.deliberation.llm_clients.base import BaseDeliberationClient

from app.services.deliberation.schemas import ModelKey

from app.services.dil_resilience.executor import execute_with_failover



T = TypeVar("T")





async def execute_council_member(

    member: CouncilMemberDefinition,

    client_map: dict[str, BaseDeliberationClient],

    prompt_fn: Callable[[BaseDeliberationClient], Awaitable[T]],

) -> tuple[ModelKey | None, list[str], T | None, str | None]:

    return await execute_with_failover(

        member.key,

        member.provider_chain,

        client_map,

        prompt_fn,

        log_prefix="council",

    )

