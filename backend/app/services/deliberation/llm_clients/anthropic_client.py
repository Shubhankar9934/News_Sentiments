"""Anthropic client for deliberation (separate from report synthesis).

PR10 hardening: instead of asking Claude for JSON in the prompt and hoping
it complies, we force the response into a single ``emit_deliberation_json``
tool call with ``tool_choice = {type: 'tool', name: ...}``. The tool input
is what we want — a JSON object — so we return its string serialization and
let ``parse_strict_json`` do the rest.

The fallback path (no tool call returned) still scrapes any plain-text
content for a JSON object so old prompts and dry-run responses keep working.
"""

from __future__ import annotations

import json
from typing import Any

from app.core.config import Settings
from app.services.deliberation.llm_clients.base import BaseDeliberationClient


_TOOL_NAME = "emit_deliberation_json"
_TOOL_DEFINITION: dict[str, Any] = {
    "name": _TOOL_NAME,
    "description": (
        "Emit the deliberation response as a single JSON object. "
        "Always call this tool with a single argument named `payload` "
        "that contains your full structured response."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "payload": {"type": "object"},
        },
        "required": ["payload"],
        "additionalProperties": False,
    },
}


class AnthropicDeliberationClient(BaseDeliberationClient):
    model_key = "claude"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)

    async def complete_json(self, system: str, user: str, max_tokens: int = 3000) -> str:
        base = self._settings.anthropic_base_url.rstrip("/")
        url = f"{base}/v1/messages"
        data = await self._post_json(
            url,
            headers={
                "x-api-key": self._settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            payload={
                "model": self._settings.anthropic_model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
                "tools": [_TOOL_DEFINITION],
                "tool_choice": {"type": "tool", "name": _TOOL_NAME},
            },
        )

        # Preferred path: tool_use block with our forced tool name.
        for block in data.get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == _TOOL_NAME:
                tool_input = block.get("input") or {}
                payload = tool_input.get("payload", tool_input)
                return json.dumps(payload, default=str)

        # Fallback: stitched text content (for legacy prompts / dry-run mocks).
        return "".join(b.get("text", "") for b in data.get("content", []))
