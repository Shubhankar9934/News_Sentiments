/**
 * TickerCard live-overlay tests.
 *
 * Verifies the strict separation contract from the IBKR plan:
 *   - When live data is present, the header price renders the live tick,
 *     not the snapshot price.
 *   - The Reverse BWB credit view (Decision / Credit safety / summary)
 *     is sourced from `card.reverse_bwb` and never shifts when only
 *     the live price changes.
 *   - When the live feed is disconnected, the "Live data unavailable"
 *     caption appears and the LIVE badge is hidden.
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import type { ReactNode } from "react";

import { TickerCard } from "@/components/dashboard/TickerCard";
import { DASHBOARD_LIVE_QUERY_KEY } from "@/hooks/useLiveMarketData";
import type {
  DashboardLiveBundle,
  DashboardTickerCard,
  WatchlistBatchStatus,
} from "@/types/schemas";

function makeBatchStatus(): WatchlistBatchStatus {
  return {
    state: "idle",
    current_ticker: null,
    queued: [],
    completed: [],
    failed: [],
    total: 12,
    started_at: null,
    finished_at: null,
    last_error: null,
  };
}

function makeCard(overrides: Partial<DashboardTickerCard> = {}): DashboardTickerCard {
  return {
    ticker: "SPY",
    company_name: "SPDR S&P 500 ETF Trust",
    tier_key: "tier-1",
    status: "completed",
    generated_at: "2026-05-25T08:00:00Z",
    price_snapshot: { price: 740.0, daily_change_pct: -0.1, as_of: null, source: "polygon" },
    reverse_bwb: {
      ticker: "SPY",
      decision: "Avoid",
      credit_safety_score: 4.1,
      risk: "High",
      confidence: "Medium",
      today_outlook: "Choppy",
      next_3d_outlook: "Volatile",
      chance_up_2_3_pct: "Medium",
      chance_down_2_3_pct: "High",
      expected_range_today: { low: 738, high: 752 },
      expected_range_next_3d: { low: 730, high: 760 },
      danger_zone: "+/- 1% around 745",
      pin_risk: "Medium",
      event_risk: "High",
      iv_quality: "Average",
      liquidity: "Good",
      actual_dynamics_summary: [
        "Tight range expected today.",
        "Risk skews to downside on FOMC tail.",
        "Premium thin given vol regime.",
      ],
    },
    opportunities: null,
    report_id: "abc-123",
    error_message: null,
    ...overrides,
  };
}

function renderCard(
  card: DashboardTickerCard,
  liveBundle: DashboardLiveBundle | null,
) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
  if (liveBundle) {
    qc.setQueryData(DASHBOARD_LIVE_QUERY_KEY, liveBundle);
  }
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter>
        <QueryClientProvider client={qc}>{children}</QueryClientProvider>
      </MemoryRouter>
    );
  }
  return render(
    <Wrapper>
      <TickerCard card={card} batchStatus={makeBatchStatus()} onRerun={() => {}} />
    </Wrapper>,
  );
}

const liveBundleConnected: DashboardLiveBundle = {
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
      opportunities: null,
    },
  },
};

const liveBundleDisconnected: DashboardLiveBundle = {
  feed_status: "disconnected",
  prices_updated_at: null,
  opportunities_updated_at: null,
  tickers: {},
};

describe("TickerCard live overlay", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows live price and LIVE badge when feed is connected", () => {
    renderCard(makeCard(), liveBundleConnected);
    expect(screen.getByText("$745.64")).toBeInTheDocument();
    expect(screen.getByText("LIVE")).toBeInTheDocument();
    // Live data unavailable caption must not be present when connected.
    expect(screen.queryByText("Live data unavailable")).not.toBeInTheDocument();
  });

  it("shows snapshot price as fallback and disconnected caption when feed is offline", () => {
    renderCard(makeCard(), liveBundleDisconnected);
    expect(screen.getByText("$740.00")).toBeInTheDocument();
    expect(screen.queryByText("LIVE")).not.toBeInTheDocument();
    // The "Live data unavailable" copy renders both in the header and in
    // each empty options table, so we should see at least one (header)
    // and at most three (header + 2 tables).
    const offlineLabels = screen.getAllByText("Live data unavailable");
    expect(offlineLabels.length).toBeGreaterThanOrEqual(1);
    expect(offlineLabels.length).toBeLessThanOrEqual(3);
  });

  it("preserves the frozen Reverse BWB analysis fields regardless of live state", () => {
    // Connected state — Decision/CreditSafety/Summary come from snapshot.
    const { unmount } = renderCard(makeCard(), liveBundleConnected);
    const reverseBwbConnected = screen.getByLabelText("Reverse BWB Credit View");
    expect(within(reverseBwbConnected).getByText("Avoid")).toBeInTheDocument();
    expect(within(reverseBwbConnected).getByText("4.1 / 10")).toBeInTheDocument();
    expect(
      within(reverseBwbConnected).getByText("Tight range expected today."),
    ).toBeInTheDocument();
    unmount();

    // Disconnected state — same snapshot fields render identically.
    renderCard(makeCard(), liveBundleDisconnected);
    const reverseBwbDisconnected = screen.getByLabelText("Reverse BWB Credit View");
    expect(within(reverseBwbDisconnected).getByText("Avoid")).toBeInTheDocument();
    expect(within(reverseBwbDisconnected).getByText("4.1 / 10")).toBeInTheDocument();
    expect(
      within(reverseBwbDisconnected).getByText("Tight range expected today."),
    ).toBeInTheDocument();
  });
});
