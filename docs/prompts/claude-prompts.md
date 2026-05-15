# Claude Prompt Reference

**Location:** `backend/app/services/llm/claude_report.py` (inline constants — no external files)

## SYSTEM_PROMPT (summary)

Role: financial research synthesizer.

Constraints:
- Input = pre-processed clusters with FinBERT + impact
- OHLCV context provided
- Answer: dominant narrative, what happened, price movers, today's price range
- **Do NOT re-score sentiment**
- Return **only** valid JSON
- Escape `"` inside string values

## User message template

```
Ticker: {ticker}

Market context:
{price_ctx JSON}

News clusters ({n} — pre-processed, sorted by impact):
{clusters JSON}

Return the research report JSON matching this schema:
{REPORT_SCHEMA}
```

## REPORT_SCHEMA fields (desk-visible)

- `data_mode`, `data_quality_note`
- `articles_analyzed`, `unique_sources`, `duplicates_removed`
- `overall_sentiment_score`, `overall_sentiment_label`
- `sentiment_breakdown[]`
- `key_events[]` — type, description, impact, impact_score
- `dominant_narrative`, `what_happened`, `price_movers`
- `source_reliability[]` — source, articles, reliability_score, tier
- `articles[]` — per-article summary fields
- `price_prediction` — prices, change %, **confidence**, bias, vol regime, reasoning, risks

## Retry / parse

- 3 retries on `aiohttp.ClientError`
- Parse: fence strip → `json.loads` → `json_repair.loads`
