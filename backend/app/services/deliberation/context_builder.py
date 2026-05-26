"""Build structured deliberation context from a completed research report.



PR10 — token-budgeted compression. Earlier the context dumped up to 30

``article_evidence`` rows verbatim, which dominated the LLM input on

high-news days. We now rank evidence by ``impact_score`` and ``reliability``,

keep top-k entries, and drop low-signal fields (long URLs, ``ai_summary``

duplicates) when the running token estimate exceeds ``DIL_CONTEXT_TOKEN_BUDGET``.

"""



from __future__ import annotations



import json

from typing import Any



from app.core.config import settings as global_settings

from app.services.deliberation.context.flow import build_flow_context

from app.services.deliberation.context.liquidity import build_liquidity_context

from app.services.deliberation.context.news_momentum import build_news_momentum

from app.services.deliberation.context.regime import build_regime_context

from app.services.deliberation.context.technical import build_technical_context

from app.services.deliberation.schemas import DeliberationContext



_EVIDENCE_HARD_CAP = 30

_EVIDENCE_KEEP_KEYS = (

    "headline",

    "source",

    "published_at",

    "impact_score",

    "sentiment_label",

    "sentiment_score",

    "reliability_score",

    "event_type",

    "abnormal_return",

)





def _approx_token_count(text: str) -> int:

    if not text:

        return 0

    return max(1, len(text) // 4)





def _rank_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:

    def score(row: dict[str, Any]) -> float:

        impact = float(row.get("impact_score") or 0.0)

        rel = float(row.get("reliability_score") or 0.5)

        return impact * (0.5 + 0.5 * rel)



    return sorted(evidence, key=lambda r: (-score(r), r.get("published_at") or ""))





def _trim_row(row: dict[str, Any]) -> dict[str, Any]:

    return {k: row[k] for k in _EVIDENCE_KEEP_KEYS if k in row and row[k] is not None}





def _budget_evidence(

    evidence: list[dict[str, Any]],

    *,

    token_budget: int,

) -> list[dict[str, Any]]:

    ranked = _rank_evidence(evidence)[:_EVIDENCE_HARD_CAP]

    if not ranked:

        return []

    trimmed = [_trim_row(r) for r in ranked]

    running = 0

    out: list[dict[str, Any]] = []

    for idx, row in enumerate(trimmed):

        approx = _approx_token_count(json.dumps(row, default=str))

        if idx < 5 or running + approx <= token_budget:

            out.append(row)

            running += approx

        else:

            break

    return out





def _historical_analogs_from_meta(meta: dict[str, Any]) -> list[dict[str, Any]]:

    analogs = meta.get("historical_analogs") or []

    if isinstance(analogs, list):

        return analogs[:8]

    return []





def build_deliberation_context(report: dict[str, Any], ticker: str) -> DeliberationContext:

    meta = report.get("_pipeline_meta") or {}

    raw_evidence = meta.get("article_evidence") or []

    token_budget = getattr(global_settings, "dil_context_token_budget", 6000)

    evidence_budget = max(800, int(token_budget * 0.66))

    article_evidence = _budget_evidence(raw_evidence, token_budget=evidence_budget)



    price_snapshot = meta.get("price_snapshot") or {}

    ohlcv_series = meta.get("ohlcv_series") or []

    options_intelligence = report.get("options_intelligence") or None



    sentiment = {

        "overall_sentiment_score": report.get("overall_sentiment_score"),

        "overall_sentiment_label": report.get("overall_sentiment_label"),

        "sentiment_breakdown": report.get("sentiment_breakdown") or [],

    }

    key_events = report.get("key_events") or []



    news_momentum = build_news_momentum(article_evidence)

    technical_context = build_technical_context(ohlcv_series, price_snapshot)

    flow_context = build_flow_context(price_snapshot, options_intelligence)

    liquidity_context = build_liquidity_context(price_snapshot, options_intelligence)

    # Phase 6 — detect a macro shock and project its first-order chain.
    from app.services.deliberation.context.macro_transmission import (
        build_macro_transmission_chain,
    )

    event_drivers: list[str] = []
    if isinstance(options_intelligence, dict):
        evblock = options_intelligence.get("event_risk") or {}
        if isinstance(evblock.get("drivers"), list):
            event_drivers = [str(d) for d in evblock["drivers"]]

    macro_chain = build_macro_transmission_chain(
        ticker=ticker,
        dominant_narrative=report.get("dominant_narrative"),
        key_events=key_events,
        event_risk_drivers=event_drivers,
    )

    regime_context = build_regime_context(

        volatility_regime=meta.get("volatility_regime"),

        sentiment=sentiment,

        key_events=key_events,

        options_intelligence=options_intelligence,

        news_momentum=news_momentum,

    )



    return DeliberationContext(

        ticker=ticker.upper(),

        market_context={

            "price_prediction": report.get("price_prediction") or {},

            "price_snapshot": price_snapshot,

            "volatility_regime": meta.get("volatility_regime"),

        },

        sentiment=sentiment,

        narrative={

            "dominant_narrative": report.get("dominant_narrative"),

            "what_happened": report.get("what_happened"),

            "price_movers": report.get("price_movers"),

        },

        key_events=key_events,

        source_reliability=report.get("source_reliability") or [],

        historical_analogs=_historical_analogs_from_meta(meta),

        article_evidence=article_evidence,

        top_impact_events=meta.get("top_impact_events") or [],

        evidence_summary={

            "articles_analyzed": report.get("articles_analyzed"),

            "unique_sources": report.get("unique_sources"),

            "data_quality_note": report.get("data_quality_note"),

            "evidence_kept": len(article_evidence),

            "evidence_total": len(raw_evidence),

        },

        options_intelligence=options_intelligence,

        technical_context=technical_context,

        flow_context=flow_context,

        liquidity_context=liquidity_context,

        regime_context=regime_context,

        news_momentum=news_momentum,

        macro_transmission_chain=macro_chain,

    )


