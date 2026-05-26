/**
 * Single-hop fetcher for the Reverse BWB Intelligence Dashboard grid.
 *
 *   GET /api/v1/dashboard/tickers
 *
 * Returns ``{ status, cards }`` where ``cards`` is the canonical 12-row
 * watchlist (in tier/order) — rows without persisted data come back with
 * ``status: "pending"`` so the grid layout never shifts.
 *
 * Refetches every 30s so cards stay live while the user lingers on the
 * tab; any explicit refresh mutation invalidates this query so a fresh
 * batch lands immediately.
 */

import { useCallback } from "react";
import { useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { z } from "zod";

import { apiClient } from "@/api/client";
import { WATCHLIST_COMPANY_BY_SYMBOL, WATCHLIST_TIERS } from "@/config/watchlist";
import {
  dashboardTickerCardSchema,
  parseResearchReportLoose,
  watchlistBatchStatusSchema,
  type DashboardTickerCard,
  type DashboardTickersResponse,
  type ResearchReport,
} from "@/types/schemas";

const REFETCH_MS = 30_000;
const REFETCH_RUNNING_MS = 3_000;
const REFETCH_POST_BATCH_MS = 5_000;
const STALE_MS = 15_000;

export const DASHBOARD_CARDS_QUERY_KEY = ["dashboard", "tickers"] as const;
export const LATEST_REPORT_QUERY_KEY = "latest-report";
export const DASHBOARD_TICKER_REPORT_QUERY_KEY = "dashboard-ticker-report";

export function dashboardTickerReportQueryKey(ticker: string) {
  return [DASHBOARD_TICKER_REPORT_QUERY_KEY, ticker.toUpperCase()] as const;
}

const TIER_KEY_BY_SYMBOL: Record<string, string> = Object.fromEntries(
  WATCHLIST_TIERS.flatMap((tier) => tier.tickers.map((t) => [t.symbol, tier.key])),
);

function fallbackCard(raw: unknown, parseError: string): DashboardTickerCard {
  const ticker =
    typeof raw === "object" && raw !== null && "ticker" in raw
      ? String((raw as { ticker: unknown }).ticker).toUpperCase()
      : "UNKNOWN";

  return {
    ticker,
    company_name: WATCHLIST_COMPANY_BY_SYMBOL[ticker] ?? ticker,
    tier_key: TIER_KEY_BY_SYMBOL[ticker] ?? "unknown",
    status: "pending",
    generated_at: null,
    price_snapshot: null,
    reverse_bwb: null,
    opportunities: null,
    report_id: null,
    error_message: parseError,
  };
}

function parseDashboardResponse(data: unknown): DashboardTickersResponse {
  const envelope = z
    .object({
      status: watchlistBatchStatusSchema,
      cards: z.array(z.unknown()),
    })
    .parse(data);

  const cards = envelope.cards.map((raw) => {
    const parsed = dashboardTickerCardSchema.safeParse(raw);
    if (parsed.success) return parsed.data;
    const message =
      parsed.error.issues[0]?.message ?? "Card payload failed validation";
    return fallbackCard(raw, message);
  });

  return { status: envelope.status, cards };
}

function isWithinPostBatchWindow(finishedAt: string | null | undefined): boolean {
  if (!finishedAt) return false;
  const finishedMs = new Date(finishedAt).getTime();
  if (Number.isNaN(finishedMs)) return false;
  return Date.now() - finishedMs < REFETCH_POST_BATCH_MS;
}

function dashboardRefetchInterval(data: DashboardTickersResponse | undefined): number | false {
  const status = data?.status;
  if (!status) return REFETCH_MS;
  if (status.state === "running") return REFETCH_RUNNING_MS;
  if (isWithinPostBatchWindow(status.finished_at)) return REFETCH_RUNNING_MS;
  return REFETCH_MS;
}

export function isTickerInActiveBatch(
  ticker: string,
  status: DashboardTickersResponse["status"] | undefined,
): boolean {
  if (!status || status.state !== "running") return false;
  const upper = ticker.toUpperCase();
  return status.current_ticker === upper || (status.queued ?? []).includes(upper);
}

export function useDashboardCards(): UseQueryResult<DashboardTickersResponse> {
  return useQuery({
    queryKey: DASHBOARD_CARDS_QUERY_KEY,
    queryFn: async (): Promise<DashboardTickersResponse> => {
      const { data } = await apiClient.get("/dashboard/tickers");
      return parseDashboardResponse(data);
    },
    refetchInterval: (query) => dashboardRefetchInterval(query.state.data),
    refetchOnWindowFocus: false,
    staleTime: STALE_MS,
    retry: (failureCount, error) => {
      const status = (error as { response?: { status?: number } }).response?.status;
      return status === 429 && failureCount < 4;
    },
    retryDelay: (attempt) => Math.min(2_000 * 2 ** attempt, 30_000),
  });
}

export function useInvalidateDashboardCards() {
  const qc = useQueryClient();
  return useCallback(() => {
    qc.invalidateQueries({ queryKey: DASHBOARD_CARDS_QUERY_KEY });
  }, [qc]);
}

type DashboardTickerReportPayload = {
  ticker: string;
  status: string;
  research_report_id: string | null;
  generated_at: string | null;
  report_json: ResearchReport;
};

export function useDashboardTickerReport(
  ticker: string,
  options?: { enabled?: boolean; refetchWhileBatchActive?: boolean },
) {
  const upper = ticker.toUpperCase();
  const enabled = (options?.enabled ?? true) && upper.length > 0;

  return useQuery({
    queryKey: dashboardTickerReportQueryKey(upper),
    queryFn: async (): Promise<ResearchReport | null> => {
      const { data } = await apiClient.get(
        `/dashboard/tickers/${encodeURIComponent(upper)}/report`,
      );
      const payload = data as DashboardTickerReportPayload;
      const { report } = parseResearchReportLoose(payload.report_json);
      return report;
    },
    enabled,
    staleTime: STALE_MS,
    refetchInterval: options?.refetchWhileBatchActive ? REFETCH_RUNNING_MS : false,
    retry: (failureCount, error) => {
      const status = (error as { response?: { status?: number } }).response?.status;
      if (status === 404) return false;
      return status === 429 && failureCount < 4;
    },
    retryDelay: (attempt) => Math.min(2_000 * 2 ** attempt, 30_000),
  });
}

export function invalidateAllLatestReports(
  qc: ReturnType<typeof useQueryClient>,
) {
  void qc.invalidateQueries({ queryKey: [LATEST_REPORT_QUERY_KEY] });
  void qc.invalidateQueries({ queryKey: [DASHBOARD_TICKER_REPORT_QUERY_KEY] });
}

export function invalidateDashboardTickerReport(
  qc: ReturnType<typeof useQueryClient>,
  ticker: string,
) {
  void qc.invalidateQueries({ queryKey: dashboardTickerReportQueryKey(ticker) });
}
