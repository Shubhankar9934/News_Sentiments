import { Card } from "@/components/ui/card";
import type { DeliberationLayer } from "@/types/schemas";
import { MODEL_LABELS, Pill, SectionTitle, stanceTone } from "./shared";

type Props = { layer: DeliberationLayer };

export function ModelOpinionCards({ layer }: Props) {
  const round1 = layer.round1 ?? {};
  const entries = Object.entries(round1).filter(([, op]) => !op.error);

  return (
    <Card className="p-4">
      <SectionTitle title="Individual model views" />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {entries.map(([key, op]) => {
          const riskN = (op.key_risks?.length ?? 0) + (op.hidden_assumptions?.length ?? 0);
          const riskLevel = riskN >= 6 ? "High" : riskN >= 3 ? "Medium" : "Low";
          return (
            <div
              key={key}
              className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--muted))]/40 p-3"
            >
              <div className="mb-2 text-sm font-bold">{MODEL_LABELS[key] ?? key}</div>
              <div className="flex flex-wrap gap-1.5">
                <Pill tone={stanceTone(op.stance)}>{op.stance}</Pill>
                <Pill>{(op.confidence * 100).toFixed(0)}% conf</Pill>
                <Pill tone={riskLevel === "High" ? "bad" : riskLevel === "Medium" ? "warn" : "ok"}>
                  {riskLevel} risk
                </Pill>
              </div>
              {op.time_horizon && (
                <p className="mt-2 text-xs text-slate-500">Horizon: {op.time_horizon}</p>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
