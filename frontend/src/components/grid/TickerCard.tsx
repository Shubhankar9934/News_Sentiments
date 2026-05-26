/**
 * TickerCard — Layer-1 dashboard card.
 *
 * Renders a fixed-size card per the spec (420px width, 650px min-height,
 * 8 sections). Drives its own state machine (IDLE / RUNNING / COMPLETED /
 * FAILED) from three React Query primitives:
 *
 *   - `useRunAnalysis(ticker)` — local mutation state (running/error)
 *   - `useTickerSummaries`     — back-end projection driving COMPLETED look
 *   - `useDeliberation(id)`    — polling for the per-model progress strip
 *
 * The card itself owns no business state. It just composes presentational
 * children and routes user clicks. Open Full Report is a `useNavigate`
 * push to /report/:ticker — same domain, no extra fetch.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ActionBar } from "@/components/grid/ActionBar";
import { CardHeader } from "@/components/grid/CardHeader";
import { ExecutiveMetrics } from "@/components/grid/ExecutiveMetrics";
import { ExecutiveSummary } from "@/components/grid/ExecutiveSummary";
import { MarketIndicators } from "@/components/grid/MarketIndicators";
import { MovementRiskPanel } from "@/components/grid/MovementRiskPanel";
import { ReportFooter } from "@/components/grid/ReportFooter";
import { RunningProgress } from "@/components/grid/RunningProgress";
import { StatusStrip } from "@/components/grid/StatusStrip";
import { useDeliberation } from "@/hooks/useDeliberation";
import { useInvalidateSummaries } from "@/hooks/useTickerSummaries";
import { useRunAnalysis } from "@/hooks/useRunAnalysis";
import { ALL_WATCHLIST_TICKERS } from "@/config/watchlist";
import { useTickerLiveOpportunities, useLiveFeedStatus } from "@/hooks/useLiveMarketData";
import { SectionFrame } from "@/components/grid/primitives";
import { cn } from "@/lib/utils";
import type {
  ExecutiveSummary as ExecutiveSummaryT,
  FeedStatus,
  LiveOpportunityBundle,
  TickerSummaryRow,
} from "@/types/schemas";

function LiveOpportunitiesPreview({
  live,
  feedStatus,
}: {
  live: LiveOpportunityBundle | null;
  feedStatus: FeedStatus;
}) {
  const calls = live?.calls ?? [];
  const puts = live?.puts ?? [];
  const hasData = calls.length > 0 || puts.length > 0;
  const isOffline = feedStatus === "disconnected" || feedStatus === "unavailable";

  const emptyMsg = isOffline
    ? "IBKR disconnected"
    : "Awaiting market data";

  function OpTable({ label, rows }: { label: string; rows: typeof calls }) {
    return (
      <div className="flex flex-col">
        <div className="bg-[hsl(var(--terminal-card-elevated))]/70 px-2 py-1 text-[9px] font-semibold uppercase tracking-wider text-[hsl(var(--terminal-text-secondary))]">
          {label}
        </div>
        <table className="w-full table-fixed border-collapse">
          <colgroup>
            <col style={{ width: "28%" }} />
            <col style={{ width: "8%" }} />
            <col style={{ width: "10%" }} />
            <col style={{ width: "18%" }} />
            <col style={{ width: "18%" }} />
            <col style={{ width: "18%" }} />
          </colgroup>
          <thead>
            <tr className="bg-[hsl(var(--terminal-card-elevated))]/40 text-[9px] font-semibold uppercase tracking-wider text-[hsl(var(--terminal-text-tertiary))]">
              <th className="px-2 py-1 text-left">Combo</th>
              <th className="px-2 py-1 text-left">Exp</th>
              <th className="px-2 py-1 text-right" title="Distance of first combo strike from spot price (not options Δ)">Delta</th>
              <th className="px-2 py-1 text-right">Premium</th>
              <th className="px-2 py-1 text-right">Margin</th>
              <th className="px-2 py-1 text-right">Liquidity</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-2 py-2 text-center font-mono text-[10px] text-[hsl(var(--terminal-text-tertiary))]">
                  {hasData ? "—" : emptyMsg}
                </td>
              </tr>
            ) : (
              rows.slice(0, 2).map((r, idx) => {
                const premiumDollars = r.premium * 100;
                const premiumClass = premiumDollars < 0 ? "text-emerald-300" : "text-rose-300";
                const premiumStr = `${premiumDollars < 0 ? "-" : "+"}$${Math.abs(premiumDollars).toFixed(0)}`;
                const marginStr = r.init_margin != null ? `$${r.init_margin.toFixed(0)}` : "—";
                const deltaStr = r.delta_pct != null ? `${r.delta_pct > 0 ? "+" : ""}${r.delta_pct.toFixed(1)}` : "—";
                // minimum_open_interest=0 means OI was unavailable (snapshot mode);
                // in that case liquidity holds the volume proxy instead.
                const isVolProxy = (r.minimum_open_interest ?? 0) === 0 && r.liquidity > 0;
                const liqNum = r.liquidity > 0
                  ? r.liquidity >= 1000 ? `${(r.liquidity / 1000).toFixed(0)}k` : String(r.liquidity)
                  : null;
                const liqStr = liqNum ? `${liqNum}${isVolProxy ? "v" : "L"}` : "—";
                return (
                  <tr key={`${r.combo}-${r.expiration}-${idx}`} className="border-t border-[hsl(var(--terminal-border))]/60">
                    <td className="truncate px-2 py-1 text-left font-mono text-[11px] tabular-nums text-slate-100" title={r.combo}>{r.combo}</td>
                    <td className="px-2 py-1 text-left font-mono text-[11px] tabular-nums text-slate-200">{r.expiration}</td>
                    <td className="px-2 py-1 text-right font-mono text-[11px] tabular-nums text-slate-300">{deltaStr}</td>
                    <td className={cn("px-2 py-1 text-right font-mono text-[11px] tabular-nums", premiumClass)}>{premiumStr}</td>
                    <td className="px-2 py-1 text-right font-mono text-[11px] tabular-nums text-slate-200">{marginStr}</td>
                    <td className="px-2 py-1 text-right font-mono text-[11px] tabular-nums text-slate-200">{liqStr}</td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <SectionFrame title="Options Opportunities">
      <div className="overflow-hidden rounded-md border border-[hsl(var(--terminal-border))] bg-[hsl(var(--terminal-card-elevated))]/50">
        <OpTable label="Call Opportunities" rows={calls} />
        <div className="border-t border-[hsl(var(--terminal-border))]" />
        <OpTable label="Put Opportunities" rows={puts} />
      </div>
    </SectionFrame>
  );
}

export type TickerCardStatus = "IDLE" | "RUNNING" | "COMPLETED" | "FAILED";

type Props = {
  ticker: string;
  company: string;
  row: TickerSummaryRow | null;
  /** External "Run All" pulse: when true, treat the card as RUNNING from the parent. */
  externalRunning?: boolean;
};

