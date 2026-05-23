import { Card } from "@/components/ui/card";
import type { DeliberationLayer } from "@/types/schemas";
import { MODEL_LABELS, SectionTitle } from "./shared";

type Props = { layer: DeliberationLayer };

export function ReasoningTree({ layer }: Props) {
  const round1 = layer.round1 ?? {};

  return (
    <Card className="p-4">
      <SectionTitle title="Reasoning trees" />
      <div className="space-y-4">
        {Object.entries(round1).map(([key, op]) => {
          if (op.error) return null;
          const steps = op.reasoning_steps ?? [];
          return (
            <div key={key}>
              <p className="mb-2 text-sm font-semibold">{MODEL_LABELS[key] ?? key}</p>
              <ol className="space-y-2 border-l-2 border-[hsl(var(--border))] pl-4">
                {steps.map((s) => (
                  <li key={s.step} className="text-sm">
                    <span className="font-medium text-slate-700 dark:text-slate-200">
                      {s.step}. {s.title}
                    </span>
                    <p className="mt-0.5 text-xs text-slate-600 dark:text-slate-400">{s.analysis}</p>
                  </li>
                ))}
              </ol>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
