import type { Explainability } from "@/types/schemas";
import { ExplainCard, ExplainRow } from "./shared";

type Breakdown = NonNullable<Explainability["credit_safety_breakdown"]>;

export function CreditSafetyBreakdownPanel({ data }: { data: Breakdown }) {
  return (
    <ExplainCard
      title="Credit Safety Breakdown"
      subtitle={`Why Credit Safety = ${data.final_credit_safety.toFixed(2)} / 10`}
    >
      <ExplainRow
        label={data.move_stability.label}
        detail={data.move_stability.explanation}
        value={
          data.move_stability.value !== null && data.move_stability.value !== undefined
            ? `${data.move_stability.value.toFixed(2)} / 10`
            : null
        }
        tone="neutral"
      />
      {(
        [
          "pin_risk_impact",
          "event_risk_impact",
          "volatility_impact",
          "structure_placement_impact",
          "liquidity_impact",
        ] as const
      ).map((key) => {
        const row = data[key];
        return (
          <ExplainRow
            key={key}
            label={row.label}
            detail={row.explanation}
            delta={row.delta ?? undefined}
          />
        );
      })}
      <div className="flex items-center justify-between border-t border-[hsl(var(--border))] pt-2">
        <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">
          Final Credit Safety
        </span>
        <span className="text-lg font-bold text-indigo-600 dark:text-indigo-300">
          {data.final_credit_safety.toFixed(2)} / 10
        </span>
      </div>
    </ExplainCard>
  );
}
