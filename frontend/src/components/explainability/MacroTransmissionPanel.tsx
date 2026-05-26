import type { Explainability } from "@/types/schemas";
import { ExplainCard } from "./shared";

type Transmission = NonNullable<Explainability["macro_transmission"]>;

function arrow(direction: string | null | undefined) {
  switch ((direction ?? "").toLowerCase()) {
    case "up":
      return "↑";
    case "down":
      return "↓";
    case "flat":
      return "→";
    case "mixed":
      return "↔";
    default:
      return "·";
  }
}

function directionColor(direction: string | null | undefined) {
  switch ((direction ?? "").toLowerCase()) {
    case "up":
      return "text-emerald-700 dark:text-emerald-300";
    case "down":
      return "text-rose-700 dark:text-rose-300";
    case "mixed":
      return "text-amber-700 dark:text-amber-300";
    default:
      return "text-slate-600 dark:text-slate-300";
  }
}

export function MacroTransmissionPanel({ data }: { data: Transmission }) {
  if (!data.chain || data.chain.length === 0) return null;
  return (
    <ExplainCard
      title="Macro Transmission"
      subtitle={
        data.primary_shock
          ? `Shock: ${data.primary_shock.replace(/_/g, " ")}`
          : undefined
      }
    >
      <ol className="flex flex-col gap-1.5">
        {data.chain.map((node, idx) => (
          <li
            key={`${node.node}-${idx}`}
            className="flex items-baseline gap-2 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--muted))] px-3 py-1.5"
          >
            <span className={`text-base font-bold ${directionColor(node.direction)}`}>
              {arrow(node.direction)}
            </span>
            <div className="flex flex-col">
              <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                {node.label}
              </span>
              {node.evidence && (
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  {node.evidence}
                </span>
              )}
            </div>
          </li>
        ))}
      </ol>
      {data.narrative && (
        <p className="rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--muted))] px-3 py-2 text-sm text-slate-700 dark:text-slate-200">
          {data.narrative}
        </p>
      )}
    </ExplainCard>
  );
}
