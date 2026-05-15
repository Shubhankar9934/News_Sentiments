# Event Pipeline — News Flow

```mermaid
flowchart TD
  R[Raw APIs] --> V[Validate headline > 10 chars]
  V --> F[MD5 fingerprint dedupe]
  F --> E[Embed MiniLM 384d]
  E --> S[Semantic dedupe cos > 0.92]
  S --> B[FinBERT batch 16]
  B --> K[Keyword event scores]
  K --> P[Polygon join daily return]
  P --> I[Impact score]
  I --> G[Group event_type + sentiment]
  G --> C[Top 15 clusters]
  C --> Q[Qdrant upsert]
  C --> L[Claude report]
  I --> DB[(processed_articles)]
  L --> DB2[(research_reports)]
```

## Collector source mapping

| ID prefix | API | Source field |
|-----------|-----|--------------|
| `fh-` | Finnhub | `item.source` |
| `na-` | NewsAPI | `source.name` |
| `pg-` | Polygon | `publisher.name` |

## Event extraction

Keyword count winner per article. Ties broken by Python `max()` ordering on dict keys (insertion order dependent).

## Compression cluster shape

```json
{
  "event_type", "sentiment", "sentiment_score", "article_count",
  "impact_score", "top_headline", "abnormal_return", "headlines": [...]
}
```

See [`../../detail_docs.md`](../../detail_docs.md) §5 for full stage table.
