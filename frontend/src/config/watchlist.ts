/**
 * Static watchlist for the executive grid dashboard.
 *
 * Three tiers, four tickers each, total 12 — the spec calls for a trader to
 * scan all 12 in under 30 seconds. The list is static on purpose: it ships
 * as a compile-time config, no admin UI required for v1. Re-tier or expand
 * by editing this file directly.
 */

export type WatchlistTicker = {
  symbol: string;
  company: string;
};

export type WatchlistTier = {
  key: string;
  name: string;
  description?: string;
  tickers: WatchlistTicker[];
};

export const WATCHLIST_TIERS: WatchlistTier[] = [
  {
    key: "tier-1",
    name: "Tier 1",
    description: "Index ETFs",
    tickers: [
      { symbol: "SPY", company: "SPDR S&P 500 ETF Trust" },
      { symbol: "QQQ", company: "Invesco QQQ Trust" },
      { symbol: "IWM", company: "iShares Russell 2000 ETF" },
      { symbol: "DIA", company: "SPDR Dow Jones Industrial Average ETF" },
    ],
  },
  {
    key: "tier-2",
    name: "Tier 2",
    description: "Mega-cap tech",
    tickers: [
      { symbol: "AAPL", company: "Apple Inc." },
      { symbol: "MSFT", company: "Microsoft Corporation" },
      { symbol: "AMZN", company: "Amazon.com, Inc." },
      { symbol: "GOOGL", company: "Alphabet Inc." },
    ],
  },
  {
    key: "tier-3",
    name: "Tier 3",
    description: "High-beta growth",
    tickers: [
      { symbol: "NVDA", company: "NVIDIA Corporation" },
      { symbol: "TSLA", company: "Tesla, Inc." },
      { symbol: "AMD", company: "Advanced Micro Devices, Inc." },
      { symbol: "META", company: "Meta Platforms, Inc." },
    ],
  },
];

export const ALL_WATCHLIST_TICKERS: string[] = WATCHLIST_TIERS.flatMap((t) =>
  t.tickers.map((s) => s.symbol),
);

export const WATCHLIST_COMPANY_BY_SYMBOL: Record<string, string> = Object.fromEntries(
  WATCHLIST_TIERS.flatMap((t) => t.tickers.map((s) => [s.symbol, s.company])),
);
