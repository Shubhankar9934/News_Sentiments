import { Card } from "@/components/ui/card";
import type {
  DebateAssignment,
  DebateCritique,
  DeliberationLayer,
} from "@/types/schemas";
import { MODEL_LABELS, Pill, SectionTitle } from "./shared";

type Props = { layer: DeliberationLayer };

const ROLE_LABELS: Record<string, string> = {
  devils_advocate: "Devil's Advocate",
  assumption_auditor: "Assumption Auditor",
  default: "",
};

function CritiqueBlock({
  roundLabel,
  critique,
  assignment,
  novelty,
}: {
  roundLabel: string;
  critique: DebateCritique;
  assignment?: DebateAssignment;
  novelty?: { similarity: number; low_novelty: boolean };
}) {
  if (critique.error) return null;
  const rev = critique.confidence_revision;
  const targets = assignment?.targets ?? [];
  const role = assignment?.role ?? "default";
  const lowNovelty = Boolean(novelty?.low_novelty);
  const similarityPct =
    novelty && typeof novelty.similarity === "number"
      ? `${Math.round(novelty.similarity * 100)}%`
      : null;
  return (
    <div className="rounded-md border border-[hsl(var(--border))] p-3 text-sm">
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <span className="font-semibold">{MODEL_LABELS[critique.model] ?? critique.model}</span>
        <span className="text-xs text-slate-500">{roundLabel}</span>
        {rev && (
          <Pill tone={rev.new < rev.old ? "warn" : "ok"}>
            conf {Math.round(rev.old * 100)}% → {Math.round(rev.new * 100)}%
          </Pill>
        )}
        {role !== "default" && ROLE_LABELS[role] && (
          <Pill tone="warn">{ROLE_LABELS[role]}</Pill>
        )}
        {targets.length > 0 && (
          <Pill>
            → targets {targets.map((m) => MODEL_LABELS[m] ?? m).join(", ")}
          </Pill>
        )}
        {lowNovelty && (
          <Pill tone="warn">low novelty{similarityPct ? ` (sim ${similarityPct})` : ""}</Pill>
        )}
      </div>
      {(critique.agrees_with?.length ?? 0) > 0 && (
        <p className="text-xs text-emerald-700 dark:text-emerald-300">
          Agrees: {(critique.agrees_with ?? []).map((m) => MODEL_LABELS[m] ?? m).join(", ")}
        </p>
      )}
      {(critique.disagrees_with?.length ?? 0) > 0 && (
        <p className="text-xs text-rose-700 dark:text-rose-300">
          Disagrees: {(critique.disagrees_with ?? []).map((m) => MODEL_LABELS[m] ?? m).join(", ")}
        </p>
      )}
      {critique.strongest_counterargument && (
        <p className="mt-1 text-xs">
          <span className="font-medium">Counter: </span>
          {critique.strongest_counterargument}
        </p>
      )}
      {critique.weakest_reasoning_detected && (
        <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
          <span className="font-medium">Weak logic: </span>
          {critique.weakest_reasoning_detected}
        </p>
      )}
    </div>
  );
}

type NoveltyEntry = { model: string; similarity: number; low_novelty: boolean };

export function DebateTimeline({ layer }: Props) {
  const rounds = layer.debate_rounds ?? [];
  const assignments = layer.debate_assignments ?? [];
  const noveltyRaw =
    (layer.metrics as { round_novelty?: NoveltyEntry[] } | undefined)?.round_novelty ?? [];
  const noveltyByModel = new Map<string, NoveltyEntry>(
    noveltyRaw.map((n) => [n.model, n]),
  );

  function lookupAssignment(roundIndex: number, model: string): DebateAssignment | undefined {
    return assignments.find((a) => a.round === roundIndex + 1 && a.model === model);
  }

  return (
    <Card className="p-4">
      <SectionTitle title="Debate timeline" />
      <div className="space-y-3">
        {rounds.length === 0 && (
          <p className="text-sm text-slate-500">No debate rounds recorded.</p>
        )}
        {rounds.map((rd, idx) => {
          // Novelty is computed between round 1 (cross-critique) and round 2
          // (revision), so attach the score only to round-2 (idx === 1) cards.
          const isRevisionRound = idx === 1;
          return (
            <div key={idx} className="space-y-2">
              <p className="text-xs font-bold uppercase text-slate-500">Round {idx + 1}</p>
              {Object.values(rd).map((c) => (
                <CritiqueBlock
                  key={c.model}
                  roundLabel={`Debate ${idx + 1}`}
                  critique={c}
                  assignment={lookupAssignment(idx, c.model)}
                  novelty={isRevisionRound ? noveltyByModel.get(c.model) : undefined}
                />
              ))}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
