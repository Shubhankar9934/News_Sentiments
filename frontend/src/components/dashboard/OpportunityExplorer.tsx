/**
 * Section 3 of the Full Report — the Reverse BWB Opportunity Explorer.
 *
 * Renders every active opportunity for a ticker with rich per-leg
 * detail. Filters (CALL/PUT, DTE, delta, premium, margin, liquidity,
 * credit efficiency), six sort columns, and virtualized rendering so
 * thousand-row chains stay responsive. A history-snapshot picker pulls
 * past cycles from ``ticker_option_opportunity_history``.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { useQuery } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";

import { apiClient } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

// Plain input styled to match the rest of the report UI; we don't pull in
// a full shadcn `<Input>` because the explorer only ever needs numeric /
// date inputs and a tighter footprint than the default.
function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={cn(
        "h-7 rounded border border-slate-300 bg-white px-1 text-[11px] dark:border-slate-700 dark:bg-slate-800",
        props.className,
      )}
    />
  );
}
import {
  opportunityExplorerResponseSchema,
  opportunityHistoryResponseSchema,
  type LiveOpportunity,
  type OpportunityHistoryEntry,
} from "@/types/schemas";

type SortKey =
  | "ranking_score"
  | "credit_efficiency"
  | "premium"
  | "init_margin"
  | "liquidity"
  | "delta_pct"
  | "expiry_days";

type Order = "asc" | "desc";

type SideFilter = "all" | "call" | "put";

type Filters = {
  side: SideFilter;
  dteMin: string;
  dteMax: string;
  deltaMin: string;
  deltaMax: string;
  premiumMin: string;
  premiumMax: string;
  marginMin: string;
  marginMax: string;
  liquidityMin: string;
  creditEfficiencyMin: string;
};

const INITIAL_FILTERS: Filters = {
  side: "all",
  dteMin: "",
  dteMax: "",
  deltaMin: "",
  deltaMax: "",
  premiumMin: "",
  premiumMax: "",
  marginMin: "",
  marginMax: "",
  liquidityMin: "",
  creditEfficiencyMin: "",
};

const COLUMNS: Array<{
  key: SortKey;
  label: string;
  className: string;
  align: "left" | "right";
}> = [
  { key: "ranking_score", label: "Score", className: "w-[6%]", align: "right" },
  { key: "ranking_score", label: "Side", className: "w-[5%]", align: "left" },
  { key: "ranking_score", label: "Combo", className: "w-[11%]", align: "left" },
  { key: "expiry_days", label: "Exp", className: "w-[5%]", align: "right" },
  { key: "delta_pct", label: "Δ %", className: "w-[6%]", align: "right" },
  { key: "premium", label: "Premium", className: "w-[8%]", align: "right" },
  { key: "init_margin", label: "Margin", className: "w-[7%]", align: "right" },
  { key: "liquidity", label: "Liquidity", className: "w-[7%]", align: "right" },
  { key: "credit_efficiency", label: "Cred Eff", className: "w-[7%]", align: "right" },
  { key: "liquidity", label: "OI Legs", className: "w-[10%]", align: "right" },
  { key: "liquidity", label: "Vol Legs", className: "w-[10%]", align: "right" },
  { key: "ranking_score", label: "IV", className: "w-[7%]", align: "right" },
  { key: "ranking_score", label: "Under", className: "w-[6%]", align: "right" },
];

const FETCH_LIMIT = 500;

type Props = {
  ticker: string;
};

export function OpportunityExplorer({ ticker }: Props) {
  const [filters, setFilters] = useState<Filters>(INITIAL_FILTERS);
  const [sortKey, setSortKey] = useState<SortKey>("ranking_score");
  const [order, setOrder] = useState<Order>("desc");
  const [historyDate, setHistoryDate] = useState<string>("");

  const liveQuery = useExplorerQuery({
    ticker,
    filters,
    sortKey,
    order,
    enabled: !historyDate,
  });

  const historyQuery = useHistoryQuery({
    ticker,
    snapshotDate: historyDate,
    enabled: !!historyDate,
  });

  const isLoading = historyDate ? historyQuery.isLoading : liveQuery.isLoading;
  const isFetching = historyDate ? historyQuery.isFetching : liveQuery.isFetching;
  const rows = historyDate
    ? historyQuery.data?.rows ?? []
    : liveQuery.data?.rows ?? [];
  const total = historyDate
    ? historyQuery.data?.total ?? 0
    : liveQuery.data?.total ?? 0;

  return (
    <Card className="flex flex-col gap-4 p-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">Reverse BWB Opportunity Explorer</h2>
          <p className="mt-0.5 text-[12px] text-slate-500 dark:text-slate-400">
            Every valid Reverse BWB structure for {ticker.toUpperCase()} — fully
            filterable, sortable, virtualized.
          </p>
        </div>
        <div className="flex items-center gap-2 text-[12px]">
          <label className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
            Snapshot:
            <input
              type="date"
              value={historyDate}
              onChange={(e) => setHistoryDate(e.target.value)}
              className="h-7 rounded border bg-white px-1 text-[12px] dark:bg-slate-800"
            />
          </label>
          {historyDate && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setHistoryDate("")}
              className="h-7 text-[12px]"
            >
              Live
            </Button>
          )}
          <span className="font-mono text-slate-500 dark:text-slate-400">
            {isFetching ? "Loading…" : `${total.toLocaleString()} rows`}
          </span>
        </div>
      </header>

      <FilterPanel filters={filters} onChange={setFilters} disabled={!!historyDate} />

      <VirtualizedExplorerTable
        rows={rows}
        sortKey={sortKey}
        order={order}
        onSortChange={(key) => {
          if (key === sortKey) {
            setOrder((prev) => (prev === "asc" ? "desc" : "asc"));
          } else {
            setSortKey(key);
            setOrder("desc");
          }
        }}
        isLoading={isLoading}
      />
    </Card>
  );
}

function FilterPanel({
  filters,
  onChange,
  disabled,
}: {
  filters: Filters;
  onChange: (f: Filters) => void;
  disabled: boolean;
}) {
  const update = <K extends keyof Filters>(key: K, value: Filters[K]) =>
    onChange({ ...filters, [key]: value });

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
      <div className="flex flex-col gap-1 text-[11px]">
        <label className="text-slate-500 dark:text-slate-400">Side</label>
        <select
          value={filters.side}
          onChange={(e) => update("side", e.target.value as SideFilter)}
          disabled={disabled}
          className="h-7 rounded border bg-white px-1 text-[11px] dark:bg-slate-800"
        >
          <option value="all">All</option>
          <option value="call">CALL</option>
          <option value="put">PUT</option>
        </select>
      </div>
      <RangeFilter
        label="DTE"
        minValue={filters.dteMin}
        maxValue={filters.dteMax}
        onMin={(v) => update("dteMin", v)}
        onMax={(v) => update("dteMax", v)}
        disabled={disabled}
      />
      <RangeFilter
        label="Δ %"
        minValue={filters.deltaMin}
        maxValue={filters.deltaMax}
        onMin={(v) => update("deltaMin", v)}
        onMax={(v) => update("deltaMax", v)}
        disabled={disabled}
      />
      <RangeFilter
        label="Premium"
        minValue={filters.premiumMin}
        maxValue={filters.premiumMax}
        onMin={(v) => update("premiumMin", v)}
        onMax={(v) => update("premiumMax", v)}
        disabled={disabled}
      />
      <RangeFilter
        label="Margin"
        minValue={filters.marginMin}
        maxValue={filters.marginMax}
        onMin={(v) => update("marginMin", v)}
        onMax={(v) => update("marginMax", v)}
        disabled={disabled}
      />
      <div className="flex flex-col gap-1 text-[11px]">
        <label className="text-slate-500 dark:text-slate-400">Liquidity ≥</label>
        <Input
          value={filters.liquidityMin}
          onChange={(e) => update("liquidityMin", e.target.value)}
          disabled={disabled}
          className="h-7 text-[11px]"
        />
      </div>
      <div className="col-span-2 flex flex-col gap-1 text-[11px] sm:col-span-3 lg:col-span-1">
        <label className="text-slate-500 dark:text-slate-400">Cred Eff ≥</label>
        <Input
          value={filters.creditEfficiencyMin}
          onChange={(e) => update("creditEfficiencyMin", e.target.value)}
          disabled={disabled}
          className="h-7 text-[11px]"
        />
      </div>
    </div>
  );
}

function RangeFilter({
  label,
  minValue,
  maxValue,
  onMin,
  onMax,
  disabled,
}: {
  label: string;
  minValue: string;
  maxValue: string;
  onMin: (v: string) => void;
  onMax: (v: string) => void;
  disabled: boolean;
}) {
  return (
    <div className="flex flex-col gap-1 text-[11px]">
      <label className="text-slate-500 dark:text-slate-400">{label}</label>
      <div className="flex items-center gap-1">
        <Input
          value={minValue}
          placeholder="min"
          onChange={(e) => onMin(e.target.value)}
          disabled={disabled}
          className="h-7 w-full text-[11px]"
        />
        <Input
          value={maxValue}
          placeholder="max"
          onChange={(e) => onMax(e.target.value)}
          disabled={disabled}
          className="h-7 w-full text-[11px]"
        />
      </div>
    </div>
  );
}

function VirtualizedExplorerTable({
  rows,
  sortKey,
  order,
  onSortChange,
  isLoading,
}: {
  rows: (LiveOpportunity | OpportunityHistoryEntry)[];
  sortKey: SortKey;
  order: Order;
  onSortChange: (key: SortKey) => void;
  isLoading: boolean;
}) {
  const parentRef = useRef<HTMLDivElement | null>(null);

  // Server already sorts; we still slice in memory for in-flight feel.
  const display = useMemo(() => rows, [rows]);

  const virtualizer = useVirtualizer({
    count: display.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 28,
    overscan: 20,
  });

  return (
    <div className="overflow-hidden rounded-md border">
      <div className="border-b bg-slate-50 dark:border-slate-800 dark:bg-slate-900/60">
        <div className="flex w-full font-mono text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">
          {COLUMNS.map((col, i) => (
            <button
              key={`${col.label}-${i}`}
              type="button"
              onClick={() => onSortChange(col.key)}
              className={cn(
                "select-none px-1 py-1.5 transition-colors hover:text-slate-900 dark:hover:text-slate-100",
                col.align === "right" ? "text-right" : "text-left",
                col.className,
                sortKey === col.key && "font-semibold text-slate-900 dark:text-slate-100",
              )}
            >
              {col.label}
              {sortKey === col.key ? (order === "asc" ? " ↑" : " ↓") : ""}
            </button>
          ))}
        </div>
      </div>
      <div
        ref={parentRef}
        style={{ height: 480, overflowY: "auto" }}
        className="font-mono text-[11px]"
      >
        {display.length === 0 ? (
          <div className="flex h-full items-center justify-center text-slate-500 dark:text-slate-400">
            {isLoading ? "Loading…" : "No opportunities match the current filters"}
          </div>
        ) : (
          <div
            style={{
              height: virtualizer.getTotalSize(),
              position: "relative",
              width: "100%",
            }}
          >
            {virtualizer.getVirtualItems().map((vRow) => {
              const row = display[vRow.index];
              return (
                <ExplorerRow
                  key={`${row.combo}-${vRow.index}`}
                  row={row}
                  top={vRow.start}
                  height={vRow.size}
                />
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function ExplorerRow({
  row,
  top,
  height,
}: {
  row: LiveOpportunity | OpportunityHistoryEntry;
  top: number;
  height: number;
}) {
  const premium = row.premium ?? 0;
  const premiumDollars = Number((premium * 100).toFixed(2));
  const premiumClass =
    premiumDollars < 0
      ? "text-emerald-600 dark:text-emerald-400"
      : premiumDollars > 0
        ? "text-rose-600 dark:text-rose-400"
        : "";

  const fmtMoney = (v: number | null | undefined) =>
    v == null || !Number.isFinite(v)
      ? "—"
      : Math.abs(v) >= 1000
        ? `$${Math.round(v).toLocaleString()}`
        : `$${v.toFixed(2)}`;

  return (
    <div
      style={{
        position: "absolute",
        top,
        height,
        left: 0,
        right: 0,
      }}
      className="flex w-full items-center border-b border-slate-200/70 last:border-b-0 hover:bg-slate-50 dark:border-slate-800/60 dark:hover:bg-slate-900/40"
    >
      <div className="w-[6%] px-1 py-1 text-right tabular-nums">
        {row.ranking_score != null ? row.ranking_score.toFixed(3) : "—"}
      </div>
      <div className="w-[5%] px-1 py-1 text-left">
        <span
          className={cn(
            "rounded px-1 text-[9px] font-semibold uppercase",
            row.side === "call"
              ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300"
              : "bg-rose-100 text-rose-700 dark:bg-rose-500/20 dark:text-rose-300",
          )}
        >
          {row.side}
        </span>
      </div>
      <div className="w-[11%] truncate px-1 py-1 text-left" title={row.combo}>
        {row.combo}
      </div>
      <div className="w-[5%] px-1 py-1 text-right">{row.expiration}</div>
      <div className="w-[6%] px-1 py-1 text-right">
        {row.delta_pct != null ? `${row.delta_pct.toFixed(2)}%` : "—"}
      </div>
      <div className={cn("w-[8%] px-1 py-1 text-right tabular-nums", premiumClass)}>
        {fmtMoney(premiumDollars)}
      </div>
      <div className="w-[7%] px-1 py-1 text-right tabular-nums">
        {fmtMoney(row.init_margin ?? row.maint_margin)}
      </div>
      <div className="w-[7%] px-1 py-1 text-right tabular-nums">
        {row.liquidity ? row.liquidity.toLocaleString() : "—"}
      </div>
      <div className="w-[7%] px-1 py-1 text-right tabular-nums">
        {row.credit_efficiency != null ? `${row.credit_efficiency.toFixed(1)}%` : "—"}
      </div>
      <div className="w-[10%] truncate px-1 py-1 text-right tabular-nums" title="OI per leg">
        {[row.oi_leg1, row.oi_leg2, row.oi_leg3].map((v) => v ?? "—").join("/")}
      </div>
      <div className="w-[10%] truncate px-1 py-1 text-right tabular-nums" title="Volume per leg">
        {[row.vol_leg1, row.vol_leg2, row.vol_leg3].map((v) => v ?? "—").join("/")}
      </div>
      <div className="w-[7%] px-1 py-1 text-right">
        {row.iv != null ? `${(row.iv * 100).toFixed(1)}%` : "—"}
      </div>
      <div className="w-[6%] px-1 py-1 text-right tabular-nums">
        {row.underlying_price != null ? row.underlying_price.toFixed(2) : "—"}
      </div>
    </div>
  );
}

function useExplorerQuery(opts: {
  ticker: string;
  filters: Filters;
  sortKey: SortKey;
  order: Order;
  enabled: boolean;
}) {
  const { ticker, filters, sortKey, order, enabled } = opts;
  const [debouncedFilters, setDebouncedFilters] = useState(filters);

  // 300ms debounce so the user can type without hammering the API.
  useEffect(() => {
    const id = setTimeout(() => setDebouncedFilters(filters), 300);
    return () => clearTimeout(id);
  }, [filters]);

  const params = useMemo(() => buildParams(debouncedFilters, sortKey, order), [
    debouncedFilters,
    sortKey,
    order,
  ]);

  return useQuery({
    queryKey: [
      "opportunity-explorer",
      ticker,
      params,
    ],
    queryFn: async () => {
      const { data } = await apiClient.get(
        `/tickers/${encodeURIComponent(ticker)}/opportunity-explorer`,
        { params: { ...params, limit: FETCH_LIMIT } },
      );
      const parsed = opportunityExplorerResponseSchema.safeParse(data);
      if (!parsed.success) {
        throw new Error("opportunity_explorer_response_malformed");
      }
      return parsed.data;
    },
    enabled: enabled && ticker.length > 0,
    staleTime: 5_000,
    refetchInterval: 15_000,
  });
}

function useHistoryQuery(opts: {
  ticker: string;
  snapshotDate: string;
  enabled: boolean;
}) {
  const { ticker, snapshotDate, enabled } = opts;
  return useQuery({
    queryKey: ["opportunity-history", ticker, snapshotDate],
    queryFn: async () => {
      const { data } = await apiClient.get(
        `/tickers/${encodeURIComponent(ticker)}/opportunity-history`,
        {
          params: {
            snapshot_date: snapshotDate,
            limit: 2000,
          },
        },
      );
      const parsed = opportunityHistoryResponseSchema.safeParse(data);
      if (!parsed.success) throw new Error("opportunity_history_response_malformed");
      return parsed.data;
    },
    enabled: enabled && ticker.length > 0 && snapshotDate.length > 0,
    staleTime: 60_000,
  });
}

function buildParams(
  filters: Filters,
  sortKey: SortKey,
  order: Order,
): Record<string, string> {
  const out: Record<string, string> = { sort: sortKey, order };
  if (filters.side !== "all") out.side = filters.side;
  const numeric: Array<[keyof Filters, string]> = [
    ["dteMin", "dte_min"],
    ["dteMax", "dte_max"],
    ["deltaMin", "delta_min"],
    ["deltaMax", "delta_max"],
    ["premiumMin", "premium_min"],
    ["premiumMax", "premium_max"],
    ["marginMin", "margin_min"],
    ["marginMax", "margin_max"],
    ["liquidityMin", "liquidity_min"],
    ["creditEfficiencyMin", "credit_efficiency_min"],
  ];
  for (const [k, q] of numeric) {
    const raw = filters[k];
    if (raw === "" || raw == null) continue;
    const num = Number(raw);
    if (!Number.isFinite(num)) continue;
    out[q] = String(num);
  }
  return out;
}
