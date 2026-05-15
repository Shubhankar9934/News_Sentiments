# Glossary

| Term | Definition |
|------|------------|
| **Research report** | JSON from Claude + `_pipeline_meta` attachment |
| **Pipeline meta** | `_pipeline_meta` — evidence, price_snapshot, run stats (backend-only truth for article rows) |
| **Cluster** | Compressed group: same `event_type` + `sentiment_label` |
| **Impact score** | Deterministic 0–1 article score (not Claude) |
| **Abnormal return** | Same-day close-to-close % (misnamed; not alpha) |
| **Vol regime** | high/medium/low from recent daily moves |
| **Desk derivation** | `deriveTradingView()` frontend heuristics |
| **Evidence** | `article_evidence[]` in pipeline meta |
| **Analog (API)** | SQL rows matching `event_type`, not embedding neighbors |
| **NO TRADE** | UI stand-aside flag; not an order type |
| **Trade quality** | A–C grade from frontend thresholds |
| **Tier 1/2/3/Social** | Source trust bucket (regex + Claude + constants) |
| **FinBERT score** | Signed probability × direction ∈ [-1,1] |
| **Dedupe threshold** | 0.92 cosine similarity default |
