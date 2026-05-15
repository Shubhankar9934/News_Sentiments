import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ResearchReport } from "@/types/schemas";

function chartPalette(isDark: boolean) {
  return {
    grid: isDark ? "hsl(217 19% 27%)" : "hsl(214 32% 91%)",
    tick: isDark ? "hsl(215 16% 65%)" : "hsl(215 16% 40%)",
    tooltipBg: isDark ? "hsl(222 47% 11%)" : "hsl(0 0% 100%)",
    tooltipBorder: isDark ? "hsl(217 19% 27%)" : "hsl(214 32% 91%)",
  };
}

function sentimentColor(label: string): string {
  const l = label.toLowerCase();
  if (l.includes("bull")) return "#22c55e";
  if (l.includes("bear")) return "#ef4444";
  if (l.includes("mix")) return "#eab308";
  return "#94a3b8";
}

function pieData(report: ResearchReport): { name: string; value: number; fill: string }[] {
  const raw = report.sentiment_breakdown;
  if (raw && raw.length > 0) {
    return raw.map((s) => ({
      name: s.label,
      value: s.count,
      fill: sentimentColor(s.label),
    }));
  }
  const arts = report.articles;
  if (!arts?.length) return [];
  const counts = new Map<string, number>();
  for (const a of arts) {
    const lab = a.sentiment_label?.trim() || "Neutral";
    counts.set(lab, (counts.get(lab) ?? 0) + 1);
  }
  return Array.from(counts.entries()).map(([name, value]) => ({
    name,
    value,
    fill: sentimentColor(name),
  }));
}

function eventsData(report: ResearchReport, limit = 10) {
  const ev = report.key_events;
  if (!ev?.length) return [];
  return ev
    .map((e, i) => ({
      name: (e.description || e.type || `Event ${i + 1}`).slice(0, 56),
      impact: typeof e.impact_score === "number" ? e.impact_score : 0,
    }))
    .sort((a, b) => b.impact - a.impact)
    .slice(0, limit);
}

function sourcesData(report: ResearchReport, limit = 12) {
  const sr = report.source_reliability;
  if (sr?.length) {
    return [...sr]
      .sort((a, b) => (b.articles ?? 0) - (a.articles ?? 0))
      .slice(0, limit)
      .map((s) => ({ name: s.source.slice(0, 24), articles: s.articles ?? 0 }));
  }
  const arts = report.articles;
  if (!arts?.length) return [];
  const m = new Map<string, number>();
  for (const a of arts) {
    const src = a.source?.trim() || "Unknown";
    m.set(src, (m.get(src) ?? 0) + 1);
  }
  return Array.from(m.entries())
    .map(([name, articles]) => ({ name: name.slice(0, 24), articles }))
    .sort((a, b) => b.articles - a.articles)
    .slice(0, limit);
}

function dailyArticleCounts(report: ResearchReport) {
  const arts = report.articles;
  if (!arts?.length) return [];
  const map = new Map<string, number>();
  for (const a of arts) {
    const p = a.published_at;
    if (!p) continue;
    const d = new Date(p);
    if (Number.isNaN(d.getTime())) continue;
    const key = d.toISOString().slice(0, 10);
    map.set(key, (map.get(key) ?? 0) + 1);
  }
  return Array.from(map.entries())
    .map(([date, count]) => ({ date, count }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

function priceBands(report: ResearchReport) {
  const p = report.price_prediction;
  if (!p) return null;
  const { low, base, high } = p;
  if (
    typeof low !== "number" ||
    typeof base !== "number" ||
    typeof high !== "number"
  ) {
    return null;
  }
  return [
    { band: "Low", value: low },
    { band: "Base", value: base },
    { band: "High", value: high },
  ];
}

type Props = { report: ResearchReport; isDark: boolean };

export function ResearchReportCharts({ report, isDark }: Props) {
  const c = chartPalette(isDark);

  const sentiment = useMemo(() => pieData(report), [report]);
  const events = useMemo(() => eventsData(report), [report]);
  const sources = useMemo(() => sourcesData(report), [report]);
  const timeline = useMemo(() => dailyArticleCounts(report), [report]);
  const priceBars = useMemo(() => priceBands(report), [report]);

  const tooltipStyle = {
    backgroundColor: c.tooltipBg,
    border: `1px solid ${c.tooltipBorder}`,
    borderRadius: 8,
    fontSize: 12,
  };

  const empty = (
    <p className="text-center text-xs text-slate-500 dark:text-slate-400">No data for this chart.</p>
  );

  return (
    <div className="mt-4 grid gap-6 lg:grid-cols-2">
      <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-3">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
          Sentiment mix
        </div>
        {sentiment.length === 0 ? (
          empty
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={sentiment}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius={52}
                outerRadius={88}
                paddingAngle={2}
              >
                {sentiment.map((entry, index) => (
                  <Cell key={`cell-${entry.name}-${index}`} fill={entry.fill} />
                ))}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-3">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
          Articles per day
        </div>
        {timeline.length === 0 ? (
          empty
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={timeline} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
              <XAxis dataKey="date" tick={{ fill: c.tick, fontSize: 10 }} tickMargin={6} />
              <YAxis allowDecimals={false} tick={{ fill: c.tick, fontSize: 11 }} width={36} />
              <Tooltip contentStyle={tooltipStyle} />
              <Line type="monotone" dataKey="count" name="Articles" stroke="#6366f1" strokeWidth={2} dot r={3} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-3 lg:col-span-2">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
          Key events by impact score
        </div>
        {events.length === 0 ? (
          empty
        ) : (
          <ResponsiveContainer width="100%" height={Math.min(420, 40 + events.length * 36)}>
            <BarChart
              layout="vertical"
              data={events}
              margin={{ top: 4, right: 16, left: 4, bottom: 4 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={c.grid} horizontal={false} />
              <XAxis type="number" tick={{ fill: c.tick, fontSize: 11 }} domain={[0, "auto"]} />
              <YAxis
                type="category"
                dataKey="name"
                width={200}
                tick={{ fill: c.tick, fontSize: 10 }}
                interval={0}
              />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="impact" name="Impact" fill="#818cf8" radius={[0, 4, 4, 0]} maxBarSize={22} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-3">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
          Top sources
        </div>
        {sources.length === 0 ? (
          empty
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={sources} margin={{ top: 8, right: 8, left: 0, bottom: 48 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
              <XAxis
                dataKey="name"
                tick={{ fill: c.tick, fontSize: 10 }}
                interval={0}
                angle={-28}
                textAnchor="end"
                height={56}
              />
              <YAxis allowDecimals={false} tick={{ fill: c.tick, fontSize: 11 }} width={36} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="articles" name="Articles" fill="#0ea5e9" radius={[4, 4, 0, 0]} maxBarSize={48} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-3">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
          Price scenario (model)
        </div>
        {!priceBars ? (
          empty
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={priceBars} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
              <XAxis dataKey="band" tick={{ fill: c.tick, fontSize: 12 }} />
              <YAxis tick={{ fill: c.tick, fontSize: 11 }} width={56} domain={["auto", "auto"]} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => v.toFixed(2)} />
              <Bar dataKey="value" name="Price" radius={[4, 4, 0, 0]}>
                {priceBars.map((row) => (
                  <Cell
                    key={row.band}
                    fill={row.band === "Base" ? "#6366f1" : row.band === "Low" ? "#f97316" : "#22c55e"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
