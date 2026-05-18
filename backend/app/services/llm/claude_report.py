"""Claude report generation."""

from __future__ import annotations

import json

import aiohttp
import json_repair
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import Settings

log = structlog.get_logger(__name__)


def _sanitize_for_json(obj: object) -> object:
    """Recursively replace straight double-quotes inside string values with
    typographic curly quotes so Claude never outputs unescaped \" in its JSON."""
    if isinstance(obj, str):
        return obj.replace('"', '\u201c').replace('"', '\u201d').replace('"', '\u2019')
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(item) for item in obj]
    return obj


def _parse_report_json(blob: str) -> dict:
    """Parse model JSON; repair common LLM mistakes (unescaped quotes in headlines)."""
    try:
        out = json.loads(blob)
        if isinstance(out, dict):
            return out
    except json.JSONDecodeError as e:
        log.warning(
            "claude.report_json_strict_failed",
            error=str(e),
            pos=getattr(e, "pos", None),
            snippet=blob[max(0, (e.pos or 0) - 120) : (e.pos or 0) + 120] if getattr(e, "pos", None) is not None else blob[:240],
        )
    try:
        out = json_repair.loads(blob)
    except Exception as e:
        log.error("claude.report_json_repair_failed", error=str(e), head=blob[:500])
        raise ValueError("Could not parse research JSON from model response") from e
    if not isinstance(out, dict):
        raise ValueError("Research JSON root must be an object")
    return out


class ClaudeReportService:
    SYSTEM_PROMPT = (
        "You are a financial research synthesizer. You receive pre-processed, deduplicated "
        "news clusters with FinBERT sentiment and event impact scores already computed. "
        "Market price data (OHLCV) is also provided where available.\n\n"
        "Your ONLY job is to synthesize, reason, and explain:\n"
        "1. What is the dominant narrative?\n"
        "2. What happened (grounded in the clusters provided)?\n"
        "3. Which events most likely moved price (use abnormal_return data if available)?\n"
        "4. Generate a price range estimate for today grounded in the news and OHLCV data.\n\n"
        "Do NOT re-score sentiment. Use the provided scores.\n"
        "Return ONLY valid JSON — no markdown, no backticks, no explanation.\n"
        "CRITICAL: Inside every JSON string value, escape any double-quote as \\\". "
        "Never put raw \" inside headline or description strings."
    )

    REPORT_SCHEMA = (
        "{\n"
        '  "data_mode": "real",\n'
        '  "data_quality_note": "<one sentence>",\n'
        '  "articles_analyzed": <int>,\n'
        '  "unique_sources": <int>,\n'
        '  "duplicates_removed": <int>,\n'
        '  "overall_sentiment_score": <float -1 to 1>,\n'
        '  "overall_sentiment_label": "Bullish|Bearish|Neutral|Mixed",\n'
        '  "sentiment_breakdown": [\n'
        '    {"label":"Bullish","count":<int>,"pct":<float>,"score":0.7},\n'
        '    {"label":"Neutral","count":<int>,"pct":<float>,"score":0.0},\n'
        '    {"label":"Bearish","count":<int>,"pct":<float>,"score":-0.6}\n'
        "  ],\n"
        '  "key_events": [\n'
        '    {"type":"<type>","description":"<one sentence>",'
        '"impact":"High|Medium|Low","impact_score":<float>}\n'
        "  ],\n"
        '  "dominant_narrative": "<one sentence>",\n'
        '  "what_happened": "<two sentences>",\n'
        '  "price_movers": "<one sentence — cite abnormal_return if available>",\n'
        '  "source_reliability": [\n'
        '    {"source":"<name>","articles":<int>,"reliability_score":<int>,'
        '"tier":"Tier 1|Tier 2|Tier 3|Social|Primary"}\n'
        "  ],\n"
        '  "articles": [\n'
        '    {"headline":"<string>","source":"<string>","published_at":"<date>",'
        '"sentiment":<float>,"sentiment_label":"Bullish|Bearish|Neutral",'
        '"event_type":"<type>|null","reliability_score":<int>,"impact_score":<float>}\n'
        "  ],\n"
        '  "price_prediction": {\n'
        '    "last_close":<float>,"low":<float>,"base":<float>,"high":<float>,\n'
        '    "change_pct_low":<float>,"change_pct_base":<float>,"change_pct_high":<float>,\n'
        '    "confidence":<int>,"bias":"Bullish|Bearish|Neutral",\n'
        '    "volatility_regime":"low|medium|high",\n'
        '    "reasoning":"<two sentences citing real clusters and OHLCV>",\n'
        '    "upside_catalyst":"<one sentence>",\n'
        '    "downside_risk":"<one sentence>",\n'
        '    "disclaimer":"News-sentiment model with real data. Not financial advice."\n'
        "  }\n"
        "}"
    )

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def generate(self, ticker: str, clusters: list[dict], price_ctx: dict) -> dict:
        safe_clusters = _sanitize_for_json(clusters)
        safe_price_ctx = _sanitize_for_json(price_ctx)
        user_msg = (
            f"Ticker: {ticker}\n\n"
            f"Market context:\n{json.dumps(safe_price_ctx, indent=2)}\n\n"
            f"News clusters ({len(clusters)} — pre-processed, sorted by impact):\n"
            f"{json.dumps(safe_clusters, indent=2)}\n\n"
            f"Return the research report JSON matching this schema:\n{self.REPORT_SCHEMA}"
        )

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(min=2, max=15),
            retry=retry_if_exception_type(aiohttp.ClientError),
        )
        async def _call() -> dict:
            base = self._settings.anthropic_base_url.rstrip("/")
            url = f"{base}/v1/messages"
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    url,
                    headers={
                        "x-api-key": self._settings.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self._settings.anthropic_model,
                        "max_tokens": 4000,
                        "system": self.SYSTEM_PROMPT,
                        "messages": [{"role": "user", "content": user_msg}],
                    },
                ) as resp:
                    raw = await resp.read()
                    if resp.status >= 400:
                        log.error(
                            "anthropic.messages_error",
                            status=resp.status,
                            model=self._settings.anthropic_model,
                            body=raw.decode(errors="replace")[:2000],
                        )
                    resp.raise_for_status()
                    return json.loads(raw)

        data = await _call()
        if data.get("error"):
            raise RuntimeError(data["error"]["message"])
        text = "".join(b.get("text", "") for b in data.get("content", []))
        clean = text.replace("```json", "").replace("```", "").strip()
        start, end = clean.find("{"), clean.rfind("}")
        if start == -1:
            raise ValueError("No JSON in Claude response")
        return _parse_report_json(clean[start : end + 1])
