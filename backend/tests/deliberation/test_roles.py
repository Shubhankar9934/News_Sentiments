"""Role specialization: each provider gets a fixed desk and a tilted context."""

import pytest

from app.services.deliberation.roles import (
    DESK_ROLES,
    context_view_for_role,
    role_for,
    role_step_titles,
)


def test_fixed_mapping_for_all_known_providers():
    assert role_for("gpt")["key"] == "macro_desk"
    assert role_for("claude")["key"] == "fundamental_desk"
    assert role_for("groq")["key"] == "options_desk"
    assert role_for("deepseek")["key"] == "risk_desk"
    assert role_for("gemini")["key"] == "devils_advocate_desk"


def test_role_for_unknown_provider_falls_back_safely():
    fb = role_for("brand_new_llm")
    assert "key" in fb and "label" in fb


def test_step_titles_unique_per_role():
    from app.services.deliberation.desk_config import ALL_DESK_KEYS, ROLE_STEP_TITLES

    seen: dict[tuple, str] = {}
    for k in ALL_DESK_KEYS:
        titles = tuple(ROLE_STEP_TITLES[k])
        assert titles, f"missing step titles for {k}"
        if titles in seen:
            pytest.fail(f"duplicate step titles for {k} and {seen[titles]}")
        seen[titles] = k


def test_options_desk_context_includes_options_intelligence():
    ctx = {
        "ticker": "NVDA",
        "market_context": {"volatility_regime": "medium"},
        "options_intelligence": {"credit_safety": {"score": 6.5, "label": "CAUTION"}},
        "article_evidence": [],
    }
    view = context_view_for_role(ctx, "options_desk")
    assert "role_focus" in view
    assert view["role_focus"]["options_intelligence"]["credit_safety"]["label"] == "CAUTION"


def test_macro_desk_context_filters_macro_articles():
    ctx = {
        "article_evidence": [
            {"headline": "Fed signals patience", "event_type": "Macro"},
            {"headline": "NVDA Q1 beat", "event_type": "Earnings"},
            {"headline": "China chip tariff change", "event_type": "Regulation"},
        ],
        "market_context": {},
    }
    view = context_view_for_role(ctx, "macro_desk")
    macro_rows = view["role_focus"]["macro_articles"]
    assert any("Fed" in r["headline"] for r in macro_rows)
    assert any("tariff" in r["headline"].lower() for r in macro_rows)
    assert not any("Earnings" in r.get("event_type", "") for r in macro_rows)
