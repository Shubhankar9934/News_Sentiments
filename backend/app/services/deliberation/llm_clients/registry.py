"""Provider registry — enabled when API key is configured."""

from __future__ import annotations

from app.core.config import Settings
from app.services.deliberation.llm_clients.anthropic_client import AnthropicDeliberationClient
from app.services.deliberation.llm_clients.base import BaseDeliberationClient
from app.services.deliberation.llm_clients.deepseek_client import DeepSeekDeliberationClient
from app.services.deliberation.llm_clients.gemini_client import GeminiDeliberationClient
from app.services.deliberation.llm_clients.groq_client import GroqDeliberationClient
from app.services.deliberation.llm_clients.openai_client import OpenAIDeliberationClient

ALL_DIL_MODEL_KEYS = ["gpt", "claude", "gemini", "deepseek", "groq"]


def get_enabled_clients(settings: Settings) -> list[BaseDeliberationClient]:
    excluded = settings.dil_excluded_model_set
    clients: list[BaseDeliberationClient] = []
    if settings.openai_api_key.strip() and "gpt" not in excluded:
        clients.append(OpenAIDeliberationClient(settings))
    if settings.anthropic_api_key.strip() and "claude" not in excluded:
        clients.append(AnthropicDeliberationClient(settings))
    if settings.gemini_api_key.strip() and "gemini" not in excluded:
        clients.append(GeminiDeliberationClient(settings))
    if settings.deepseek_api_key.strip() and "deepseek" not in excluded:
        clients.append(DeepSeekDeliberationClient(settings))
    if settings.groq_api_key.strip() and "groq" not in excluded:
        clients.append(GroqDeliberationClient(settings))
    return clients
