/**
 * Single hop that loads the slim per-ticker projection driving the grid.
 *
 *   GET /api/v1/summaries?tickers=SPY,QQQ,...
 *
 * Refetches every 30s so cards stay fresh when the user leaves the tab open;
 * any per-card mutation invalidates this query so a fresh run lands instantly.
 */

import { useCallback } from "react";
import { useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import { tickerSummariesResponseSchema, type TickerSummaryRow } from "@/types/schemas";

const REFETCH_MS = 30_000;
const STALE_MS = 15_000;

export const SUMMARIES_QUERY_KEY = (tickers: readonly string[]) => [
  "summaries",
  tickers.join(","),
] as const;

export function useTickerSummaries(
  tickers: readonly string[],
): UseQueryResult<TickerSummaryRow[]> {
  const enabled = tickers.length > 0;
  return useQuery({
    queryKey: SUMMARIES_QUERY_KEY(tickers),
    queryFn: async (): Promise<TickerSummaryRow[]> => {
      const { data } = await apiClient.get("/summaries", {
        params: { tickers: tickers.join(",") },
      });
      return tickerSummariesResponseSchema.parse(data);
    },
    enabled,
    refetchInterval: REFETCH_MS,
    refetchOnWindowFocus: false, // 12-card dashboard refocus would burst the projection endpoint.
    staleTime: STALE_MS,
    // 429 from a transiently saturated rate-limit window: exponential back-off
    // up to 30s. Mirrors `useDeliberation`'s retry stance.
    retry: (failureCount, error) => {
      const status = (error as { response?: { status?: number } }).response?.status;
      return status === 429 && failureCount < 4;
    },
    retryDelay: (attempt) => Math.min(2_000 * 2 ** attempt, 30_000),
  });
}

/**
 * Imperatively invalidate the summaries cache (used after a Run Analysis
 * completes so the just-updated card refreshes from the projection).
 *
 * The returned function is referentially stable across renders so callers
 * may safely include it in `useEffect` dependency arrays without causing
 * a fetch storm.
 */
export function useInvalidateSummaries() {
  const qc = useQueryClient();
  return useCallback(
    (tickers: readonly string[]) => {
      qc.invalidateQueries({ queryKey: SUMMARIES_QUERY_KEY(tickers) });
    },
    [qc],
  );
}
