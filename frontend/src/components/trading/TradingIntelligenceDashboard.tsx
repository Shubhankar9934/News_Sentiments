import { useMemo, type ReactNode } from "react";
import { ResearchReportCharts } from "@/components/dashboard/ResearchReportCharts";
import { NewsCard } from "@/components/news/NewsCard";
import { NewsTimeline } from "@/components/news/NewsTimeline";
import { SourceBadge } from "@/components/news/SourceBadge";
import { OptionsIntelligencePanel } from "@/components/options/OptionsIntelligencePanel";
import { TickerSummaryCard } from "@/components/trading/TickerSummaryCard";
import { Card } from "@/components/ui/card";
import {
  deriveTradingView,
  formatExpectedMove,
  isTodayImportant,
} from "@/lib/deriveTradeDecision";
import { getArticleEvidence, getPipelineMeta, getPriceSnapshot } from "@/lib/pipelineMeta";
import type { ArticleEvidence, ResearchReport } from "@/types/schemas";

type KeyEventRow = NonNullable<ResearchReport["key_events"]>[number];

export type AnalogRow = {
  headline?: string | null;
  published_at?: string | null;
  sentiment_score?: number | null;
  impact_score?: number | null;
  close?: number | null;
  volume?: number | null;
  match_reason?: string | null;
  match_score?: number | null;
};

const ANALOG_REASON_LABEL: Record<string, { label: string; cls: string }> = {
  exact_event_type: {
    label: "Same event type",
    cls: "border-slate-400/40 bg-slate-100/60 text-slate-700 dark:bg-slate-700/40 dark:text-slate-200",
  },
  semantic: {
    label: "Semantic match",
    cls: "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-200",
  },
  earnings_beat_sell_off: {
    label: "Sell-the-news",
    cls: "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-200",
  },
  sector_rotation: {
    label: "Sector rotation",
    cls: "border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-100",
  },
};

type Props = {
  ticker: string;
  report: ResearchReport;
  isDark: boolean;
  analogRows?: AnalogRow[];
  analogsLoading?: boolean;
  dominantEventLabel?: string | null;
};

function findLlmArticle(row: ArticleEvidence, articles: ResearchReport["articles"]) {
  if (!articles?.length) return undefined;
  const h = (row.headline ?? "").toLowerCase().trim();
  return (
    articles.find((a) => (a.headline ?? "").toLowerCase().trim() === h) ??
    articles.find((a) => {
      const ah = (a.headline ?? "").toLowerCase().trim();
      return ah.length > 20 && (h.includes(ah.slice(0, 40)) || ah.includes(h.slice(0, 40)));
    })
  );
}

function SectionTitle({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-2 flex items-baseline justify-between gap-2">
      <h2 className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
        {title}
      </h2>
      {children}
    </div>
  );
}

