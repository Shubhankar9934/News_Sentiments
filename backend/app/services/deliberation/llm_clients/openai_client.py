"""OpenAI client for deliberation."""

from __future__ import annotations

from app.core.config import Settings
from app.services.deliberation.llm_clients.base import BaseDeliberationClient


class OpenAIDeliberationClient(BaseDeliberationClient):
    model_key = "gpt"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)

    async def complete_json(self, system: str, user: str, max_tokens: int = 3000) -> str:
        base = self._settings.openai_base_url.rstrip("/")
        url = f"{base}/chat/completions"
        data = await self._post_json(
            url,
            headers={
                "Authorization": f"Bearer {self._settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            payload={
                "model": self._settings.openai_model,
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        return data["choices"][0]["message"]["content"]
