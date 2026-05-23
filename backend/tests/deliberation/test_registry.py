"""Tests for deliberation provider registry."""

from __future__ import annotations

from app.core.config import Settings
from app.services.deliberation.llm_clients.registry import ALL_DIL_MODEL_KEYS, get_enabled_clients


def test_all_dil_model_keys_includes_groq():
    assert "groq" in ALL_DIL_MODEL_KEYS


def test_groq_enabled_when_api_key_set():
    settings = Settings(GROQ_API_KEY="gsk_test")
    clients = get_enabled_clients(settings)
    assert any(c.model_key == "groq" for c in clients)


def test_groq_excluded_when_in_dil_exclude_models():
    settings = Settings(GROQ_API_KEY="gsk_test", DIL_EXCLUDE_MODELS="groq")
    clients = get_enabled_clients(settings)
    assert not any(c.model_key == "groq" for c in clients)
