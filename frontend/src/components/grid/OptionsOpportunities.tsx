/**
 * OptionsOpportunities — the additive Layer-1 card section that surfaces
 * the best CALL and PUT setups in two compact tables. Today it is fed
 * with mock data; the `OptionsData` shape below is the same contract the
 * IBKR Gateway integration will return, so no UI changes will be needed
 * once the real feed lands.
 *
 * Sized to fit inside the watchlist grid card's ~328px usable width with
 * no horizontal scroll — uses table-fixed columns and truncates the long
 * Combo strings on overflow.
 */

import { Chip, SectionFrame } from "@/components/grid/primitives";
import type { Tone } from "@/lib/deriveDecisionTone";

export type OptionLiquidity = "High" | "Medium" | "Low";

export type OptionRow = {
  combo: string;
  exp: string;
  premium: string;
  margin: string;
  liquidity: OptionLiquidity;
};

export type OptionsData = {
  calls: OptionRow[];
  puts: OptionRow[];
};

function liquidityTone(liquidity: OptionLiquidity): Tone {
  switch (liquidity) {
    case "High":
      return "ok";
    case "Medium":
      return "warn";
    case "Low":
      return "bad";
    default:
      return "neutral";
  }
}

function OptionsTable({ label, rows }: { label: string; rows: OptionRow[] }) {
  return (
    <div className="flex flex-col">
      <div className="bg-[hsl(var(--terminal-card-elevated))]/70 px-2 py-1 text-[9px] font-semibold uppercase tracking-wider text-[hsl(var(--terminal-text-secondary))]">
        {label}
      </div>
      <table className="w-full table-fixed border-collapse">
        <colgroup>
          <col style={{ width: "36%" }} />
          <col style={{ width: "12%" }} />
          <col style={{ width: "16%" }} />
          <col style={{ width: "18%" }} />
          <col style={{ width: "18%" }} />
        </colgroup>
        <thead>
          <tr className="bg-[hsl(var(--terminal-card-elevated))]/40 text-[9px] font-semibold uppercase tracking-wider text-[hsl(var(--terminal-text-tertiary))]">
            <th className="px-2 py-1 text-left">Combo</th>
            <th className="px-2 py-1 text-left">Exp</th>
            <th className="px-2 py-1 text-right">Premium</th>
            <th className="px-2 py-1 text-right">Margin</th>
            <th className="px-2 py-1 text-center">Liquidity</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td
                colSpan={5}
                className="px-2 py-2 text-center font-mono text-[10px] text-[hsl(var(--terminal-text-tertiary))]"
              >
                —
              </td>
            </tr>
          ) : (
            rows.map((row, idx) => (
              <tr
                key={`${row.combo}-${row.exp}-${idx}`}
                className="border-t border-[hsl(var(--terminal-border))]/60"
              >
                <td
                  className="truncate px-2 py-1 text-left font-mono text-[11px] tabular-nums text-slate-100"
                  title={row.combo}
                >
                  {row.combo}
                </td>
                <td className="px-2 py-1 text-left font-mono text-[11px] tabular-nums text-slate-200">
                  {row.exp}
                </td>
                <td className="px-2 py-1 text-right font-mono text-[11px] tabular-nums text-emerald-300">
                  {row.premium}
                </td>
                <td className="px-2 py-1 text-right font-mono text-[11px] tabular-nums text-slate-200">
                  {row.margin}
                </td>
                <td className="px-2 py-1 text-center">
                  <Chip tone={liquidityTone(row.liquidity)} className="text-[9px]">
                    {row.liquidity}
                  </Chip>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export function OptionsOpportunities({ data }: { data: OptionsData }) {
  const calls = data.calls.slice(0, 2);
  const puts = data.puts.slice(0, 2);
  return (
    <SectionFrame title="Options Opportunities">
      <div className="overflow-hidden rounded-md border border-[hsl(var(--terminal-border))] bg-[hsl(var(--terminal-card-elevated))]/50">
        <OptionsTable label="Call Opportunities" rows={calls} />
        <div className="border-t border-[hsl(var(--terminal-border))]" />
        <OptionsTable label="Put Opportunities" rows={puts} />
      </div>
    </SectionFrame>
  );
}
