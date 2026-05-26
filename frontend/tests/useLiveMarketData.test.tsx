/**
 * useLiveMarketData hook tests.
 *
 * Verifies:
 *   - The hook polls /dashboard/live and exposes the bulk bundle.
 *   - The per-ticker selectors return slices keyed by uppercased ticker.
 *   - A failed fetch resolves to a graceful empty bundle (feed_status='unavailable').
 */

import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

import { apiClient } from "@/api/client";
import {
  useLiveFeedStatus,
  useLiveMarketData,
  useTickerLiveOpportunities,
  useTickerLiveQuote,
} from "@/hooks/useLiveMarketData";

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
    },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

const SAMPLE_RESPONSE = {
  feed_status: "live",
  prices_updated_at: "2026-05-25T08:30:00Z",
  opportunities_updated_at: "2026-05-25T08:29:30Z",
  tickers: {
    SPY: {
      ticker: "SPY",
      quote: {
        ticker: "SPY",
        last_price: 745.64,
        bid: 745.6,
        ask: 745.66,
        change_abs: 1.5,
        change_pct: 0.2,
        volume: 12345678,
        prev_close: 744.14,
        feed_status: "live",
        updated_at: "2026-05-25T08:30:00Z",
      },
      opportunities: {
        calls: [
          {
            ticker: "SPY",
            side: "call",
            rank: 0,
            combo: "750/755/765",
            expiration: "20260530",
            expiry_days: 7,
            delta_pct: 1.42,
            premium: -0.6,
            init_margin: 510,
            maint_margin: 510,
            init_margin_source: "deterministic",
            liquidity: 1500,
            minimum_open_interest: 1500,
            minimum_volume: 200,
            credit_efficiency: 11.4,
            ranking_score: 0.78,
            underlying_price: 745.64,
            opportunity_version: "00000000-0000-0000-0000-000000000001",
            updated_at: "2026-05-25T08:29:30Z",
          },
        ],
        puts: [],
        call_version: "00000000-0000-0000-0000-000000000001",
        put_version: null,
        updated_at: "2026-05-25T08:29:30Z",
        feed_status: "live",
      },
    },
  },
};

beforeEach(() => {
  vi.spyOn(apiClient, "get").mockResolvedValue({ data: SAMPLE_RESPONSE });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useLiveMarketData", () => {
  it("returns the parsed bulk bundle", async () => {
    const { result } = renderHook(() => useLiveMarketData(), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => {
      expect(result.current.data?.feed_status).toBe("live");
    });
    expect(result.current.data?.tickers.SPY?.quote?.last_price).toBe(745.64);
  });

  it("exposes per-ticker quote selectors keyed by uppercase ticker", async () => {
    function Combined() {
      useLiveMarketData(); // primes the cache
      const quote = useTickerLiveQuote("spy");
      const opps = useTickerLiveOpportunities("spy");
      const status = useLiveFeedStatus();
      return { quote, opps, status };
    }
    const { result } = renderHook(() => Combined(), { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(result.current.quote?.last_price).toBe(745.64);
    });
    expect(result.current.status).toBe("live");
    expect(result.current.opps?.calls).toHaveLength(1);
    expect(result.current.opps?.calls[0].combo).toBe("750/755/765");
  });

  it("falls back to an empty bundle when the API errors", async () => {
    vi.spyOn(apiClient, "get").mockRejectedValueOnce(new Error("network down"));
    const { result } = renderHook(() => useLiveMarketData(), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => {
      expect(result.current.data?.feed_status).toBe("unavailable");
    });
    expect(result.current.data?.tickers).toEqual({});
  });
});
