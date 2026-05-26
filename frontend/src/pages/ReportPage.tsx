/**
 * Layer-2 Full Report — `/report/:ticker`.
 *
 * Reuses the existing TradingIntelligenceDashboard + DeliberationDashboard
 * verbatim. Watchlist tickers load the canonical dashboard snapshot
 * (`GET /dashboard/tickers/{ticker}/report`); others fall back to
 * `/history/{ticker}?limit=1`.
 *
 * IMPORTANT: nothing about the legacy single-ticker workbench is changed.
 * That experience still exists at `/workbench`. This page is purely
 * additive — it composes the same children with a URL-driven ticker.
 */

import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2, Moon, Sun } from "lucide-react";
import { toast } from "sonner";
import { DeliberationDashboard } from "@/components/deliberation/DeliberationDashboard";
import { ExplainabilitySection } from "@/components/explainability/ExplainabilitySection";
import { OpportunityExplorer } from "@/components/dashboard/OpportunityExplorer";
import {
  TradingIntelligenceDashboard,
  type AnalogRow,
} from "@/components/trading/TradingIntelligenceDashboard";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiClient } from "@/api/client";
import { ALL_WATCHLIST_TICKERS, WATCHLIST_COMPANY_BY_SYMBOL } from "@/config/watchlist";
import {
  DASHBOARD_CARDS_QUERY_KEY,
  dashboardTickerReportQueryKey,
  isTickerInActiveBatch,
  LATEST_REPORT_QUERY_KEY,
  useDashboardCards,
  useDashboardTickerReport,
} from "@/hooks/useDashboardCards";
import { useDashboardBatchSync } from "@/hooks/useDashboardBatchSync";
import { useRefreshDashboard } from "@/hooks/useRefreshDashboard";
import { useAnalogs, useResearch } from "@/hooks/useApi";
import { pickDominantEventType } from "@/lib/pipelineMeta";
import { useThemeStore } from "@/store/theme";
import { parseResearchReportLoose, type ResearchReport } from "@/types/schemas";

type HistoryRow = {
  id: string;
  time_window: string | null;
  data_mode: string | null;
  articles_ct: number | null;
  created_at: string;
  report_json: unknown;
};

function useLatestPersistedReport(ticker: string, refetchWhileBatchActive: boolean) {
  return useQuery({
    queryKey: [LATEST_REPORT_QUERY_KEY, ticker],
    queryFn: async (): Promise<ResearchReport | null> => {
      const { data } = await apiClient.get(`/history/${encodeURIComponent(ticker)}`, {
        params: { limit: 1 },
      });
      const rows = data as HistoryRow[];
      const first = rows[0]?.report_json;
      if (!first) return null;
      return parseResearchReportLoose(first).report;
    },
    enabled: ticker.length > 0,
    staleTime: 30_000,
    refetchInterval: refetchWhileBatchActive ? 3_000 : false,
  });
}

