/**
 * Section 2 of the strict 3-section ticker card — renders every field of the
 * server-side ReverseBwbSummary contract with no truncation or per-field
 * abbreviation. Tone is derived from the centralised palette in
 * ``deriveDecisionTone`` so chip colors stay consistent with the report
 * page.
 *
 * Label strings match the spec for the Assessment-Team owned card:
 *   {ticker} — Reverse BWB Credit View
 *   Today's outlook / Next 2–3 days outlook
 *   Chance of +2–3% move / Chance of -2–3% move
 *   Body / danger zone — Pin risk near body
 *   IV / premium quality — Liquidity / fills
 *   Actual dynamics summary
 */

import { MetricCell, SectionTitle } from "@/components/grid/primitives";
import {
  nextOutlookTone,
  qualityTone,
  todayOutlookTone,
  toneFor,
  toneForScore,
} from "@/lib/deriveDecisionTone";
import type { ReverseBwbSummary } from "@/types/schemas";

type Props = {
  summary: ReverseBwbSummary;
};

function formatRange(low: number, high: number): string {
  return `$${low.toFixed(2)} – $${high.toFixed(2)}`;
}

function formatScore(score: number): string {
  if (Number.isNaN(score)) return "—";
  return score.toFixed(1);
}

export function ReverseBwbCreditView({ summary }: Props) {
  return (
    <section className="flex flex-col gap-3" aria-label="Reverse BWB Credit View">
      <SectionTitle>{summary.ticker} — Reverse BWB Credit View</SectionTitle>

      <div className="grid grid-cols-2 gap-2">
        <MetricCell
          label="Decision"
          tone={toneFor(summary.decision)}
          emphasis
          value={summary.decision}
        />
        <MetricCell
          label="Credit safety"
          tone={toneForScore(summary.credit_safety_score)}
          emphasis
          value={`${formatScore(summary.credit_safety_score)} / 10`}
        />
        <MetricCell label="Risk" tone={toneFor(summary.risk)} value={summary.risk} />
        <MetricCell
          label="Confidence"
          tone={toneFor(summary.confidence)}
          value={summary.confidence}
        />
      </div>

      <div className="grid grid-cols-2 gap-2">
        <MetricCell
          label="Today's outlook"
          tone={todayOutlookTone(summary.today_outlook)}
          value={summary.today_outlook}
        />
        <MetricCell
          label="Next 2–3 days outlook"
          tone={nextOutlookTone(summary.next_3d_outlook)}
          value={summary.next_3d_outlook}
        />
        <MetricCell
          label="Chance of +2–3% move"
          tone={toneFor(summary.chance_up_2_3_pct)}
          value={summary.chance_up_2_3_pct}
        />
        <MetricCell
          label="Chance of -2–3% move"
          tone={toneFor(summary.chance_down_2_3_pct)}
          value={summary.chance_down_2_3_pct}
        />
      </div>

      <div className="grid grid-cols-1 gap-2">
        <MetricCell
          label="Expected range today"
          value={formatRange(
            summary.expected_range_today.low,
            summary.expected_range_today.high,
          )}
        />
        <MetricCell
          label="Expected range next 3 days"
          value={formatRange(
            summary.expected_range_next_3d.low,
            summary.expected_range_next_3d.high,
          )}
        />
      </div>

      <div className="grid grid-cols-2 gap-2">
        <MetricCell label="Body / danger zone" value={summary.danger_zone} />
        <MetricCell
          label="Pin risk near body"
          tone={toneFor(summary.pin_risk)}
          value={summary.pin_risk}
        />
        <MetricCell
          label="Event risk"
          tone={toneFor(summary.event_risk)}
          value={summary.event_risk}
        />
        <MetricCell
          label="IV / premium quality"
          tone={qualityTone(summary.iv_quality)}
          value={summary.iv_quality}
        />
        <MetricCell
          label="Liquidity / fills"
          tone={qualityTone(summary.liquidity)}
          value={summary.liquidity}
          className="col-span-2"
        />
      </div>

      <div className="flex flex-col gap-2">
        <SectionTitle>Actual dynamics summary</SectionTitle>
        <ul className="flex flex-col gap-1.5 rounded-md border border-[hsl(var(--terminal-border))] bg-[hsl(var(--terminal-card-elevated))]/60 px-3 py-2">
          {summary.actual_dynamics_summary.map((line, idx) => (
            <li
              key={idx}
              className="text-[12px] leading-snug text-[hsl(var(--terminal-text-primary))]"
            >
              {line}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
