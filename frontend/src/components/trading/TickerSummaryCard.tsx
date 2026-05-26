import type { ReactNode } from "react";
import { Card } from "@/components/ui/card";
import type { OptionsIntelligence, ResearchReport } from "@/types/schemas";
import { getPriceSnapshot } from "@/lib/pipelineMeta";

type Props = {
  ticker: string;
  report: ResearchReport;
};

type Tone = "ok" | "warn" | "bad" | "neutral";

function tone(label: string): Tone {
  const l = label.toUpperCase();
  if (l === "SAFE" || l === "LOW") return "ok";
  if (l === "CAUTION" || l === "MEDIUM") return "warn";
  if (l === "UNSAFE" || l === "HIGH") return "bad";
  return "neutral";
}

function Pill({ children, t }: { children: ReactNode; t?: Tone }) {
  const cls =
    t === "ok"
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200"
      : t === "warn"
        ? "border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-100"
        : t === "bad"
          ? "border-rose-500/30 bg-rose-500/10 text-rose-800 dark:text-rose-200"
          : "border-[hsl(var(--border))] bg-[hsl(var(--muted))] text-slate-700 dark:text-slate-200";
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${cls}`}>
      {children}
    </span>
  );
}

function MiniMetric({
  label,
  primary,
  pill,
  hint,
}: {
  label: string;
  primary: ReactNode;
  pill?: ReactNode;
  hint?: string;
}) {
  return (
    <div className="flex min-w-[8rem] flex-col gap-0.5 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--card))] px-3 py-1.5">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className="flex items-baseline gap-2">
        <div className="text-sm font-semibold text-slate-900 dark:text-slate-50">{primary}</div>
        {pill}
      </div>
      {hint && <div className="text-[10px] text-slate-500">{hint}</div>}
    </div>
  );
}

function summaryScoreColor(score: number): string {
  if (score >= 7) return "text-emerald-600 dark:text-emerald-300";
  if (score >= 4) return "text-amber-700 dark:text-amber-200";
  return "text-rose-600 dark:text-rose-300";
}

function MinimalCard({ ticker, sessionPct }: { ticker: string; sessionPct: number | null | undefined }) {
  return (
    <Card className="border-indigo-500/25 p-3 dark:border-indigo-400/25">
      <div className="flex flex-wrap items-center gap-3">
        <div className="font-mono text-xl font-bold tracking-tight">{ticker.toUpperCase()}</div>
        <div className="text-xs text-slate-500">
          Options intelligence not available for this report — re-run research to populate Credit Safety, Expected Range, Pin Risk, Event Risk.
        </div>
        {typeof sessionPct === "number" && (
          <Pill t={sessionPct >= 0 ? "ok" : "bad"}>
            {sessionPct >= 0 ? "+" : ""}{sessionPct.toFixed(2)}%
          </Pill>
        )}
      </div>
    </Card>
  );
}

export function TickerSummaryCard({ ticker, report }: Props) {
  const opts: OptionsIntelligence | undefined = report.options_intelligence;
  const snap = getPriceSnapshot(report);
  const sessionPct = snap?.last_session_change_pct;

  if (!opts) {
    return <MinimalCard ticker={ticker} sessionPct={sessionPct} />;
  }

  const cs = opts.credit_safety;
  const er = opts.expected_range;
  const bwb = opts.reverse_bwb;

  return (
    <Card className="border-indigo-500/25 p-3 dark:border-indigo-400/25">
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-baseline gap-3">
          <div className="font-mono text-2xl font-bold tracking-tight">{ticker.toUpperCase()}</div>
          {typeof snap?.last_close === "number" && (
            <span className="font-mono text-sm text-slate-500">${snap.last_close.toFixed(2)}</span>
          )}
          {typeof sessionPct === "number" && (
            <Pill t={sessionPct >= 0 ? "ok" : "bad"}>
              {sessionPct >= 0 ? "+" : ""}{sessionPct.toFixed(2)}%
            </Pill>
          )}
        </div>

        <div className="ml-auto flex flex-wrap items-center gap-2">
          <MiniMetric
            label="Credit Safety"
            primary={
              <span className={summaryScoreColor(cs.score)}>{cs.score.toFixed(1)}<span className="text-xs text-slate-400">/10</span></span>
            }
            pill={<Pill t={tone(cs.label)}>{cs.label}</Pill>}
          />
          <MiniMetric
            label={`Expected Range ${opts.horizon_days}d`}
            primary={
              <span className="font-mono">
                {er.low.toFixed(2)}<span className="mx-1 text-slate-400">–</span>{er.high.toFixed(2)}
              </span>
            }
            hint={`σ ${er.sigma_pct.toFixed(2)}%`}
          />
          <MiniMetric
            label="Pin Risk"
            primary={<Pill t={tone(opts.pin_risk.label)}>{opts.pin_risk.label}</Pill>}
            hint={`near ${opts.pin_risk.nearest_round.toFixed(2)}`}
          />
          <MiniMetric
            label="Event Risk"
            primary={<Pill t={tone(opts.event_risk.label)}>{opts.event_risk.label}</Pill>}
            hint={(opts.event_risk.drivers ?? [])[0] ?? ""}
          />
        </div>
      </div>

      {bwb.score >= 6 && (
        <div className="mt-2 text-[11px] text-slate-600 dark:text-slate-300">
          <span className="font-semibold text-indigo-700 dark:text-indigo-300">Suggested Reverse-BWB </span>
          · score {bwb.score.toFixed(1)} · wings {bwb.suggested_wing_width_pct.toFixed(2)}% · DTE {bwb.suggested_dte} ·{" "}
          {bwb.rationale}
        </div>
      )}
    </Card>
  );
}
