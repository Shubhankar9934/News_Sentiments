import { Card } from "@/components/ui/card";
import type { DeliberationLayer } from "@/types/schemas";
import { Pill, SectionTitle, stanceTone } from "./shared";

type Props = { layer: DeliberationLayer };

export function ConsensusPanel({ layer }: Props) {
  const c = layer.consensus;
  if (!c) {
    return (
      <Card className="p-4">
        <SectionTitle title="Consensus synthesizer" />
        <p className="text-sm text-slate-500">Consensus pending.</p>
      </Card>
    );
  }

  const uncTone = c.uncertainty === "high" ? "bad" : c.uncertainty === "medium" ? "warn" : "ok";

  return (
    <Card className="p-4">
      <SectionTitle title="Consensus synthesizer" />
      <div className="mb-3 flex flex-wrap gap-2">
        <Pill tone={stanceTone(c.consensus)}>{c.consensus}</Pill>
        <Pill>Agreement {(c.agreement_score * 100).toFixed(0)}%</Pill>
        <Pill tone={uncTone}>Uncertainty: {c.uncertainty}</Pill>
      </div>
      {c.dominant_thesis && (
        <p className="mb-2 text-sm">
          <span className="font-semibold">Dominant thesis: </span>
          {c.dominant_thesis}
        </p>
      )}
      {c.conflicting_thesis && (
        <p className="mb-2 text-sm text-amber-800 dark:text-amber-200">
          <span className="font-semibold">Conflicting: </span>
          {c.conflicting_thesis}
        </p>
      )}
      {c.recommended_positioning && (
        <p className="mb-2 text-sm">
          <span className="font-semibold">Positioning: </span>
          {c.recommended_positioning}
        </p>
      )}
      {(c.main_conflicts?.length ?? 0) > 0 && (
        <ul className="mt-2 list-inside list-disc text-xs text-slate-600 dark:text-slate-400">
          {c.main_conflicts!.map((x, i) => (
            <li key={i}>{x}</li>
          ))}
        </ul>
      )}
      {c.debate_summary && (
        <p className="mt-3 text-xs text-slate-500 italic">{c.debate_summary}</p>
      )}
    </Card>
  );
}
