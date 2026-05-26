/**
 * Live IBKR market-data hooks.
 *
 *   GET /api/v1/dashboard/live      — bulk endpoint, polled every 4s.
 *   GET /api/v1/tickers/:t/...      — per-ticker single-shot endpoints.
 *
 * The bulk hook (`useLiveMarketData`) is the primary one used by the
 * 12-card grid: a single network round-trip every ~4s carries every
 * ticker's quote and options-opportunities. Per-ticker selectors fan
 * out cheaply.
 *
 * Strict separation rule: these hooks never invalidate
 * `["dashboard", "tickers"]` (the snapshot query). They run on their
 * own poll cadence so a price tick never re-renders the frozen
 * Reverse-BWB summary section of any card.
 */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { apiClient } from "@/api/client";
import {
  dashboardLiveBundleSchema,
  type DashboardLiveBundle,
  type DashboardLiveTickerEntry,
  type LiveOpportunityBundle,
  type LiveQuote,
} from "@/types/schemas";

const LIVE_REFETCH_MS = 4_000;
const LIVE_STALE_MS = 2_000;

export const DASHBOARD_LIVE_QUERY_KEY = ["dashboard", "live"] as const;

function emptyBundle(): DashboardLiveBundle {
  return {
    feed_status: "unavailable",
    prices_updated_at: null,
    opportunities_updated_at: null,
    tickers: {},
  };
}

function parseDashboardLiveResponse(data: unknown): DashboardLiveBundle {
  const parsed = dashboardLiveBundleSchema.safeParse(data);
  if (parsed.success) return parsed.data;
  // Defensive: never let a malformed response break the dashboard. The
  // worst case is the user sees "Live data unavailable" until the next
  // poll lands a valid payload.
  return emptyBundle();
}

/**
 * Bulk live data for every watchlist ticker. Polled every ~4s.
 */
export function useLiveMarketData(): UseQueryResult<DashboardLiveBundle> {
  return useQuery({
    queryKey: DASHBOARD_LIVE_QUERY_KEY,
    queryFn: async (): Promise<DashboardLiveBundle> => {
      try {
        const { data } = await apiClient.get("/dashboard/live");
        return parseDashboardLiveResponse(data);
      } catch (err) {
        // Live polling must never bubble toasts on each failed poll;
        // the API client interceptor already gates network-error
        // toasts to non-cancelled requests, but we still want to
        // gracefully surface "disconnected" to the UI.
        return emptyBundle();
      }
    },
    refetchInterval: LIVE_REFETCH_MS,
    refetchOnWindowFocus: false,
    staleTime: LIVE_STALE_MS,
    retry: false,
  });
}

/**
 * Pluck one ticker's slice from the bulk live query.
 *
 * This intentionally does NOT issue a separate request — it reads the
 * cached payload from `useLiveMarketData()` so all 12 cards share a
 * single network call.
 */
export function useTickerLiveQuote(ticker: string): LiveQuote | null {
  const { data } = useLiveMarketData();
  if (!data) return null;
  const entry: DashboardLiveTickerEntry | undefined =
    data.tickers[ticker.toUpperCase()];
  if (!entry || !entry.quote) return null;
  return entry.quote;
}

export function useTickerLiveOpportunities(
  ticker: string,
): LiveOpportunityBundle | null {
  const { data } = useLiveMarketData();
  if (!data) return null;
  const entry: DashboardLiveTickerEntry | undefined =
    data.tickers[ticker.toUpperCase()];
  if (!entry || !entry.opportunities) return null;
  return entry.opportunities;
}

export function useLiveFeedStatus() {
  const { data } = useLiveMarketData();
  return data?.feed_status ?? "unavailable";
}
