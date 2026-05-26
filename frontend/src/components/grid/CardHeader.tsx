import type { ReactNode } from "react";

import { Chip } from "@/components/grid/primitives";
import type { FeedStatus } from "@/types/schemas";

type Props = {
  ticker: string;
  company: string;
  price: number | null;
  dailyChangePct: number | null;
  action?: ReactNode;
  /**
   * Live IBKR feed status for the price column. When set, the header
   * renders a small badge next to the price ("LIVE" / "STALE" / "—") and
   * shows the "Live data unavailable" caption when disconnected.
   */
  liveStatus?: FeedStatus;
};

function formatPrice(price: number | null): string {
  if (price == null || Number.isNaN(price)) return "—";
  return `$${price.toFixed(2)}`;
}

function formatChange(pct: number | null): { text: string; tone: "ok" | "bad" | "neutral" } {
  if (pct == null || Number.isNaN(pct)) return { text: "—", tone: "neutral" };
  const sign = pct >= 0 ? "+" : "";
  return {
    text: `${sign}${pct.toFixed(2)}%`,
    tone: pct >= 0 ? "ok" : "bad",
  };
}

function liveBadge(status: FeedStatus | undefined): { label: string; tone: "ok" | "warn" | "bad" } | null {
  if (!status) return null;
  if (status === "live") return { label: "LIVE", tone: "ok" };
  if (status === "stale") return { label: "STALE", tone: "warn" };
  // disconnected / unavailable both render the same banner; the "Live
  // data unavailable" caption below carries the user-facing copy.
  return null;
}

export function CardHeader({
  ticker,
  company,
  price,
  dailyChangePct,
  action,
  liveStatus,
}: Props) {
  const change = formatChange(dailyChangePct);
  const badge = liveBadge(liveStatus);
  const isOffline = liveStatus === "disconnected" || liveStatus === "unavailable";
  return (
    <header className="flex items-start justify-between gap-3">
      <div className="flex flex-col gap-1 overflow-hidden">
        <div className="grid-card-ticker font-mono">{ticker.toUpperCase()}</div>
        <div className="grid-card-company truncate" title={company}>
          {company}
        </div>
        <div className="flex items-center gap-2">
          <div className="grid-card-price font-mono">{formatPrice(price)}</div>
          {badge ? (
            <Chip tone={badge.tone} className="text-[9px]">
              {badge.label}
            </Chip>
          ) : null}
        </div>
        {isOffline ? (
          <div className="text-[10px] font-medium uppercase tracking-wider text-[hsl(var(--terminal-text-tertiary))]">
            Live data unavailable
          </div>
        ) : null}
      </div>
      <div className="flex shrink-0 flex-col items-end gap-2">
        {dailyChangePct != null && !Number.isNaN(dailyChangePct) ? (
          <Chip tone={change.tone}>{change.text}</Chip>
        ) : null}
        {action}
      </div>
    </header>
  );
}
