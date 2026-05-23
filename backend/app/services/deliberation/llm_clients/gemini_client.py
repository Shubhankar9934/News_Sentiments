"""Google Gemini client for deliberation."""

from __future__ import annotations

from app.core.config import Settings
from app.services.deliberation.llm_clients.base import BaseDeliberationClient


class GeminiDeliberationClient(BaseDeliberationClient):
    model_key = "gemini"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)

    async def complete_json(self, system: str, user: str, max_tokens: int = 3000) -> str:
        model = self._settings.gemini_model
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            f"?key={self._settings.gemini_api_key}"
        )
        data = await self._post_json(
            url,
            headers={"Content-Type": "application/json"},
            payload={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {
                    "maxOutputTokens": max_tokens,
                    "responseMimeType": "application/json",
                },
            },
        )
        candidates = data.get("candidates") or []
        if not candidates:
            raise ValueError("Empty Gemini response")
        parts = candidates[0].get("content", {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts)
