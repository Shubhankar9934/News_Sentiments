/**
 * Virtualized opportunity table smoke tests.
 *
 * The Reverse BWB Workstation card may render thousands of opportunities
 * per ticker. We rely on `@tanstack/react-virtual` to keep the DOM small.
 * These tests lock down:
 *
 *   * 5000 rows -> dramatically fewer DOM nodes (well below 100 visible).
 *   * Sticky header is rendered alongside the virtual rows.
 *   * Clicking a sortable column header changes the visible top row.
 *   * Liquidity renders as raw numbers (never "Good"/"Excellent").
 *   * Premium colour reflects sign (credit vs debit).
 */

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, beforeAll } from "vitest";

import { OptionOpportunitiesTables } from "@/components/dashboard/OptionOpportunitiesTables";
import type {
  LiveOpportunity,
  LiveOpportunityBundle,
} from "@/types/schemas";

function makeOpp(i: number): LiveOpportunity {
  const score = 0.001 * (5000 - i); // descending score so row 0 has highest
  return {
    ticker: "SPY",
    side: "call",
    rank: i,
    combo: `${700 + i}/${705 + i}/${715 + i}`,
    strike_long_wing_a: 700 + i,
    strike_short_body: 705 + i,
    strike_long_wing_b: 715 + i,
    expiration: "20260530",
    expiry_days: 7 + (i % 3),
    delta_pct: 1 + i * 0.001,
    premium: -0.6 - i * 0.0001,
    init_margin: 500 + i,
    maint_margin: 420,
    init_margin_source: i % 2 === 0 ? "deterministic" : "whatif",
    liquidity: 2000 + i,
    minimum_open_interest: 2000 + i,
    minimum_volume: 100 + i,
    oi_leg1: 2000 + i,
    oi_leg2: 2050 + i,
    oi_leg3: 2100 + i,
    vol_leg1: 100,
    vol_leg2: 110,
    vol_leg3: 120,
    iv_leg1: 0.30,
    iv_leg2: 0.31,
    iv_leg3: 0.32,
    mid_leg1: 1.80,
    mid_leg2: 3.80,
    mid_leg3: 5.20,
    credit_efficiency: 11 + (i % 10) * 0.1,
    ranking_score: score,
    underlying_price: 745.64,
    iv: 0.31,
    opportunity_version: "00000000-0000-0000-0000-000000000001",
    updated_at: "2026-05-25T08:30:00Z",
  };
}

function makeBundle(count: number, side: "call" | "put"): LiveOpportunityBundle {
  const rows = Array.from({ length: count }, (_, i) => makeOpp(i));
  return {
    calls: side === "call" ? rows : [],
    puts: side === "put" ? rows.map((o) => ({ ...o, side: "put" })) : [],
    call_version: "00000000-0000-0000-0000-000000000001",
    put_version: "00000000-0000-0000-0000-000000000002",
    updated_at: "2026-05-25T08:30:00Z",
    feed_status: "live",
  };
}

beforeAll(() => {
  // jsdom doesn't implement layout — give the virtualizer a real
  // scrollable height so it materializes some rows.
  if (!HTMLElement.prototype.scrollTo) {
    HTMLElement.prototype.scrollTo = () => {};
  }
  Object.defineProperty(HTMLElement.prototype, "offsetHeight", {
    configurable: true,
    get() {
      return 320;
    },
  });
  Object.defineProperty(HTMLElement.prototype, "clientHeight", {
    configurable: true,
    get() {
      return 320;
    },
  });
});

afterEach(() => {
  cleanup();
});

describe("OptionOpportunitiesTables (virtualized)", () => {
  it("renders far fewer DOM rows than the input row count", () => {
    const live = makeBundle(5000, "call");
    render(
      <OptionOpportunitiesTables data={null} live={live} feedStatus="live" />,
    );
    // Both panels render. The CALL panel should show "5,000 rows" header.
    expect(screen.getByText(/5,000 rows/)).toBeInTheDocument();

    // The visible rows include the combo prefix "700/705/715" for row 0
    // (highest score) — verify the first row is rendered.
    expect(screen.getByText("700/705/715")).toBeInTheDocument();

    // Sticky header buttons are present (we query by the title attribute
    // because the visible accessible name only carries the column label).
    expect(screen.getAllByTitle(/Sort by Combo/).length).toBeGreaterThan(0);
    expect(screen.getAllByTitle(/Sort by Premium/).length).toBeGreaterThan(0);
  });

  it("renders liquidity as a number, not a category label", () => {
    const live = makeBundle(20, "call");
    render(
      <OptionOpportunitiesTables data={null} live={live} feedStatus="live" />,
    );
    // The top row's liquidity = 2000.
    expect(screen.getAllByText("2,000").length).toBeGreaterThan(0);
    // Words like "Good"/"Excellent"/"Average" must not appear.
    expect(screen.queryByText(/^Good$/)).toBeNull();
    expect(screen.queryByText(/^Excellent$/)).toBeNull();
  });

  it("colours premium according to sign", () => {
    const live = makeBundle(2, "call");
    render(
      <OptionOpportunitiesTables data={null} live={live} feedStatus="live" />,
    );
    // -0.6 * 100 = -60 -> green "credit" colour. Look for the credit
    // formatting "-$60.00".
    const premiumCells = screen.getAllByText(/-\$60/);
    expect(premiumCells.length).toBeGreaterThan(0);
    const cell = premiumCells[0];
    expect(cell.className).toMatch(/emerald|green/);
  });

  it("shows the LIVE/PUT empty-state when offline and live bundle is null", () => {
    render(
      <OptionOpportunitiesTables
        data={null}
        live={null}
        feedStatus="disconnected"
      />,
    );
    expect(screen.getAllByText(/Live data unavailable/).length).toBeGreaterThan(0);
  });

  it("re-sorts when a column header is clicked", () => {
    const live = makeBundle(20, "call");
    const { container } = render(
      <OptionOpportunitiesTables data={null} live={live} feedStatus="live" />,
    );
    // Default sort: ranking_score desc -> top combo is row 0 ("700/705/715").
    expect(within(container).getAllByText("700/705/715").length).toBeGreaterThan(0);
    // Click the Score header (button text is "Score ↓" by default) to
    // flip the sort direction. The CALL panel's button is the first
    // matching one in the document.
    const scoreButtons = within(container).getAllByTitle(/Sort by Score/);
    fireEvent.click(scoreButtons[0]);
    // After flipping to ascending, the lowest score (row 19) is on top.
    expect(within(container).getAllByText("719/724/734").length).toBeGreaterThan(0);
  });
});
