# Financial News Research — Documentation Index

**Master reference:** [`../detail_docs.md`](../detail_docs.md) (exhaustive single-file audit)

## Structure

| Folder | Document | Topics |
|--------|----------|--------|
| [architecture/](architecture/) | [system-overview.md](architecture/system-overview.md) | Context, components, deployment |
| [calculations/](calculations/) | [formulas.md](calculations/formulas.md) | Impact, sentiment, vol, dedupe |
| [ai_pipeline/](ai_pipeline/) | [claude-synthesis.md](ai_pipeline/claude-synthesis.md) | Prompts, schema, retries |
| [frontend/](frontend/) | [ui-sections.md](frontend/ui-sections.md) | All 10 panels + hooks |
| [backend/](backend/) | [pipeline-stages.md](backend/pipeline-stages.md) | Services, routes, persistence |
| [signal_engine/](signal_engine/) | [desk-derivation.md](signal_engine/desk-derivation.md) | Trade quality, NO TRADE, alignment |
| [risk_engine/](risk_engine/) | [risk-and-contradictions.md](risk_engine/risk-and-contradictions.md) | Risk level, contradictory rules |
| [event_pipeline/](event_pipeline/) | [news-flow.md](event_pipeline/news-flow.md) | Collect → report stages |
| [vector_search/](vector_search/) | [qdrant-analogs.md](vector_search/qdrant-analogs.md) | Embeddings, Qdrant, analog gap |
| [prompts/](prompts/) | [claude-prompts.md](prompts/claude-prompts.md) | Full prompt text reference |
| [diagrams/](diagrams/) | [diagrams.md](diagrams/diagrams.md) | Mermaid diagrams |
| [glossary/](glossary/) | [terms.md](glossary/terms.md) | Domain terms |

## Quick lineage cheat sheet

```
External APIs → NewsCollector → Cleaner → FinBERT → Events → Polygon → Impact
  → Compress → Qdrant → Claude → _pipeline_meta → PostgreSQL/Redis
  → GET /research → useResearch → deriveTradingView → TradingIntelligenceDashboard
```
