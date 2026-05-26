/**
 * Detects watchlist batch completion edges and forces dashboard + history
 * refetches so cards update immediately when the worker finishes a ticker
 * (without waiting for the 30s idle poll window).
 */

import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { DASHBOARD_CARDS_QUERY_KEY, LATEST_REPORT_QUERY_KEY, dashboardTickerReportQueryKey } from "@/hooks/useDashboardCards";
import type { WatchlistBatchStatus } from "@/types/schemas";

type Snapshot = {
  state: WatchlistBatchStatus["state"];
  completed: string[];
};

function snapshotOf(status: WatchlistBatchStatus): Snapshot {
  return { state: status.state, completed: [...status.completed] };
}

function invalidateHistoryForTickers(
  qc: ReturnType<typeof useQueryClient>,
  tickers: string[],
) {
  for (const ticker of tickers) {
    const upper = ticker.toUpperCase();
    qc.invalidateQueries({ queryKey: [LATEST_REPORT_QUERY_KEY, upper] });
    qc.invalidateQueries({ queryKey: dashboardTickerReportQueryKey(upper) });
  }
}

export function useDashboardBatchSync(status: WatchlistBatchStatus | undefined) {
  const qc = useQueryClient();
  const prevRef = useRef<Snapshot | null>(null);

  useEffect(() => {
    if (!status) return;

    const prev = prevRef.current;
    if (prev) {
      const newCompletions = status.completed.filter((t) => !prev.completed.includes(t));
      if (newCompletions.length > 0) {
        void qc.refetchQueries({ queryKey: DASHBOARD_CARDS_QUERY_KEY });
        invalidateHistoryForTickers(qc, newCompletions);
      }

      if (prev.state === "running" && status.state !== "running") {
        void qc.refetchQueries({ queryKey: DASHBOARD_CARDS_QUERY_KEY });
        invalidateHistoryForTickers(qc, status.completed);
      }
    }

    prevRef.current = snapshotOf(status);
  }, [status, qc]);
}