export function ReportPage() {
  const params = useParams<{ ticker: string }>();
  const tickerParam = (params.ticker ?? "").toUpperCase();
  const qc = useQueryClient();
  const theme = useThemeStore((s) => s.theme);
  const toggleTheme = useThemeStore((s) => s.toggle);

  const isWatchlistTicker = ALL_WATCHLIST_TICKERS.includes(tickerParam);

  const dashboard = useDashboardCards();
  const batchStatus = dashboard.data?.status;
  const tickerBatchActive = isTickerInActiveBatch(tickerParam, batchStatus);

  useDashboardBatchSync(batchStatus);

  const dashboardReport = useDashboardTickerReport(tickerParam, {
    enabled: isWatchlistTicker,
    refetchWhileBatchActive: tickerBatchActive,
  });
  const latest = useLatestPersistedReport(tickerParam, tickerBatchActive);
  const research = useResearch(tickerParam, 7);
  const { refreshTicker } = useRefreshDashboard();

  const report =
    dashboardReport.data ?? latest.data ?? research.data ?? null;

  const dominantEvent = useMemo(
    () => (report ? pickDominantEventType(report) : null),
    [report],
  );
  const analogQuery = useAnalogs(tickerParam, dominantEvent ?? "Earnings", Boolean(report));

  const isRefreshing =
    refreshTicker.isPending ||
    (isWatchlistTicker && tickerBatchActive) ||
    research.isPending;

  const handleRunFresh = async () => {
    try {
      if (isWatchlistTicker) {
        await refreshTicker.mutateAsync(tickerParam);
        await qc.invalidateQueries({
          queryKey: dashboardTickerReportQueryKey(tickerParam),
        });
        await qc.invalidateQueries({ queryKey: [LATEST_REPORT_QUERY_KEY, tickerParam] });
        await qc.invalidateQueries({ queryKey: DASHBOARD_CARDS_QUERY_KEY });
        toast.success(`${tickerParam} analysis queued`);
      } else {
        await research.mutateAsync();
        await qc.invalidateQueries({ queryKey: [LATEST_REPORT_QUERY_KEY, tickerParam] });
        toast.success(`${tickerParam} analysis complete`);
      }
    } catch {
      toast.error(`${tickerParam} analysis failed`);
    }
  };

  const company = WATCHLIST_COMPANY_BY_SYMBOL[tickerParam] ?? "";
  const isLoading =
    (isWatchlistTicker ? dashboardReport.isLoading : false) ||
    latest.isLoading ||
    (research.isPending && !report);
  const fetchFailed =
    (isWatchlistTicker && dashboardReport.isError && !latest.data && !report) ||
    (latest.isError && !dashboardReport.data && !report);
  const showEmpty =
    !report &&
    !isLoading &&
    !isRefreshing &&
    ((isWatchlistTicker && dashboardReport.isFetched && latest.isFetched) ||
      (!isWatchlistTicker && latest.isFetched)) &&
    !fetchFailed;

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4 p-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <Button
            asChild
            variant="outline"
            size="sm"
            className="w-fit"
          >
            <Link to="/" aria-label="Back to dashboard">
              <ArrowLeft className="h-4 w-4" /> Dashboard
            </Link>
          </Button>
          <h1 className="text-xl font-semibold">
            {tickerParam}{" "}
            {company && (
              <span className="ml-2 text-sm font-normal text-slate-500 dark:text-slate-400">
                {company}
              </span>
            )}
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-300">
            Full multi-LLM Deliberative Intelligence report for {tickerParam}.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={handleRunFresh} size="sm" disabled={isRefreshing || !tickerParam}>
            {isRefreshing ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" /> Running…
              </>
            ) : report ? (
              "Re-run analysis"
            ) : (
              "Run analysis"
            )}
          </Button>
          <Button variant="outline" size="sm" onClick={toggleTheme} aria-label="Toggle theme">
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
        </div>
      </header>

      {isLoading && (
        <Card className="flex flex-col gap-3">
          <div className="flex items-center gap-2 text-sm">
            <Loader2 className="h-4 w-4 animate-spin" />
            {isRefreshing
              ? `Running analysis for ${tickerParam}…`
              : "Loading latest persisted report…"}
          </div>
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </Card>
      )}

      {fetchFailed && (
        <Card>
          <p className="text-sm">
            Could not load the persisted report for {tickerParam}.{" "}
            <button
              type="button"
              className="font-medium text-indigo-600 underline underline-offset-2 dark:text-indigo-400"
              onClick={handleRunFresh}
            >
              Retry analysis
            </button>
          </p>
        </Card>
      )}

      {showEmpty && (
        <Card>
          <p className="text-sm">
            No persisted report exists for {tickerParam}. Click{" "}
            <strong>Run analysis</strong> to generate one.
          </p>
        </Card>
      )}

      {report && (
        <>
          <TradingIntelligenceDashboard
            ticker={tickerParam}
            report={report}
            isDark={theme === "dark"}
            analogRows={(analogQuery.data as AnalogRow[] | undefined) ?? []}
            analogsLoading={analogQuery.isLoading}
            dominantEventLabel={dominantEvent}
          />
          <ExplainabilitySection report={report} />
          <DeliberationDashboard
            ticker={tickerParam}
            report={report}
            isDark={theme === "dark"}
          />
          {/* Section 3: full Reverse BWB Opportunity Explorer with filters/sort
              and a history snapshot picker. Live + history come from the
              market-data tables, completely independent of the frozen
              analysis snapshot above. */}
          {isWatchlistTicker && <OpportunityExplorer ticker={tickerParam} />}
        </>
      )}
    </div>
  );
}
