/**
 * Reverse BWB Intelligence Dashboard — the home page.
 *
 * Loads all twelve ticker cards in a single hop from
 * ``GET /api/v1/dashboard/tickers`` and lays them out in three tier
 * sections. The strict 3-section card layout (header / Reverse BWB credit
 * view / option opportunities tables) is enforced by the new
 * ``components/dashboard/TickerCard`` — each card exposes Re-run Analysis and
 * Open Full Report header actions.
 *
 * The backend owns sequential batch execution; the header "Refresh All"
 * button just kicks ``POST /dashboard/refresh`` and surfaces the live
 * progress from ``WatchlistBatchStatus``.
 */

import { Link } from "react-router-dom";
import { Loader2, Moon, Sun } from "lucide-react";

import { RefreshAllButton } from "@/components/dashboard/RefreshAllButton";
import { TickerCard } from "@/components/dashboard/TickerCard";
import { TierSection } from "@/components/grid/TierSection";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { WATCHLIST_TIERS } from "@/config/watchlist";
import { useHealth } from "@/hooks/useApi";
import { useDashboardCards } from "@/hooks/useDashboardCards";
import { useDashboardBatchSync } from "@/hooks/useDashboardBatchSync";
import { useMarketDataSocket } from "@/hooks/useMarketDataSocket";
import { useRefreshDashboard } from "@/hooks/useRefreshDashboard";
import { useThemeStore } from "@/store/theme";
import type { DashboardTickerCard, WatchlistBatchStatus } from "@/types/schemas";

const EMPTY_STATUS: WatchlistBatchStatus = {
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

function HealthDot() {
  const { data, isLoading } = useHealth();
  if (isLoading) {
    return (
      <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
        <Loader2 className="h-3 w-3 animate-spin" /> Checking
      </span>
    );
  }
  const ok = !!data;
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider ${
        ok ? "text-emerald-700 dark:text-emerald-300" : "text-rose-700 dark:text-rose-300"
      }`}
    >
      <span
        className={`inline-block h-2 w-2 rounded-full ${ok ? "bg-emerald-400" : "bg-rose-400"}`}
      />
      {ok ? `v${data!.version} online` : "Backend offline"}
    </span>
  );
}

export function WatchlistGridPage() {
  const theme = useThemeStore((s) => s.theme);
  const toggleTheme = useThemeStore((s) => s.toggle);

  const dashboard = useDashboardCards();
  const { refreshAll, refreshTicker } = useRefreshDashboard();

  // Live IBKR push socket — patches the bulk cache on every tick and
  // invalidates the opportunity slice on opportunity_version changes.
  // Soft-fails when the backend doesn't run the worker (degrades to the
  // existing 4s `/dashboard/live` poll).
  useMarketDataSocket();

  const status = dashboard.data?.status ?? EMPTY_STATUS;
  useDashboardBatchSync(dashboard.data?.status);
  const cards = dashboard.data?.cards ?? [];
  const cardByTicker: Record<string, DashboardTickerCard> = {};
  for (const card of cards) cardByTicker[card.ticker] = card;

  return (
    <div className="terminal-bg min-h-dvh">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-6 px-6 py-6">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <h1 className="text-2xl font-semibold tracking-tight text-[hsl(var(--terminal-text-primary))]">
              Reverse BWB Intelligence Dashboard
            </h1>
            <p className="text-[12px] uppercase tracking-[0.18em] text-[hsl(var(--terminal-text-tertiary))]">
              Multi-LLM Deliberative Intelligence Platform
            </p>
            <div className="mt-2 flex items-center gap-3 text-[12px] text-[hsl(var(--terminal-text-secondary))]">
              <HealthDot />
              <span className="font-mono">
                {dashboard.isFetching ? "Refreshing cards…" : `${cards.length} tickers tracked`}
              </span>
              {status.last_error ? (
                <span
                  className="truncate font-mono text-rose-700 dark:text-rose-300/80"
                  title={status.last_error}
                >
                  Last error: {status.last_error}
                </span>
              ) : null}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <RefreshAllButton
              status={status}
              onRefresh={() => refreshAll.mutate()}
              isPending={refreshAll.isPending}
            />
            <Button
              asChild
              size="sm"
              variant="outline"
              className="border-[hsl(var(--terminal-border))] text-[hsl(var(--terminal-text-primary))] hover:bg-[hsl(var(--terminal-card-elevated))]"
            >
              <Link to="/workbench">Workbench</Link>
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={toggleTheme}
              className="border-[hsl(var(--terminal-border))] text-[hsl(var(--terminal-text-primary))] hover:bg-[hsl(var(--terminal-card-elevated))]"
              aria-label="Toggle theme"
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
          </div>
        </header>

        {dashboard.isError && (
          <div className="rounded-md border border-rose-500/40 bg-rose-50 px-4 py-3 text-sm text-rose-800 dark:bg-rose-500/10 dark:text-rose-200">
            Failed to load dashboard data. The backend may be offline — refresh
            once it's back online.
          </div>
        )}

        {dashboard.isLoading ? (
          <div className="flex flex-col gap-6">
            {WATCHLIST_TIERS.map((tier) => (
              <div key={tier.key} className="flex flex-col gap-3">
                <Skeleton className="h-5 w-40" />
                <div
                  className="grid gap-3"
                  style={{ gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))" }}
                >
                  {tier.tickers.map((t) => (
                    <Skeleton key={t.symbol} className="h-[650px] w-full rounded-xl" />
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex flex-col gap-6">
            {WATCHLIST_TIERS.map((tier) => (
              <TierSection key={tier.key} name={tier.name} description={tier.description}>
                {tier.tickers.map((t) => {
                  const card =
                    cardByTicker[t.symbol] ??
                    ({
                      ticker: t.symbol,
                      company_name: t.company,
                      tier_key: tier.key,
                      status: "pending",
                      generated_at: null,
                      price_snapshot: null,
                      reverse_bwb: null,
                      opportunities: null,
                      report_id: null,
                      error_message: null,
                    } as DashboardTickerCard);
                  return (
                    <TickerCard
                      key={t.symbol}
                      card={card}
                      batchStatus={status}
                      onRerun={(ticker) => refreshTicker.mutate(ticker)}
                    />
                  );
                })}
              </TierSection>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