function Pill({ children, tone }: { children: ReactNode; tone?: "ok" | "warn" | "bad" | "neutral" }) {
  const cls =
    tone === "ok"
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200"
      : tone === "warn"
        ? "border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-100"
        : tone === "bad"
          ? "border-rose-500/30 bg-rose-500/10 text-rose-800 dark:text-rose-200"
          : "border-[hsl(var(--border))] bg-[hsl(var(--muted))] text-slate-700 dark:text-slate-200";
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${cls}`}>
      {children}
    </span>
  );
}

export function TradingIntelligenceDashboard({
  ticker,
  report,
  isDark,
  analogRows,
  analogsLoading,
  dominantEventLabel,
}: Props) {
  const derived = useMemo(() => deriveTradingView(report, ticker), [report, ticker]);
  const today = useMemo(() => isTodayImportant(report), [report]);
  const evidence = useMemo(() => getArticleEvidence(report), [report]);
  const snap = getPriceSnapshot(report);
  const meta = getPipelineMeta(report);
  const pred = report.price_prediction;

  const catalysts = useMemo((): KeyEventRow[] => {
    const ke = report.key_events ?? [];
    return [...ke].sort((a, b) => (b.impact_score ?? 0) - (a.impact_score ?? 0)).slice(0, 8);
  }, [report.key_events]);

  const instLines = useMemo(() => {
    const sr = report.source_reliability ?? [];
    return [...sr]
      .sort((a, b) => (b.reliability_score ?? 0) - (a.reliability_score ?? 0))
      .slice(0, 12)
      .map((s) => ({
        source: s.source,
        tier: s.tier,
        score: s.reliability_score,
        n: s.articles,
      }));
  }, [report.source_reliability]);

  const topEvidence = useMemo(() => {
    return [...evidence].sort((a, b) => (b.impact_score ?? 0) - (a.impact_score ?? 0)).slice(0, 10);
  }, [evidence]);

  const eventConfirm = useMemo(() => {
    const top = catalysts[0];
    if (!top?.type) return null;
    const t = top.type;
    const sources = new Set(
      evidence
        .filter((e: ArticleEvidence) => (e.event_type ?? "").toLowerCase() === t.toLowerCase())
        .map((e: ArticleEvidence) => e.source)
        .filter((s): s is string => typeof s === "string" && s.length > 0)
    );
    return { type: t, sources: [...sources].slice(0, 8) };
  }, [catalysts, evidence]);

  const sessionPct = snap?.last_session_change_pct;
  const volVs = snap?.volume_vs_avg;

  return (
    <div className="space-y-5">
      <TickerSummaryCard ticker={ticker} report={report} />

      <div className="rounded-xl border border-indigo-500/25 bg-gradient-to-br from-indigo-500/5 via-transparent to-transparent px-4 py-3 dark:from-indigo-400/10">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-indigo-700 dark:text-indigo-300">
          Core question
        </p>
        <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-50">
          Should I even consider trading <span className="font-mono">{ticker.toUpperCase()}</span> today?
        </p>
        <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
          Noise → context → conviction → decision. AI summarizes; you verify sources; you decide.
        </p>
      </div>

      {/* 1 Snapshot */}
      <Card className="p-4">
        <SectionTitle title="1 · Stock snapshot">2-second attention filter</SectionTitle>
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <div className="font-mono text-3xl font-bold tracking-tight">{ticker.toUpperCase()}</div>
            <div className="mt-1 flex flex-wrap gap-2">
              <Pill tone={typeof sessionPct === "number" && sessionPct >= 0 ? "ok" : typeof sessionPct === "number" ? "bad" : "neutral"}>
                Last session {typeof sessionPct === "number" ? `${sessionPct >= 0 ? "+" : ""}${sessionPct.toFixed(2)}%` : "move n/a"}
              </Pill>
              <Pill>Signal {derived.signal}</Pill>
              <Pill>Confidence {derived.signalConfidencePct}%</Pill>
              <Pill tone="warn">Volatility {(pred?.volatility_regime ?? meta?.volatility_regime ?? "—").toString().toUpperCase()}</Pill>
              <Pill>News strength {derived.newsStrength}</Pill>
              <Pill tone={derived.riskLevel === "HIGH" ? "bad" : "neutral"}>Risk {derived.riskLevel}</Pill>
            </div>
          </div>
        </div>
        <dl className="mt-4 grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt className="text-slate-500">Last close (Polygon)</dt>
            <dd className="font-mono text-sm font-semibold">{snap?.last_close != null ? snap.last_close.toFixed(2) : "—"}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Volume vs 20d avg</dt>
            <dd className="font-mono text-sm font-semibold">{volVs != null ? `${volVs.toFixed(2)}×` : "—"}</dd>
          </div>
          <div>
            <dt className="text-slate-500">ATR / tape context</dt>
            <dd className="text-sm font-semibold text-slate-600 dark:text-slate-300">Use your platform ATR</dd>
          </div>
          <div>
            <dt className="text-slate-500">Sector · SPY</dt>
            <dd className="text-sm text-slate-600 dark:text-slate-300">
              {derived.sectorNote} {derived.spyNote}
            </dd>
          </div>
        </dl>
        <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-500">
          <span>
            Today importance: <strong className="text-slate-800 dark:text-slate-100">{today.level}</strong> — {today.detail}
          </span>
          <span className="rounded bg-[hsl(var(--muted))] px-2 py-0.5 font-mono text-[10px]">
            data_mode {report.data_mode ?? meta?.data_mode ?? "—"}
          </span>
        </div>
      </Card>

      {/* 2 AI summary */}
      <Card className="p-4">
        <SectionTitle title="2 · AI market summary">Institutional-style note</SectionTitle>
        <div className="space-y-3 text-sm leading-relaxed text-slate-800 dark:text-slate-100">
          {report.dominant_narrative && (
            <p>
              <span className="font-semibold text-slate-900 dark:text-white">Thesis. </span>
              {report.dominant_narrative}
            </p>
          )}
          {report.what_happened && (
            <p>
              <span className="font-semibold text-slate-900 dark:text-white">What happened. </span>
              {report.what_happened}
            </p>
          )}
          {report.price_movers && (
            <p>
              <span className="font-semibold text-slate-900 dark:text-white">Tape read. </span>
              {report.price_movers}
            </p>
          )}
          {pred?.reasoning && (
            <p className="rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--muted))] p-3 text-xs text-slate-700 dark:text-slate-200">
              <span className="font-semibold">Model reasoning. </span>
              {pred.reasoning}
            </p>
          )}
          {!report.dominant_narrative && !report.what_happened && (
            <p className="text-slate-500">No narrative block in this cached report — re-run research on latest backend.</p>
          )}
        </div>
      </Card>

      {/* 3 Trade decision */}
      <Card className="p-4">
        <SectionTitle title="3 · Trade decision panel">Directional clarity</SectionTitle>
        {derived.noTrade && (
          <div className="mb-3 rounded-lg border-2 border-dashed border-amber-500/50 bg-amber-500/5 px-3 py-2 text-sm font-semibold text-amber-900 dark:text-amber-100">
            NO TRADE (default bias) — {derived.noTradeReason}
          </div>
        )}
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2 text-sm">
            <div className="text-xs font-semibold uppercase text-slate-500">Today&apos;s market bias</div>
            <div className="flex flex-wrap gap-2">
              <Pill>Direction {pred?.bias ?? derived.signal}</Pill>
              <Pill>Expected move {formatExpectedMove(report)}</Pill>
              <Pill>Momentum {derived.momentumLabel}</Pill>
              <Pill>Vol regime {(pred?.volatility_regime ?? meta?.volatility_regime ?? "—").toString().toUpperCase()}</Pill>
              <Pill>Inst. confidence {derived.signalConfidencePct}%</Pill>
              <Pill tone={derived.tradeQuality === "NO TRADE" ? "warn" : "ok"}>Trade quality {derived.tradeQuality}</Pill>
            </div>
          </div>
          <div>
            <div className="text-xs font-semibold uppercase text-slate-500">Suggested strategy</div>
            <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-slate-700 dark:text-slate-200">
              {derived.strategyBullets.map((b: string) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          </div>
        </div>
      </Card>

      {/* 3.5 Options intelligence */}
      {report.options_intelligence && (
        <OptionsIntelligencePanel options={report.options_intelligence} />
      )}

      {/* 4 Catalysts */}
      <Card className="p-4">
        <SectionTitle title="4 · Why the tape is moving">Top catalysts</SectionTitle>
        <ol className="list-decimal space-y-3 pl-4 text-sm">
          {catalysts.map((ev: KeyEventRow, idx: number) => (
            <li key={`${ev.description}-${idx}`} className="text-slate-800 dark:text-slate-100">
              <div className="font-medium">{ev.description ?? ev.type ?? "Driver"}</div>
              <div className="mt-0.5 text-xs text-slate-500">
                Impact {ev.impact ?? "—"} · score {typeof ev.impact_score === "number" ? ev.impact_score.toFixed(3) : "—"}
                {ev.type ? ` · ${ev.type}` : ""}
              </div>
            </li>
          ))}
        </ol>
        {eventConfirm && eventConfirm.sources.length > 0 && (
          <div className="mt-4 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--muted))] p-3 text-xs">
            <div className="font-semibold text-slate-800 dark:text-slate-100">Event confidence ({eventConfirm.type})</div>
            <p className="mt-1 text-slate-600 dark:text-slate-300">
              Same event bucket echoed by: {eventConfirm.sources.join(" · ")}
            </p>
          </div>
        )}
      </Card>

      {/* 5 Institutional sentiment */}
      <Card className="p-4">
        <SectionTitle title="5 · Source stack">Institutional vs headline mill</SectionTitle>
        <div className="grid gap-2 sm:grid-cols-2">
          {instLines.map((row: { source: string; tier?: string; score?: number; n?: number }) => (
            <div
              key={row.source}
              className="flex items-center justify-between gap-2 rounded-md border border-[hsl(var(--border))] px-2 py-1.5 text-xs"
            >
              <SourceBadge source={row.source} tier={row.tier} className="max-w-[11rem]" />
              <span className="shrink-0 text-slate-500">
                {row.n != null ? `${row.n} art.` : ""} · rel. {row.score ?? "—"}
              </span>
            </div>
          ))}
        </div>
        <div className="mt-3 rounded-md border border-[hsl(var(--border))] p-3 text-xs text-slate-700 dark:text-slate-200">
          <span className="font-semibold">Read. </span>
          {derived.institutionalTone}. {derived.retailTone}
        </div>
      </Card>

      {/* 6 Alignment */}
      <Card className="p-4">
        <SectionTitle title="6 · News / price alignment">Is the tape confirming?</SectionTitle>
        <div className="grid gap-2 text-sm sm:grid-cols-2">
          <div className="rounded-md border border-[hsl(var(--border))] p-3">
            <div className="text-xs font-semibold uppercase text-slate-500">Checks</div>
            <ul className="mt-2 space-y-1 text-slate-700 dark:text-slate-200">
              <li>Bullish/bearish skew (model): {derived.alignment.newsBias}</li>
              <li>Price confirmation: {derived.alignment.priceConfirmation}</li>
              <li>Volume confirmation: {derived.alignment.volumeConfirmation}</li>
              <li>Momentum confirmation: {derived.alignment.momentumConfirmation}</li>
            </ul>
          </div>
          <div className="rounded-md border border-indigo-500/20 bg-indigo-500/5 p-3 text-sm text-slate-800 dark:text-slate-100">
            {derived.alignment.conclusion}
          </div>
        </div>
      </Card>

      {/* 7 Historical */}
      <Card className="p-4">
        <SectionTitle title="7 · Historical analogs">
          {dominantEventLabel ? (
            <span className="text-[10px] font-normal normal-case text-slate-500">Event {dominantEventLabel}</span>
          ) : null}
        </SectionTitle>
        {analogsLoading && <p className="text-xs text-slate-500">Loading SQL analogs…</p>}
        {!analogsLoading && (!analogRows || analogRows.length === 0) && (
          <p className="text-xs text-slate-500">No analog rows for this event type yet — run more history through the pipeline.</p>
        )}
        <ul className="space-y-2 text-sm">
          {(analogRows ?? []).slice(0, 5).map((r: AnalogRow, i: number) => {
            const badge = r.match_reason ? ANALOG_REASON_LABEL[r.match_reason] : undefined;
            return (
              <li key={`${r.headline}-${i}`} className="rounded-md border border-[hsl(var(--border))] px-3 py-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="font-medium text-slate-900 dark:text-slate-50">{r.headline ?? "—"}</div>
                  {badge && (
                    <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${badge.cls}`}>
                      {badge.label}
                    </span>
                  )}
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  {r.published_at ? new Date(r.published_at).toLocaleDateString() : "—"} · close{" "}
                  {r.close != null ? r.close.toFixed(2) : "—"} · vol {r.volume != null ? r.volume.toLocaleString() : "—"}
                  {typeof r.match_score === "number" && (
                    <span className="ml-1 font-mono">· match {(r.match_score * 100).toFixed(0)}%</span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      </Card>

      {/* 8 Risk */}
      <Card className="p-4">
        <SectionTitle title="8 · Risk panel">Avoid the bullish echo chamber</SectionTitle>
        <ul className="list-disc space-y-1 pl-4 text-sm text-slate-700 dark:text-slate-200">
          {pred?.downside_risk && <li>{pred.downside_risk}</li>}
          {pred?.upside_catalyst && <li>Catalyst to respect: {pred.upside_catalyst}</li>}
          {report.data_quality_note && <li>Data quality: {report.data_quality_note}</li>}
          <li>Model disclaimer: {pred?.disclaimer ?? "Not financial advice."}</li>
        </ul>
        {derived.contradictory.show && (
          <div className="mt-3 rounded-md border border-rose-500/30 bg-rose-500/5 p-3 text-xs text-rose-900 dark:text-rose-100">
            <div className="font-bold uppercase tracking-wide">Contradictory signals</div>
            <ul className="mt-2 list-disc pl-4">
              {derived.contradictory.bullets.map((b: string) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          </div>
        )}
      </Card>

      {/* 9 Timeline */}
      <Card className="p-4">
        <SectionTitle title="9 · Live evidence timeline">Newest first — every line links out</SectionTitle>
        <NewsTimeline items={evidence} limit={16} />
      </Card>

      {/* 10 Verdict */}
      <Card className="border-indigo-500/30 p-4 dark:border-indigo-400/25">
        <SectionTitle title="10 · Final desk verdict">Probability vs. risk</SectionTitle>
        <div className="space-y-2 text-sm text-slate-800 dark:text-slate-100">
          <p>
            <span className="font-semibold">Bias. </span>
            {pred?.bias ?? derived.signal} · confidence {derived.signalConfidencePct}%
          </p>
          <p>
            <span className="font-semibold">Why it could matter. </span>
          </p>
          <ul className="list-disc space-y-1 pl-4 text-xs text-slate-700 dark:text-slate-200">
            {derived.whyImportant.map((w: string) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
          <p className="text-xs text-slate-500">
            Compress research time — but always click through on Tier-1/Tier-2 items before sizing risk.
          </p>
        </div>
      </Card>

      {/* Evidence cards */}
      <Card className="p-4">
        <SectionTitle title="Evidence deck">Expand rows — FinBERT + impact + link-out</SectionTitle>
        <div className="space-y-2">
          {topEvidence.map((row: ArticleEvidence) => (
            <NewsCard key={`${row.headline}-${row.published_at}`} row={row} llmArticle={findLlmArticle(row, report.articles)} />
          ))}
        </div>
      </Card>

      <details className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-3">
        <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-500">
          Optional charts (sentiment mix, volume, scenarios)
        </summary>
        <div className="mt-3">
          <ResearchReportCharts report={report} isDark={isDark} />
        </div>
      </details>
    </div>
  );
}
