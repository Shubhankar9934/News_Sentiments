import type { Explainability } from "@/types/schemas";
import { ExplainCard } from "./shared";
import { Pill } from "@/components/deliberation/shared";

type Justification = NonNullable<Explainability["decision_justification"]>;

function decisionTone(decision: string): "ok" | "warn" | "bad" | "neutral" {
  const d = decision.toUpperCase();
  if (d === "ENTER") return "ok";
  if (d === "WAIT") return "warn";
  if (d === "AVOID") return "bad";
  return "neutral";
}

export function DecisionJustificationPanel({ data }: { data: Justification }) {
  return (
    <ExplainCard
      title="Decision Justification"
      subtitle={`Why the verdict = ${data.consensus_decision.toUpperCase()}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone={decisionTone(data.consensus_decision)}>
          Consensus: {data.consensus_decision.toUpperCase()}
        </Pill>
        {data.consensus_confidence !== null && data.consensus_confidence !== undefined && (
          <Pill tone="neutral">
            Confidence {(data.consensus_confidence * 100).toFixed(0)}%
          </Pill>
        )}
        {Object.entries(data.support_counts).map(([decision, count]) => (
          <Pill key={decision} tone={decisionTone(decision)}>
            {decision}: {count}
          </Pill>
        ))}
      </div>

      {data.council_votes.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400">
                <th className="py-1">Member</th>
                <th className="py-1">Decision</th>
                <th className="py-1">Conf.</th>
                <th className="py-1">Top Reason</th>
              </tr>
            </thead>
            <tbody>
              {data.council_votes.map((vote, idx) => (
                <tr key={idx} className="border-t border-[hsl(var(--border))]">
                  <td className="py-1 pr-2 font-medium text-slate-700 dark:text-slate-200">
                    {vote.label}
                  </td>
                  <td className="py-1 pr-2">
                    <Pill tone={decisionTone(vote.decision)}>{vote.decision}</Pill>
                  </td>
                  <td className="py-1 pr-2 text-slate-600 dark:text-slate-300">
                    {vote.confidence !== null && vote.confidence !== undefined
                      ? `${(vote.confidence * 100).toFixed(0)}%`
                      : "—"}
                  </td>
                  <td className="py-1 text-slate-600 dark:text-slate-300">
                    {vote.top_reason ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data.primary_reasons.length > 0 && (
        <div>
          <div className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
            Primary reasons
          </div>
          <ul className="ml-4 mt-1 list-disc text-sm text-slate-700 dark:text-slate-200">
            {data.primary_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      )}

      {data.dissent.length > 0 && (
        <div className="rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--muted))] px-3 py-2">
          <div className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
            Dissent
          </div>
          <ul className="ml-4 mt-1 list-disc text-sm text-slate-700 dark:text-slate-200">
            {data.dissent.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        </div>
      )}

      {data.main_conflict && (
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Main conflict: {data.main_conflict}
        </p>
      )}
    </ExplainCard>
  );
}
