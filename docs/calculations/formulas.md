# Calculation Formulas

Source of truth: [`../../detail_docs.md`](../../detail_docs.md) §3

## Impact score

**File:** `backend/app/services/impact_scoring/scorer.py`

```
impact = min(1, |sentiment_score| × (reliability/100) × 2^(-age_days/3) × event_weight × vol_mult)
```

| vol_regime | vol_mult |
|------------|----------|
| high | 1.3 |
| medium | 1.0 |
| low | 0.75 |
| unknown | 1.0 |

## Event weights (`constants.py`)

Earnings 1.0 → Analyst 0.5; default 0.5

## FinBERT sentiment

```
sentiment_score = round(P(class) × direction, 3)
```

direction: Bullish +1, Bearish -1, Neutral 0

## Volatility regime

Mean absolute daily % change over last 10 bars:

- \> 3% → high
- \> 1.5% → medium
- else low

## Dedupe

Cosine similarity > `DEDUPE_THRESHOLD` (0.92); keep higher reliability.

## NOT calculated in backend

- `price_prediction.confidence` → Claude
- Trade quality A/B/C → frontend
- News/price alignment YES/NO → frontend
