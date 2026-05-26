---
name: options opportunities section
overview: Add an additive `OPTIONS OPPORTUNITIES` section to every ticker card, slotted between Risk Indicators and Executive Summary, rendering compact CALL and PUT tables driven by a reusable `optionsData` shape ready for future IBKR Gateway wiring.
todos:
  - id: create-component
    content: Add frontend/src/components/grid/OptionsOpportunities.tsx with OptionsData types and the two-table layout
    status: completed
  - id: create-mock
    content: Add frontend/src/lib/mockOptionsData.ts exporting getMockOptionsData(ticker) returning the spec fixture
    status: completed
  - id: wire-card
    content: Insert <OptionsOpportunities data={getMockOptionsData(ticker)} /> in TickerCard.tsx between MarketIndicators and the RunningProgress/ExecutiveSummary block
    status: completed
  - id: verify
    content: Run the frontend typecheck/build and visually verify the section appears, fits within the card, and matches existing header styling
    status: completed
isProject: false
---

# Options Opportunities Card Section

## Goal

Insert a new section into every `TickerCard` that shows the best CALL and PUT setups in two compact tables, using mock data today, with a data shape that swaps cleanly for IBKR Gateway later. Strictly additive — no existing section is removed or reordered.

## Final Section Order

`CardHeader` → `ActionBar` (Run Analysis / Open Full Report) → `StatusStrip` (Decision banner) → `ExecutiveMetrics` → `MovementRiskPanel` → `MarketIndicators` (Risk Indicators) → **`OptionsOpportunities` (NEW)** → `RunningProgress` / `ExecutiveSummary` → `ReportFooter` (Last Updated).

## Data Shape (IBKR-ready)

A single reusable type lives next to the component so the backend can drop in later without touching the UI:

```ts
export type OptionLiquidity = "High" | "Medium" | "Low";

export type OptionRow = {
  combo: string;     
  exp: string;       
  premium: string;   
  margin: string;    
  liquidity: OptionLiquidity;
};

export type OptionsData = {
  calls: OptionRow[];  
  puts: OptionRow[];   
};
```

When IBKR is wired up, the server will return this same `OptionsData` shape (likely on `TickerSummaryRow`), and `TickerCard` swaps the mock for the real value — no component changes required.

## Files to Add

- `frontend/src/components/grid/OptionsOpportunities.tsx`
  - Exports `OptionsOpportunities({ data }: { data: OptionsData })`.
  - Outer wrapper: `<SectionFrame title="Options Opportunities">` (matches the casing/tracking of `EXECUTIVE METRICS`, `MOVEMENT RISK`, `RISK INDICATORS` via `.grid-card-section-title`).
  - Inside: two stacked subsections, each rendered as a small `<table>`:
    - `CALL OPPORTUNITIES` (sub-title using a 10px uppercase label, same tone as existing in-panel labels in `MovementRiskPanel`/`MarketIndicators`).
    - `PUT OPPORTUNITIES` (same structure).
  - Columns: `Combo | Exp | Premium | Margin | Liquidity`.
  - Slice rows to max 2 each: `data.calls.slice(0, 2)` and `data.puts.slice(0, 2)` to enforce the size constraint defensively even if the backend returns more.
  - Liquidity cell renders the `Chip` primitive with tone derived from value: `High → ok` (green), `Medium → warn` (amber), `Low → bad` (red). Reuses `toneBadgeClass` so dark-mode colors stay consistent with the rest of the card.

- `frontend/src/lib/mockOptionsData.ts`
  - Exports `getMockOptionsData(ticker: string): OptionsData` returning the example fixture from the spec (same values for every ticker for now, ticker arg kept so we can vary later without API churn).

## Files to Modify

- `frontend/src/components/grid/TickerCard.tsx`
  - Import `OptionsOpportunities` and `getMockOptionsData`.
  - Compute `const optionsData = getMockOptionsData(ticker);` (memoized via `useMemo` keyed on `ticker`).
  - Insert the component between `<MarketIndicators ... />` and the `isRunning ? <RunningProgress/> : <ExecutiveSummary/>` block — no other lines touched, no props removed.

## Layout & Styling Details

To fit inside the ~328px usable width with no horizontal scroll:

- Use `<table className="w-full table-fixed">` with `border-collapse` so columns don't expand.
- Column widths (proportional, table-fixed): Combo 36% · Exp 12% · Premium 16% · Margin 18% · Liquidity 18%.
- Compact typography:
  - Header row: `text-[9px] font-semibold uppercase tracking-wider text-[hsl(var(--terminal-text-secondary))]`, padding `px-2 py-1`, background `bg-[hsl(var(--terminal-card-elevated))]/70` (the "slightly darker" header band).
  - Body cells: `font-mono text-[11px] text-slate-100`, padding `px-2 py-1`, numerics use `tabular-nums`.
  - Combo cell: `truncate` with `title={combo}` for full text on hover (handles e.g. `225/227.5/232.5`).
- Container: `rounded-md border border-[hsl(var(--terminal-border))] bg-[hsl(var(--terminal-card-elevated))]/50` (matches `MarketIndicators` and `MovementRiskPanel` panels exactly).
- Each table separated by a thin divider (`border-t border-[hsl(var(--terminal-border))]`) so CALL and PUT visually segment without doubling card padding.
- Liquidity `Chip` rendered at `text-[9px]` to keep the row height aligned with body cells.

## Component Sketch

```tsx
<SectionFrame title="Options Opportunities">
  <div className="overflow-hidden rounded-md border border-[hsl(var(--terminal-border))] bg-[hsl(var(--terminal-card-elevated))]/50">
    <OptionsTable label="Call Opportunities" rows={data.calls.slice(0, 2)} />
    <div className="border-t border-[hsl(var(--terminal-border))]" />
    <OptionsTable label="Put Opportunities"  rows={data.puts.slice(0, 2)} />
  </div>
</SectionFrame>
```

`OptionsTable` is a private helper that renders the sub-title row, then a `<table>` with header + body. Liquidity cell:

```tsx
<Chip tone={liquidityTone(row.liquidity)} className="text-[9px]">
  {row.liquidity}
</Chip>
```

## Constraints Honored

- No section removed; ordering preserved; only one insertion point added in `TickerCard.tsx`.
- Card min-width / `grid-card` CSS untouched — no width regression. Existing responsive grid in `WatchlistGridPage.tsx` (`minmax(360px, 1fr)`) keeps working.
- Tables fit within ~328px content width via `table-fixed` + truncation on the Combo column; no horizontal scroll.
- Dark-only styling driven entirely off existing `--terminal-*` tokens and `Chip` tones — matches every other section.
- Max-2 rows enforced in the component, so a future backend that returns more is automatically clipped without UI overflow.

## Out of Scope

- No backend changes (no `TickerSummaryRow` schema edits, no new endpoints, no IBKR wiring).
- No edits to the full report page — this is a Layer-1 dashboard-only change.
- No tests added for the mock fixture; will be added when the real IBKR data path lands.