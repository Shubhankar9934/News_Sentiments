# Vector Search & Analogs

## Qdrant collection

| Property | Value |
|----------|-------|
| Name | `article_embeddings` (`QDRANT_COLLECTION`) |
| Size | 384 |
| Distance | COSINE |
| Model | `all-MiniLM-L6-v2` |

## Upsert payload

`article_id`, `ticker`, `headline`, `source`, `published_at`, `sentiment`, `event_type`, `impact_score`

## Dedupe search

`search_similar(embedding, limit=3)` — score > 0.92 → mark duplicate

## Historical analogs (implemented, unused)

`find_historical_analogs()`:

```python
results = search(limit=limit*3)  # global
analogs = [r for r in results if r.payload.ticker == ticker and r.score > 0.85]
```

## What the UI actually uses

`GET /analogs/{ticker}/{event_type}` → SQL:

- Filter: same ticker + same `event_type`
- Order: `impact_score DESC`, `published_at DESC`
- Limit: 5

**Gap:** UI label "Historical analogs" suggests embedding similarity; API is categorical SQL.

**Improvement path:** Wire `/analogs` to Qdrant using dominant cluster embedding, or rename UI to "Prior events of same type".
