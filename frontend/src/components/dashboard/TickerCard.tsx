/**

 * Strict 3-section Reverse BWB ticker card.

 *

 *   Section 1: CardHeader  (ticker / company / price / daily % / actions)

 *   Section 2: ReverseBwbCreditView  (LLM-synthesised credit-collector intelligence)

 *   Section 3: OptionOpportunitiesTables (Reverse-BWB combo opportunities)

 *

 * Header actions: Re-run Analysis (queued single-ticker refresh) and Open Full Report.

 * Failed/pending cards show an EmptyCardState in place of sections 2 + 3.

 */



import { ArrowUpRight, Clock, Loader2, Play, RefreshCw } from "lucide-react";

import { useNavigate } from "react-router-dom";



import { CardAnalysisMeta } from "@/components/dashboard/CardAnalysisMeta";

import { CardHeader } from "@/components/grid/CardHeader";

import { EmptyCardState } from "@/components/dashboard/EmptyCardState";

import { OptionOpportunitiesTables } from "@/components/dashboard/OptionOpportunitiesTables";

import { ReverseBwbCreditView } from "@/components/dashboard/ReverseBwbCreditView";

import { Button } from "@/components/ui/button";

import { cn } from "@/lib/utils";

import {
  useLiveFeedStatus,
  useTickerLiveOpportunities,
  useTickerLiveQuote,
} from "@/hooks/useLiveMarketData";

import type {

  DashboardTickerCard as DashboardTickerCardType,

  FeedStatus,

  WatchlistBatchStatus,

} from "@/types/schemas";



type Props = {

  card: DashboardTickerCardType;

  batchStatus: WatchlistBatchStatus;

  onRerun: (ticker: string) => void;

};



const outlineBtnClass =

  "h-8 border-[hsl(var(--terminal-border))] px-2.5 text-[11px] text-[hsl(var(--terminal-text-primary))] hover:bg-[hsl(var(--terminal-card-elevated))]";



export function TickerCard({ card, batchStatus, onRerun }: Props) {

  const navigate = useNavigate();

  // Live IBKR slices for this card. These are read from a single bulk
  // query (`useLiveMarketData`) so all 12 cards share one network call;
  // the selectors below are pure cache reads. The Reverse BWB credit
  // view + meta strip continue to render exclusively from the snapshot.
  const liveQuote = useTickerLiveQuote(card.ticker);
  const liveOpps = useTickerLiveOpportunities(card.ticker);
  const liveFeedStatus: FeedStatus = useLiveFeedStatus();

  const livePrice = liveQuote?.last_price ?? null;
  const liveChangePct = liveQuote?.change_pct ?? null;
  // Per-quote status falls back to the top-level connection status so
  // that a card whose ticker has never received a tick still renders
  // "Live data unavailable" when IBKR is disconnected.
  const headerLiveStatus: FeedStatus =
    liveQuote?.feed_status ?? liveFeedStatus;

  // Snapshot-time price is preserved as a backstop only — once a live
  // quote arrives, it always wins.
  const headerPrice = livePrice ?? card.price_snapshot?.price ?? null;
  const headerChangePct =
    liveChangePct ?? card.price_snapshot?.daily_change_pct ?? null;



  const handleOpenReport = () => {

    navigate(`/report/${encodeURIComponent(card.ticker)}`);

  };



  const current = batchStatus.current_ticker;

  const isThisTickerRunning =

    batchStatus.state === "running" && current === card.ticker;

  const isQueued =

    (batchStatus.queued ?? []).includes(card.ticker) && current !== card.ticker;

  const canRerun = !isThisTickerRunning && !isQueued;



  const renderedStatus = isThisTickerRunning ? "running" : card.status;

  const hasData = card.status === "completed" && card.reverse_bwb;

  const canOpenReport = Boolean(card.report_id) && !isThisTickerRunning;



  const runLabel = isThisTickerRunning

    ? "Running…"

    : isQueued

      ? "Queued"

      : renderedStatus === "failed"

        ? "Retry"

        : card.status === "completed"

          ? "Re-run Analysis"

          : "Run Analysis";

  const RunIcon = isThisTickerRunning

    ? Loader2

    : isQueued

      ? Clock

      : renderedStatus === "failed"

        ? RefreshCw

        : Play;



  const analysisStatus = isThisTickerRunning ? "running" : card.status;



  return (

    <article

      className={cn(

        "grid-card flex flex-col gap-4",

        renderedStatus === "failed" && "border-rose-500/30",

        (isThisTickerRunning || isQueued) && "border-amber-500/40 ring-1 ring-amber-500/20",

      )}

      data-status={renderedStatus}

      aria-busy={isThisTickerRunning}

    >

      <CardHeader

        ticker={card.ticker}

        company={card.company_name}

        price={headerPrice}

        dailyChangePct={headerChangePct}

        liveStatus={headerLiveStatus}

        action={

          <div className="flex flex-wrap items-center justify-end gap-1.5">

            <Button

              size="sm"

              onClick={() => onRerun(card.ticker)}

              disabled={!canRerun}

              className="h-8 bg-indigo-500 px-2.5 text-[11px] text-white hover:bg-indigo-400 dark:bg-indigo-500 dark:hover:bg-indigo-400"

            >

              <RunIcon

                className={cn("h-3.5 w-3.5", isThisTickerRunning && "animate-spin")}

                aria-hidden="true"

              />

              {runLabel}

            </Button>

            <Button

              size="sm"

              variant="outline"

              onClick={handleOpenReport}

              disabled={!canOpenReport}

              className={outlineBtnClass}

            >

              <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />

              Open Full Report

            </Button>

          </div>

        }

      />



      <CardAnalysisMeta

        generatedAt={card.generated_at}

        status={analysisStatus}

        isRunning={isThisTickerRunning}

        errorMessage={card.error_message}

      />



      {hasData && card.reverse_bwb ? (

        <>

          <ReverseBwbCreditView summary={card.reverse_bwb} />

          <OptionOpportunitiesTables

            live={liveOpps}

            feedStatus={liveFeedStatus}

          />

        </>

      ) : (

        <EmptyCardState

          status={

            isQueued || isThisTickerRunning

              ? "running"

              : renderedStatus === "completed"

                ? "pending"

                : renderedStatus

          }

          errorMessage={card.error_message ?? null}

        />

      )}

    </article>

  );

}


