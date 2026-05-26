import type { Explainability } from "@/types/schemas";
import { ExplainCard, ExplainRow, gradeTone } from "./shared";

type Liquidity = NonNullable<Explainability["liquidity_assessment"]>;

export function LiquidityAssessmentPanel({ data }: { data: Liquidity }) {
  return (
    <ExplainCard
      title="Liquidity Assessment"
      subtitle="3-axis decomposition behind the card's liquidity grade"
    >
      <ExplainRow
        label="Underlying Liquidity"
        detail={data.underlying_liquidity.detail ?? undefined}
        value={data.underlying_liquidity.grade}
        tone={gradeTone(data.underlying_liquidity.grade)}
      />
      <ExplainRow
        label="Options Liquidity"
        detail={data.options_liquidity.detail ?? undefined}
        value={data.options_liquidity.grade}
        tone={gradeTone(data.options_liquidity.grade)}
      />
      <ExplainRow
        label="Execution Quality"
        detail={data.execution_quality.detail ?? undefined}
        value={data.execution_quality.grade}
        tone={gradeTone(data.execution_quality.grade)}
      />
      <p className="rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--muted))] px-3 py-2 text-sm text-slate-700 dark:text-slate-200">
        {data.reason}
      </p>
    </ExplainCard>
  );
}
