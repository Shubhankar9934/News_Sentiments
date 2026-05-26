import { Card } from "@/components/ui/card";
import type { DeliberationLayer } from "@/types/schemas";
import { Pill, SectionTitle } from "./shared";

const COUNCIL_LABELS: Record<string, string> = {
  portfolio_manager: "Portfolio Manager",
  risk_manager: "Risk Manager",
  market_strategist: "Market Strategist",
  quant_reviewer: "Quant Reviewer",
  contrarian_investor: "Contrarian Investor",
};

function decisionTone(d: string): "ok" | "warn" | "bad" | "neutral" {
  const u = d.toUpperCase();
  if (u === "ENTER") return "ok";
  if (u === "AVOID") return "bad";
  return "warn";
}

type Props = { layer: DeliberationLayer };

export function CouncilPanel({ layer }: Props) {
  const council = layer.council_layer as
    | {
        question?: string;
        trigger?: string;
        round1?: Record<
          string,
          {
            council_label?: string;
            decision?: string;
            confidence?: number;
            key_risks?: string[];
            model?: string;
          }
        >;
        round3?: Record<
          string,
          {
            prior_decision?: string;
            revised_decision?: string;
            revision_rationale?: string;
          }
        >;
        consensus?: {
          decision?: string;
          support?: Record<string, number>;
          confidence?: number;
          main_conflict?: string;
          debate_summary?: string;
        };
      }
    | undefined;

  if (!layer.council_triggered || !council?.consensus) return null;

  const consensus = council.consensus;
  const support = consensus.support ?? {};
  const total = Object.values(support).reduce((a, b) => a + b, 0);

  return (
    <Card className="p-4 space-y-4">
      <SectionTitle title="Decision council" />
      {council.question && (
        <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
          {council.question}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Pill tone={decisionTone(consensus.decision ?? "WAIT")}>
          {consensus.decision ?? "WAIT"}
        </Pill>
        {layer.mapped_decision && (
          <Pill tone="neutral">Dashboard: {layer.mapped_decision}</Pill>
        )}
        {consensus.confidence != null && (
          <Pill>{(consensus.confidence * 100).toFixed(0)}% confidence</Pill>
        )}
      </div>

      {consensus.main_conflict && (
        <p className="text-xs text-amber-700 dark:text-amber-200">
          Main conflict: {consensus.main_conflict}
        </p>
      )}

      {total > 0 && (
        <div className="space-y-1">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Vote support
          </p>
          {(["ENTER", "WAIT", "AVOID"] as const).map((d) => {
            const n = support[d] ?? 0;
            if (n === 0) return null;
            const pct = (n / total) * 100;
            return (
              <div key={d} className="flex items-center gap-2 text-xs">
                <span className="w-12 font-semibold">{d}</span>
                <div className="h-2 flex-1 rounded bg-slate-200 dark:bg-slate-700">
                  <div
                    className="h-2 rounded bg-slate-600 dark:bg-slate-400"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="w-8 text-right">{n}</span>
              </div>
            );
          })}
        </div>
      )}

      {council.round1 && (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(council.round1).map(([role, dec]) => {
            const rev = council.round3?.[role];
            const finalDecision = rev?.revised_decision ?? dec.decision ?? "WAIT";
            return (
              <div
                key={role}
                className="rounded border border-[hsl(var(--border))] p-2 text-xs"
              >
                <div className="font-semibold">
                  {dec.council_label ?? COUNCIL_LABELS[role] ?? role}
                </div>
                <div className="mt-1 flex flex-wrap gap-1">
                  <Pill tone={decisionTone(finalDecision)}>{finalDecision}</Pill>
                  {rev && rev.prior_decision !== rev.revised_decision && (
                    <Pill tone="warn">
                      {rev.prior_decision} → {rev.revised_decision}
                    </Pill>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {consensus.debate_summary && (
        <p className="text-xs text-slate-600 dark:text-slate-300">{consensus.debate_summary}</p>
      )}
    </Card>
  );
}
