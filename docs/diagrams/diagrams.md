# Architecture Diagrams

Canonical copies also live in [`../../detail_docs.md`](../../detail_docs.md) §13.

## End-to-end data flow

```mermaid
flowchart LR
  subgraph FE [Frontend]
    DP[DashboardPage]
    TD[TradingIntelligenceDashboard]
    DT[deriveTradeDecision]
  end
  subgraph BE [Backend]
    RT[research route]
    PL[pipeline.run]
    CL[ClaudeReportService]
  end
  subgraph EXT [External]
    FH[Finnhub]
    NA[NewsAPI]
    PO[Polygon]
    AN[Anthropic]
  end
  DP -->|GET /research| RT --> PL
  PL --> FH & NA & PO
  PL --> CL --> AN
  PL -->|report + _pipeline_meta| DP
  DP --> TD --> DT
```

## WebSocket vs HTTP

```mermaid
sequenceDiagram
  participant U as User
  participant H as Run HTTP
  participant W as Run WS

  U->>H: useResearch.mutateAsync
  H-->>U: Full ResearchReport → setReport

  U->>W: useResearchProgress.run
  W-->>U: progress messages only
  Note over U,W: Report NOT auto-loaded
```

## Database ER

See [`../../detail_docs.md`](../../detail_docs.md) §7.1
