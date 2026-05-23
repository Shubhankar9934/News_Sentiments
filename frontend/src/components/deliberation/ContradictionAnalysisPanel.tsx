import { Card } from "@/components/ui/card";
import type { DeliberationLayer } from "@/types/schemas";
import { MODEL_LABELS, Pill, SectionTitle, stanceTone } from "./shared";

type Props = { layer: DeliberationLayer };

type Contradiction = {
  type: string;
  topic?: string;
  model_a: string;
  model_b?: string;
  stance_a?: string;
  stance_b?: string;
  severity?: string;
  note?: string;
  evidence_refs?: string[];
};

const TYPE_LABELS: Record<string, string> = {
  pair_topic: "Pairwise stance opposition",
  stance_vs_evidence: "Stance vs. evidence mismatch",
  confidence_vs_reasoning: "Confidence vs. reasoning mismatch",
};

function severityTone(s: string | undefined): "ok" | "warn" | "bad" | "neutral" {
  if (s === "high") return "bad";
  if (s === "medium") return "warn";
  return "neutral";
}

export function ContradictionAnalysisPanel({ layer }: Props) {
  const contradictions =
    (layer.metrics as { contradictions?: Contradiction[] } | undefined)?.contradictions ?? [];
  if (contradictions.length === 0) return null;

  return (
    <Card className="p-4">
      <SectionTitle title="Contradiction analysis">
        <span className="text-[11px] text-slate-500">{contradictions.length} detected</span>
      </SectionTitle>
      <ul className="space-y-2 text-sm">
        {contradictions.map((c, idx) => {
          const a = MODEL_LABELS[c.model_a] ?? c.model_a;
          const b = c.model_b ? (MODEL_LABELS[c.model_b] ?? c.model_b) : null;
          return (
            <li
              key={idx}
              className="rounded border border-[hsl(var(--border))] p-3"
            >
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <Pill tone={severityTone(c.severity)}>{c.severity ?? "—"}</Pill>
                <span className="text-xs font-semibold text-slate-700 dark:text-slate-200">
                  {TYPE_LABELS[c.type] ?? c.type}
                </span>
                {c.topic && <Pill>{c.topic}</Pill>}
              </div>
              {c.type === "pair_topic" && b ? (
                <p className="text-xs">
                  <span className="font-medium">{a}</span>{" "}
                  <Pill tone={stanceTone(c.stance_a ?? "")}>{c.stance_a}</Pill>{" "}
                  <span className="text-slate-500">vs</span>{" "}
                  <span className="font-medium">{b}</span>{" "}
                  <Pill tone={stanceTone(c.stance_b ?? "")}>{c.stance_b}</Pill>
                </p>
              ) : (
                <p className="text-xs">
                  <span className="font-medium">{a}</span>
                  {c.stance_a ? (
                    <>
                      {" — "}
                      <Pill tone={stanceTone(c.stance_a)}>{c.stance_a}</Pill>
                    </>
                  ) : null}
                </p>
              )}
              {c.note && (
                <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">{c.note}</p>
              )}
              {c.evidence_refs && c.evidence_refs.length > 0 && (
                <p className="mt-1 text-[11px] text-slate-500">
                  Evidence topics: {c.evidence_refs.join(", ")}
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
