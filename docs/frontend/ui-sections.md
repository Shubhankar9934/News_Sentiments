# Frontend UI Sections

**Master:** [`../../detail_docs.md`](../../detail_docs.md) §2, §6

**Single component:** `frontend/src/components/trading/TradingIntelligenceDashboard.tsx`

| # | Section | Primary data | Transform |
|---|---------|--------------|-----------|
| 1 | Stock Snapshot | `_pipeline_meta`, `deriveTradingView` | Pills, dl grid |
| 2 | AI Market Summary | Claude narrative fields | Verbatim |
| 3 | Trade Decision | `deriveTradingView`, `price_prediction` | NO TRADE, strategy |
| 4 | Why Tape Moving | `key_events`, `eventConfirm` | Sort by impact_score |
| 5 | Source Stack | `source_reliability`, tones | SourceBadge |
| 6 | News/Price Alignment | `derived.alignment` | All frontend |
| 7 | Historical Analogs | `useAnalogs` → SQL rows | Top 5 |
| 8 | Risk Panel | Claude + contradictory | List |
| 9 | Evidence Timeline | `article_evidence` | NewsTimeline |
| 10 | Final Verdict | bias + whyImportant | List |
| — | Evidence Deck | top 10 evidence | NewsCard |
| — | Charts | report aggregates | ResearchReportCharts |

## Hooks (`hooks/useApi.ts`)

- `useResearch` — mutation, `GET /research/{ticker}?days=`
- `useAnalogs` — `GET /analogs/{ticker}/{eventType}`
- `useHistory` — cached reports
- `useHealth` — infra status

**Not present:** `useResearchQuery`, `useSignalMetrics`

## State

- `report` in `DashboardPage` useState (WS run does **not** set it)
- Theme: Zustand `useThemeStore` (persisted)
