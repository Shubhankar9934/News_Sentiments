/**
 * Placeholder options-opportunities fixture for the watchlist grid card.
 *
 * Returns the same hard-coded `OptionsData` for every ticker today. Wired
 * through `TickerCard` so the new OPTIONS OPPORTUNITIES section renders
 * with realistic-looking values until the IBKR Gateway feed is available.
 *
 * The `ticker` argument is intentionally accepted (and unused) so the
 * call site stays stable when we later swap this for a real per-ticker
 * source — either a hook (`useOptionsOpportunities(ticker)`) or a field
 * on `TickerSummaryRow`.
 */

import type { OptionsData } from "@/components/grid/OptionsOpportunities";

const MOCK_OPTIONS_DATA: OptionsData = {
  calls: [
    {
      combo: "225/227.5/232.5",
      exp: "2D",
      premium: "$90",
      margin: "$3000",
      liquidity: "High",
    },
    {
      combo: "227.5/230/235",
      exp: "3D",
      premium: "$45",
      margin: "$2750",
      liquidity: "High",
    },
  ],
  puts: [
    {
      combo: "210/205/200",
      exp: "2D",
      premium: "$85",
      margin: "$2600",
      liquidity: "High",
    },
    {
      combo: "215/210/205",
      exp: "3D",
      premium: "$55",
      margin: "$2400",
      liquidity: "High",
    },
  ],
};

export function getMockOptionsData(_ticker: string): OptionsData {
  return MOCK_OPTIONS_DATA;
}
