import type { Explainability } from "@/types/schemas";
import { ExplainCard } from "./shared";

type PositionRisk = NonNullable<Explainability["position_risk"]>;

function pct(x: number) {
  return `${(x * 100).toFixed(1)}%`;
}

export function PositionRiskPanel({ data }: { data: PositionRisk }) {
  return (
    <ExplainCard
      title="Trade Risk Analysis"
      subtitle={`Method: ${data.method ?? "lognormal_closed_form"}`}
    >
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <MetricBox label="Probability of Profit" value={pct(data.probability_of_profit)} tone="ok" />
        <MetricBox label="Probability of Touch" value={pct(data.probability_of_touch)} tone="warn" />
        <MetricBox
          label="Probability of Breakeven"
          value={pct(data.probability_of_breakeven)}
          tone="neutral"
        />
        <MetricBox
          label="Probability of Max Loss"
          value={pct(data.probability_of_max_loss)}
          tone="bad"
        />
        <MetricBox
          label="Expected Value (per contract)"
          value={`$${data.expected_value_usd.toFixed(2)}`}
          tone={data.expected_value_usd >= 0 ? "ok" : "bad"}
        />
      </div>
      {data.assumptions && data.assumptions.length > 0 && (
        <ul className="ml-4 list-disc text-xs text-slate-500 dark:text-slate-400">
          {data.assumptions.map((line, idx) => (
            <li key={idx}>{line}</li>
          ))}
        </ul>
      )}
    </ExplainCard>
  );
}

function MetricBox({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "ok" | "warn" | "bad" | "neutral";
}) {
  const cls =
    tone === "ok"
      ? "border-emerald-500/30 bg-emerald-500/10"
      : tone === "warn"
        ? "border-amber-500/30 bg-amber-500/10"
        : tone === "bad"
          ? "border-rose-500/30 bg-rose-500/10"
          : "border-[hsl(var(--border))] bg-[hsl(var(--muted))]";
  return (
    <div className={`flex flex-col gap-0.5 rounded-md border p-2 ${cls}`}>
      <span className="text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400">
        {label}
      </span>
      <span className="text-base font-semibold text-slate-800 dark:text-slate-100">
        {value}
      </span>
    </div>
  );
}
