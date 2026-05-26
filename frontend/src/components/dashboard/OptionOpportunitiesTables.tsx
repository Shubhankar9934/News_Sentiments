/**
 * Section 3 of the Reverse BWB Trading Workstation ticker card —
 * two stacked virtualized opportunity tables (CALL + PUT).
 *
 * Columns (per spec):
 *   Combo | Exp | Delta % | Premium | Margin | Liquidity | Cred Eff | Score
 *
 * Liquidity is rendered as a raw integer (the min open-interest across
 * the three legs), never "Good"/"Excellent"/etc. Premium is sign-coloured:
 * negative => credit (green), positive => debit (red).
 *
 * Each section is fixed-height with `position: sticky` header and uses
 * `@tanstack/react-virtual` so a ticker that produces thousands of
 * opportunities still scrolls smoothly. Click any column header to sort.
 */

import { useMemo, useRef, useState } from "react";

import { useVirtualizer } from "@tanstack/react-virtual";

import { SectionTitle } from "@/components/grid/primitives";
import { cn } from "@/lib/utils";
import type {
  FeedStatus,
  LiveOpportunity,
  LiveOpportunityBundle,
} from "@/types/schemas";

type Props = {
  /** Live IBKR rows. */
  live?: LiveOpportunityBundle | null | undefined;
  /** Top-level live feed status (drives the empty-state copy). */
  feedStatus?: FeedStatus;
};

type SortKey =
  | "ranking_score"
  | "credit_efficiency"
  | "premium"
  | "init_margin"
  | "liquidity"
  | "delta_pct"
  | "expiry_days";

type SortOrder = "asc" | "desc";

type DisplayRow = {
  key: string;
  combo: string;
  expiry: string;
  expiryDays: number | null;
  deltaPct: number | null;
  premiumDollars: number; // sign-preserved, x100 for contract value
  premiumPerShare: number;
  margin: number | null;
  marginSource: "deterministic" | "whatif";
  liquidity: number;
  creditEfficiency: number | null;
  score: number | null;
};

const ROW_HEIGHT_PX = 26;
const TABLE_HEIGHT_PX = 320;

function liveToRow(r: LiveOpportunity, idx: number): DisplayRow {
  return {
    key: `${r.combo}-${r.expiration}-${r.rank}-${idx}`,
    combo: r.combo,
    expiry: r.expiration,
    expiryDays: r.expiry_days ?? null,
    deltaPct: r.delta_pct ?? null,
    premiumDollars: Number((r.premium * 100).toFixed(2)),
    premiumPerShare: r.premium,
    margin: r.init_margin ?? r.maint_margin ?? null,
    marginSource: r.init_margin_source ?? "deterministic",
    liquidity: r.liquidity ?? 0,
    creditEfficiency: r.credit_efficiency ?? null,
    score: r.ranking_score ?? null,
  };
}


function formatMoney(value: number | null, signed = false): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const sign = signed ? (value < 0 ? "-" : value > 0 ? "+" : "") : "";
  const abs = Math.abs(value);
  if (abs >= 1000) return `${sign}$${abs.toFixed(0)}`;
  return `${sign}$${abs.toFixed(2)}`;
}

