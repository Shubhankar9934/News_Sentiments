"""DeepSeek client (OpenAI-compatible API)."""

from __future__ import annotations

from app.core.config import Settings
from app.services.deliberation.llm_clients.base import BaseDeliberationClient


class DeepSeekDeliberationClient(BaseDeliberationClient):
    model_key = "deepseek"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)

    async def complete_json(self, system: str, user: str, max_tokens: int = 3000) -> str:
        base = self._settings.deepseek_base_url.rstrip("/")
        url = f"{base}/v1/chat/completions"
        data = await self._post_json(
            url,
            headers={
                "Authorization": f"Bearer {self._settings.deepseek_api_key}",
                "Content-Type": "application/json",
            },
            payload={
                "model": self._settings.deepseek_model,
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        return data["choices"][0]["message"]["content"]
