import type { Explainability } from "@/types/schemas";
import { ExplainCard } from "./shared";

type Structure = NonNullable<Explainability["structure_analysis"]>;

function fmt(value: number, digits = 2) {
  return Number.isFinite(value) ? value.toFixed(digits) : "—";
}

export function StructureAnalysisPanel({ data }: { data: Structure }) {
  const g = data.geometry;
  return (
    <ExplainCard
      title="Reverse BWB Structure Analysis"
      subtitle="Deterministic geometry + Structure Desk verdict"
    >
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
        <Metric label="Distance To Body" value={`${fmt(g.distance_to_body_pct)}% (${fmt(g.distance_to_body_sigma)}σ)`} />
        <Metric label="Body Exposure" value={`${fmt(g.body_exposure_pct, 1)}%`} />
        <Metric label="Wing Protection" value={`${fmt(g.wing_protection_ratio)}×`} />
        <Metric label="Credit Efficiency" value={fmt(g.credit_efficiency, 3)} />
        <Metric label="Risk / Reward" value={fmt(g.risk_reward, 3)} />
        <Metric label="DTE" value={`${g.dte}d`} />
        <Metric label="Spot" value={`$${fmt(g.spot)}`} />
        <Metric label="Body Strike" value={`$${fmt(g.body_strike)}`} />
        <Metric label="Wing Width" value={`${fmt(g.wing_width_pct)}% ($${fmt(g.wing_width_dollars)})`} />
        <Metric label="Credit" value={`$${fmt(g.credit)}`} />
        <Metric label="Max Loss" value={`$${fmt(g.max_loss)}`} />
        <Metric
          label="Breakevens"
          value={`$${fmt(g.lower_breakeven)} / $${fmt(g.upper_breakeven)}`}
        />
      </div>
      {data.desk_narrative && (
        <div className="rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--muted))] p-3">
          <div className="mb-1 text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400">
            Structure Desk
            {data.desk_model && (
              <span className="ml-1 normal-case text-slate-400">· {data.desk_model}</span>
            )}
          </div>
          <p className="text-sm text-slate-700 dark:text-slate-200">
            {data.desk_narrative}
          </p>
        </div>
      )}
    </ExplainCard>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400">
        {label}
      </span>
      <span className="text-sm font-medium text-slate-700 dark:text-slate-200">
        {value}
      </span>
    </div>
  );
}