export function TickerCard({ ticker, company, row, externalRunning }: Props) {
  const navigate = useNavigate();
  const run = useRunAnalysis(ticker);
  const invalidate = useInvalidateSummaries();

  // Local error from a failed mutation, sticky until the next click.
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const reportId = row?.report_id ?? null;
  const deliberationStatus = row?.deliberation_status ?? null;
  const deliberation = useDeliberation(reportId ?? undefined);

  // The card is RUNNING whenever any of: the local mutation is in flight,
  // the parent "Run All" loop ticked us, or the persisted DIL layer is still
  // pending/running on the back-end.
  const layer = deliberation.data;
  const dilActive =
    deliberationStatus === "pending" ||
    deliberationStatus === "running" ||
    layer?.status === "pending" ||
    layer?.status === "running";

  const status: TickerCardStatus = useMemo(() => {
    if (run.isPending || externalRunning) return "RUNNING";
    if (errorMessage) return "FAILED";
    if (dilActive) return "RUNNING";
    if (row?.executive_summary) return "COMPLETED";
    return "IDLE";
  }, [run.isPending, externalRunning, errorMessage, dilActive, row?.executive_summary]);

  // Whenever the polled DIL transitions to complete, refresh the projection.
  // Tracked via a ref so we fire ONCE per transition — depending on `layer.status`
  // alone would re-invalidate on every poll-driven re-render and storm the
  // /summaries endpoint with 12 cards in the grid.
  const lastDilStatusRef = useRef<string | null>(null);
  useEffect(() => {
    const cur = layer?.status ?? null;
    const prev = lastDilStatusRef.current;
    lastDilStatusRef.current = cur;
    if (cur === "complete" && prev !== "complete") {
      invalidate(ALL_WATCHLIST_TICKERS);
    }
  }, [layer?.status, invalidate]);

  // Surface mutation errors via toast; keep the card stuck in FAILED.
  useEffect(() => {
    if (run.isError) {
      const msg = run.error instanceof Error ? run.error.message : "Run analysis failed";
      setErrorMessage(msg);
      toast.error(`${ticker}: ${msg}`);
    }
  }, [run.isError, run.error, ticker]);

  useEffect(() => {
    if (run.isPending) setErrorMessage(null);
  }, [run.isPending]);

  const handleRun = () => {
    setErrorMessage(null);
    run.mutate(undefined, {
      onSuccess: () => {
        toast.success(`${ticker} analysis started`);
      },
    });
  };

  const handleOpenReport = () => {
    navigate(`/report/${encodeURIComponent(ticker)}`);
  };

  const summary: ExecutiveSummaryT | null = row?.executive_summary ?? null;
  const isRunning = status === "RUNNING";

  const liveOpps = useTickerLiveOpportunities(ticker);
  const liveFeedStatus = useLiveFeedStatus();

  return (
    <article
      className={cn(
        "grid-card group",
        status === "FAILED" && "border-rose-500/40",
        status === "RUNNING" && "border-amber-500/30",
      )}
      aria-busy={isRunning}
      aria-labelledby={`card-${ticker}-title`}
    >
      <div id={`card-${ticker}-title`} className="sr-only">
        {ticker} {company} executive summary
      </div>

      <CardHeader
        ticker={ticker}
        company={company}
        price={row?.last_close ?? null}
        dailyChangePct={row?.session_change_pct ?? null}
      />

      <ActionBar
        status={status}
        onRunAnalysis={handleRun}
        onOpenFullReport={handleOpenReport}
        hasReport={Boolean(reportId)}
      />

      <StatusStrip
        decision={summary?.decision ?? null}
        creditSafetyScore={summary?.credit_safety_score ?? null}
        loading={isRunning && !summary}
      />

      <ExecutiveMetrics summary={summary} />

      <MovementRiskPanel summary={summary} />

      <MarketIndicators summary={summary} />

      <LiveOpportunitiesPreview live={liveOpps} feedStatus={liveFeedStatus} />

      {isRunning ? (
        <RunningProgress
          layer={layer ?? null}
          fallbackMessage={
            run.isPending ? "Calling /research, expect ~5-10s before DIL kicks off." : undefined
          }
        />
      ) : (
        <ExecutiveSummary
          text={summary?.summary ?? null}
          loading={false}
          version={summary?.summary_version}
        />
      )}

      <div className="mt-auto" />

      <ReportFooter
        lastRunAt={row?.last_run_at ?? null}
        state={status}
        error={errorMessage ?? undefined}
      />
    </article>
  );
}