function formatPct(value: number | null, fractionDigits = 2): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(fractionDigits)}%`;
}

function formatLiquidity(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "—";
  return Math.round(value).toLocaleString();
}

function compareRows(a: DisplayRow, b: DisplayRow, key: SortKey, order: SortOrder) {
  const av = readSortValue(a, key);
  const bv = readSortValue(b, key);
  if (av === null && bv === null) return 0;
  if (av === null) return 1;
  if (bv === null) return -1;
  return order === "asc" ? av - bv : bv - av;
}

function readSortValue(row: DisplayRow, key: SortKey): number | null {
  switch (key) {
    case "ranking_score":
      return row.score;
    case "credit_efficiency":
      return row.creditEfficiency;
    case "premium":
      return row.premiumDollars;
    case "init_margin":
      return row.margin;
    case "liquidity":
      return row.liquidity;
    case "delta_pct":
      return row.deltaPct;
    case "expiry_days":
      return row.expiryDays;
  }
}

type Column = {
  key: SortKey;
  label: string;
  className: string;
  textAlign: "left" | "right";
};

const COLUMNS: Column[] = [
  { key: "ranking_score", label: "Combo", className: "w-[20%]", textAlign: "left" },
  { key: "expiry_days", label: "Exp", className: "w-[8%]", textAlign: "right" },
  { key: "delta_pct", label: "Δ %", className: "w-[10%]", textAlign: "right" },
  { key: "premium", label: "Premium", className: "w-[13%]", textAlign: "right" },
  { key: "init_margin", label: "Margin", className: "w-[12%]", textAlign: "right" },
  { key: "liquidity", label: "Liquidity", className: "w-[12%]", textAlign: "right" },
  { key: "credit_efficiency", label: "Cred Eff", className: "w-[12%]", textAlign: "right" },
  { key: "ranking_score", label: "Score", className: "w-[13%]", textAlign: "right" },
];

function VirtualizedTable({
  label,
  rows,
  emptyMessage,
}: {
  label: string;
  rows: DisplayRow[];
  emptyMessage: string;
}) {
  const parentRef = useRef<HTMLDivElement | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("ranking_score");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");

  const sortedRows = useMemo(() => {
    if (rows.length === 0) return rows;
    return [...rows].sort((a, b) => compareRows(a, b, sortKey, sortOrder));
  }, [rows, sortKey, sortOrder]);

  const virtualizer = useVirtualizer({
    count: sortedRows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT_PX,
    overscan: 10,
  });

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortOrder("desc");
    }
  };

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--terminal-text-secondary))]">
          {label}
        </span>
        <span className="font-mono text-[10px] text-[hsl(var(--terminal-text-tertiary))]">
          {sortedRows.length.toLocaleString()} rows
        </span>
      </div>
      {sortedRows.length === 0 ? (
        <div className="rounded-md border border-dashed border-[hsl(var(--terminal-border))] px-2 py-2 text-center font-mono text-[10px] text-[hsl(var(--terminal-text-tertiary))]">
          {emptyMessage}
        </div>
      ) : (
        <div className="overflow-hidden rounded-md border border-[hsl(var(--terminal-border))] bg-[hsl(var(--terminal-card-elevated))]/60">
          {/* Sticky header sits OUTSIDE the scrolling region so the table
              borders line up cleanly under it. */}
          <div className="border-b border-[hsl(var(--terminal-border))] bg-[hsl(var(--terminal-card-elevated))]">
            <div className="flex w-full font-mono text-[10px] uppercase tracking-wider text-[hsl(var(--terminal-text-secondary))]">
              {COLUMNS.map((col, i) => (
                <button
                  key={`${col.label}-${i}`}
                  type="button"
                  onClick={() => handleSort(col.key)}
                  className={cn(
                    "select-none px-1 py-1 font-semibold transition-colors hover:text-[hsl(var(--terminal-text-primary))]",
                    col.textAlign === "right" ? "text-right" : "text-left",
                    col.className,
                    sortKey === col.key && "text-[hsl(var(--terminal-text-primary))]",
                  )}
                  title={`Sort by ${col.label}`}
                >
                  {col.label}
                  {sortKey === col.key ? (sortOrder === "asc" ? " ↑" : " ↓") : ""}
                </button>
              ))}
            </div>
          </div>
          <div
            ref={parentRef}
            style={{ height: TABLE_HEIGHT_PX, overflowY: "auto" }}
            className="font-mono text-[11px]"
          >
            <div
              style={{
                height: virtualizer.getTotalSize(),
                position: "relative",
                width: "100%",
              }}
            >
              {virtualizer.getVirtualItems().map((vRow) => {
                const row = sortedRows[vRow.index];
                return (
                  <RowDisplay
                    key={row.key}
                    row={row}
                    top={vRow.start}
                    height={vRow.size}
                  />
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function RowDisplay({
  row,
  top,
  height,
}: {
  row: DisplayRow;
  top: number;
  height: number;
}) {
  const premiumClass =
    row.premiumDollars < 0
      ? "text-emerald-400"
      : row.premiumDollars > 0
        ? "text-rose-400"
        : "text-[hsl(var(--terminal-text-primary))]";
  return (
    <div
      style={{
        position: "absolute",
        top,
        height,
        left: 0,
        right: 0,
      }}
      className="flex w-full items-center border-b border-[hsl(var(--terminal-border))]/40 last:border-b-0"
    >
      <div className="w-[20%] truncate px-1 py-1 text-left text-[hsl(var(--terminal-text-primary))]" title={row.combo}>
        {row.combo}
      </div>
      <div className="w-[8%] px-1 py-1 text-right text-[hsl(var(--terminal-text-primary))]">
        {row.expiry}
      </div>
      <div className="w-[10%] px-1 py-1 text-right text-[hsl(var(--terminal-text-primary))]">
        {formatPct(row.deltaPct)}
      </div>
      <div className={cn("w-[13%] px-1 py-1 text-right", premiumClass)}>
        {formatMoney(row.premiumDollars, true)}
      </div>
      <div
        className="w-[12%] px-1 py-1 text-right text-[hsl(var(--terminal-text-primary))]"
        title={row.marginSource === "whatif" ? "IBKR WhatIf" : "Deterministic estimate"}
      >
        {formatMoney(row.margin)}
        {row.marginSource === "deterministic" ? (
          <span className="ml-0.5 text-[8px] text-[hsl(var(--terminal-text-tertiary))]">est</span>
        ) : null}
      </div>
      <div className="w-[12%] px-1 py-1 text-right tabular-nums text-[hsl(var(--terminal-text-primary))]">
        {formatLiquidity(row.liquidity)}
      </div>
      <div className="w-[12%] px-1 py-1 text-right text-[hsl(var(--terminal-text-primary))]">
        {row.creditEfficiency != null
          ? `${row.creditEfficiency.toFixed(1)}%`
          : "—"}
      </div>
      <div className="w-[13%] px-1 py-1 text-right tabular-nums text-[hsl(var(--terminal-text-primary))]">
        {row.score != null ? row.score.toFixed(3) : "—"}
      </div>
    </div>
  );
}

export function OptionOpportunitiesTables({ live, feedStatus }: Props) {
  const calls: DisplayRow[] = useMemo(
    () => (live?.calls ?? []).map(liveToRow),
    [live],
  );
  const puts: DisplayRow[] = useMemo(
    () => (live?.puts ?? []).map(liveToRow),
    [live],
  );

  const isOffline = feedStatus === "disconnected" || feedStatus === "unavailable";
  const emptyMessage = isOffline
    ? "Live data unavailable — check IBKR connection"
    : "Awaiting live opportunity data";

  return (
    <section className="flex flex-col gap-2" aria-label="Options Opportunities">
      <SectionTitle>Options Opportunities</SectionTitle>
      <VirtualizedTable label="CALL side" rows={calls} emptyMessage={emptyMessage} />
      <VirtualizedTable label="PUT side" rows={puts} emptyMessage={emptyMessage} />
    </section>
  );
}
