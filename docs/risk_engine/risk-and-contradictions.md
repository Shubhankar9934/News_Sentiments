# Risk Engine

## LLM risk (sections 8, 10)

From `price_prediction` in Claude JSON:

- `downside_risk` — one sentence
- `upside_catalyst` — one sentence
- `disclaimer` — static template in schema

`data_quality_note` — Claude one-liner on coverage gaps.

## Frontend risk level

`riskFrom()` in `deriveTradeDecision.ts`:

| Condition | Level |
|-----------|-------|
| Mixed + high vol | HIGH |
| High vol only | MEDIUM |
| Mixed only | MEDIUM |
| Low vol | LOW |
| Default | MEDIUM |

## Contradictory signals

Triggered when:

1. Bullish bias + `change_pct_base` < -0.5
2. Bearish bias + `change_pct_base` > 0.5
3. Bullish overall label + last session red
4. STRONG news + `volume_vs_avg` < 0.85

Rendered in Risk Panel rose box.

## Not implemented

- RSI / overbought / oversold
- Options implied vol
- Sector beta / SPY hedge ratio (UI says "not wired")
