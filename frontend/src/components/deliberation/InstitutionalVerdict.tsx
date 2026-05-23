import { Card } from "@/components/ui/card";
import type { DeliberationLayer } from "@/types/schemas";
import { Pill, SectionTitle, stanceTone } from "./shared";

type Props = { layer: DeliberationLayer };

function pct(x: number | undefined): string {
  if (typeof x !== "number" || Number.isNaN(x)) return "—";
  return `${Math.round(x * 100)}%`;
}

export function InstitutionalVerdict({ layer }: Props) {
  const c = layer.consensus;
  const metrics = layer.metrics;

  if (!c) {
    return (
      <Card className="p-4 border-2 border-[hsl(var(--border))]">
        <SectionTitle title="Institutional verdict" />
        <p className="text-sm text-slate-500">Awaiting deliberation completion.</p>
      </Card>
    );
  }

  const riskN = c.hidden_risks?.length ?? 0;
  const riskLevel = riskN >= 8 ? "High" : riskN >= 4 ? "Medium" : "Low";
  const riskTone = riskLevel === "High" ? "bad" : riskLevel === "Medium" ? "warn" : "ok";

  // PR1 fix: prefer the reconciled label and structured calibration block when
  // present. The 86%-style "confidence" pill was previously rendering the
  // agreement_score — a directional-spread metric, not consensus confidence.
  const displayedLabel = c.reconciled_label || c.consensus;
  const cal = c.calibration;
  const uncertainty = cal?.uncertainty ?? c.uncertainty;
  const uncertaintyTone =
    uncertainty === "high" ? "bad" : uncertainty === "medium" ? "warn" : "ok";

  return (
    <Card className="p-4 border-2 border-indigo-500/20 bg-indigo-500/5">
      <SectionTitle title="Institutional verdict" />
      <div className="mb-4 flex flex-wrap gap-2">
        <Pill tone={stanceTone(displayedLabel)}>Bias: {displayedLabel}</Pill>
        {cal ? (
          <>
            <Pill>Directional conviction {pct(cal.directional_conviction)}</Pill>
            <Pill>Consensus strength {pct(cal.consensus_strength)}</Pill>
            <Pill>Confidence {pct(cal.confidence_aggregate)}</Pill>
          </>
        ) : (
          // Legacy back-compat: older reports have no calibration block.
          <Pill>Agreement {pct(c.agreement_score)}</Pill>
        )}
        <Pill tone={uncertaintyTone}>{uncertainty} uncertainty</Pill>
        <Pill tone={riskTone}>{riskLevel} risk</Pill>
      </div>
      <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-200">
        {c.recommended_positioning}
      </p>
      <p className="mt-3 text-xs text-slate-600 dark:text-slate-400">
        <span className="font-semibold">Why disagreement matters: </span>
        Model divergence {metrics?.model_divergence?.toFixed(2) ?? "—"} with contradiction
        density {metrics?.contradiction_density?.toFixed(2) ?? "—"}. Institutional edge comes
        from mapping where models refuse to converge — not from majority vote.
      </p>
    </Card>
  );
}
