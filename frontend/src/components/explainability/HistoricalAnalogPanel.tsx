import type { Explainability } from "@/types/schemas";
import { ExplainCard } from "./shared";

type Analogs = NonNullable<Explainability["historical_analogs"]>;

function pctOrDash(value: number | null | undefined, suffix = "%") {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(1)}${suffix}`;
}

export function HistoricalAnalogPanel({ data }: { data: Analogs }) {
  const agg = data.aggregates;
  return (
    <ExplainCard
      title="Historical Analog Engine"
      subtitle={`${agg.n_setups} similar setups projected forward`}
    >
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <Stat
          label="Win Rate"
          value={agg.win_rate !== undefined && agg.win_rate !== null ? `${(agg.win_rate * 100).toFixed(1)}%` : "—"}
        />
        <Stat
          label="Avg Credit Retained"
          value={pctOrDash(agg.avg_credit_retained)}
        />
        <Stat
          label="Max Loss Frequency"
          value={
            agg.max_loss_frequency !== undefined && agg.max_loss_frequency !== null
              ? `${(agg.max_loss_frequency * 100).toFixed(1)}%`
              : "—"
          }
        />
        <Stat
          label="Avg Forward Return"
          value={pctOrDash(agg.avg_forward_return_pct)}
        />
        <Stat
          label="P(touch body)"
          value={
            agg.p_touch_body !== undefined && agg.p_touch_body !== null
              ? `${(agg.p_touch_body * 100).toFixed(1)}%`
              : "—"
          }
        />
      </div>
      {data.sample_size_warning && (
        <p className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-900 dark:text-amber-100">
          {data.sample_size_warning}
        </p>
      )}
      {data.matches.length > 0 && (
        <ol className="flex flex-col gap-1.5">
          {data.matches.slice(0, 6).map((m, idx) => (
            <li
              key={idx}
              className="flex flex-col gap-0.5 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--muted))] px-3 py-1.5"
            >
              <span className="text-sm font-medium text-slate-700 dark:text-slate-200">
                {m.headline ?? "Untitled match"}
              </span>
              <span className="text-xs text-slate-500 dark:text-slate-400">
                {m.published_at ?? "Unknown date"}
                {m.match_reason ? ` · ${m.match_reason}` : ""}
                {m.forward_return_pct !== undefined && m.forward_return_pct !== null
                  ? ` · forward ${m.forward_return_pct.toFixed(2)}%`
                  : ""}
                {m.credit_retained_pct !== undefined && m.credit_retained_pct !== null
                  ? ` · credit ${m.credit_retained_pct.toFixed(0)}%`
                  : ""}
              </span>
            </li>
          ))}
        </ol>
      )}
    </ExplainCard>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--muted))] p-2">
      <span className="text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400">
        {label}
      </span>
      <span className="text-base font-semibold text-slate-800 dark:text-slate-100">
        {value}
      </span>
    </div>
  );
}
