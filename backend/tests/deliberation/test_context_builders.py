"""Tests for deterministic deliberation context builders."""

from app.services.deliberation.context.news_momentum import build_news_momentum
from app.services.deliberation.context.regime import build_regime_context
from app.services.deliberation.context.technical import build_technical_context
from app.services.deliberation.context_builder import build_deliberation_context


def test_technical_context_computes_rsi():
    series = [{"c": 100 + i, "h": 101 + i, "l": 99 + i, "v": 1_000_000} for i in range(30)]
    ctx = build_technical_context(series, {"last_session_change_pct": 1.2})
    assert ctx["rsi_14"] is not None
    assert ctx["trend"] in ("uptrend", "downtrend", "range_bound")


def test_news_momentum_from_evidence():
    evidence = [
        {"sentiment_label": "Bullish", "published_at": "2026-05-24T10:00:00+00:00"},
        {"sentiment_label": "Bearish", "published_at": "2026-05-23T10:00:00+00:00"},
    ]
    mom = build_news_momentum(evidence)
    assert "label" in mom
    assert mom["articles_48h"] >= 1


def test_regime_context_primary_label():
    regime = build_regime_context(
        volatility_regime="high",
        sentiment={"overall_sentiment_label": "Bearish"},
        key_events=[{"event_type": "Macro"}, {"event_type": "Macro"}],
        options_intelligence={"event_risk": {"label": "High"}},
        news_momentum={"label": "accelerating_bearish"},
    )
    assert regime["primary_regime"]
    assert "Macro Week" in regime["regime_tags"]


def test_context_builder_includes_specialized_blocks():
    report = {
        "overall_sentiment_label": "Bullish",
        "key_events": [],
        "_pipeline_meta": {
            "volatility_regime": "medium",
            "price_snapshot": {"avg_volume_20d": 2_000_000},
            "ohlcv_series": [{"c": 100, "h": 101, "l": 99, "v": 500_000}] * 25,
            "article_evidence": [],
        },
    }
    ctx = build_deliberation_context(report, "AAPL")
    assert ctx.technical_context is not None
    assert ctx.regime_context is not None
    assert ctx.news_momentum is not None
