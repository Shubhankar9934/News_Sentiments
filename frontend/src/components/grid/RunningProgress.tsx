/**
 * Replaces the executive-summary block while a card is RUNNING. Visualises
 * the multi-LLM debate progress derived from the polled `deliberation_layer`:
 *
 *   - models_requested vs round1 keys → tick or "Running"
 *   - debate_rounds.length            → "Debating…"
 *   - consensus presence              → "Consensus building" → "Done"
 */

import { Check, Loader2, Pause } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DeliberationLayer } from "@/types/schemas";

type ModelStatus = "complete" | "running" | "waiting";

function deskStatuses(
  layer: DeliberationLayer | null | undefined,
  requested: string[],
): { model: string; label: string; status: ModelStatus }[] {
  const round1 = layer?.round1 ?? {};
  const finalRound =
    Array.isArray(layer?.debate_rounds) && layer.debate_rounds.length
      ? layer.debate_rounds[layer.debate_rounds.length - 1]
      : undefined;

  let firstMissingMarked = false;
  return requested.map((key) => {
    const label = key.replace(/_desk$/, "").replace(/_/g, " ");
    const inRound1 = key in round1;
    const inFinalRound = finalRound ? key in finalRound : false;
    const status: ModelStatus = inFinalRound
      ? "complete"
      : inRound1
        ? layer?.consensus
          ? "complete"
          : "running"
        : firstMissingMarked
          ? "waiting"
          : ((firstMissingMarked = true), "running");
    return { model: key, label, status };
  });
}

const FALLBACK_REQUESTED = ["gpt", "claude", "gemini", "deepseek", "groq"];

type Props = {
  layer: DeliberationLayer | null | undefined;
  fallbackMessage?: string;
};

export function RunningProgress({ layer, fallbackMessage }: Props) {
  const requested =
    layer?.desks_requested?.length
      ? layer.desks_requested
      : layer?.models_requested?.length
        ? layer.models_requested
        : FALLBACK_REQUESTED;
  const rows = deskStatuses(layer, requested);
  const consensusReady = Boolean(layer?.consensus);
  const debating =
    layer?.status === "running" &&
    Array.isArray(layer?.debate_rounds) &&
    layer.debate_rounds.length > 0 &&
    !consensusReady;

  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <div className="grid-card-section-title">Generating DIL Report</div>
        <span className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-amber-200">
          <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
          {layer?.status ?? "running"}
        </span>
      </div>
      <div className="rounded-md border border-[hsl(var(--terminal-border))] bg-[hsl(var(--terminal-card-elevated))]/50 p-3">
        <ul className="flex flex-col gap-1.5">
          {rows.map((row) => (
            <li
              key={row.model}
              className="flex items-center justify-between gap-2 font-mono text-[12px]"
            >
              <span className="font-semibold text-slate-200">{row.label}</span>
              <span
                className={cn(
                  "inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider",
                  row.status === "complete"
                    ? "text-emerald-300"
                    : row.status === "running"
                      ? "text-amber-200"
                      : "text-slate-500",
                )}
              >
                {row.status === "complete" ? (
                  <Check className="h-3 w-3" aria-hidden="true" />
                ) : row.status === "running" ? (
                  <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
                ) : (
                  <Pause className="h-3 w-3" aria-hidden="true" />
                )}
                {row.status === "complete" ? "Done" : row.status === "running" ? "Running" : "Waiting"}
              </span>
            </li>
          ))}
        </ul>
        <div className="mt-3 border-t border-[hsl(var(--terminal-border))] pt-2 text-[11px] font-medium text-slate-300">
          {consensusReady ? (
            <span className="inline-flex items-center gap-1.5 text-emerald-300">
              <Check className="h-3 w-3" aria-hidden="true" />
              Consensus reached — refreshing card…
            </span>
          ) : debating ? (
            <span className="inline-flex items-center gap-1.5 text-amber-200">
              <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
              Cross-critique round in progress…
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 text-slate-300">
              <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
              {fallbackMessage ?? "Round-1 independent opinions in flight…"}
            </span>
          )}
        </div>
      </div>
    </section>
  );
}
