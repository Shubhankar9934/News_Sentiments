# Claude Synthesis Pipeline

**File:** `backend/app/services/llm/claude_report.py`

## Inputs

1. `ticker: str`
2. `clusters: list[dict]` — max 15 from `NarrativeCompressionService`
3. `price_ctx: dict` — last_close, volatility_regime, recent_returns, avg_daily_vol_pct

## Model call

- `POST {ANTHROPIC_BASE_URL}/v1/messages`
- `model`: `ANTHROPIC_MODEL` (default `claude-sonnet-4-6`)
- `max_tokens`: 4000
- Retries: 3 on transport errors

## Output fields (desk-critical)

| Field | Used in UI |
|-------|------------|
| `dominant_narrative`, `what_happened`, `price_movers` | AI Market Summary |
| `key_events[]` | Why Tape Is Moving |
| `source_reliability[]` | Source Stack |
| `price_prediction.*` | Snapshot, Trade panel, Risk, Verdict |
| `overall_sentiment_*` | Fallback signal / NO TRADE |

## Parsing

1. Strip ```json fences
2. `json.loads` → on fail `json_repair.loads`
3. No JSON Schema validation step

## Guardrails

- System prompt: do not re-score sentiment; JSON only; escape quotes
- No RAG beyond provided clusters + price_ctx

Full prompt text: [`../prompts/claude-prompts.md`](../prompts/claude-prompts.md)
