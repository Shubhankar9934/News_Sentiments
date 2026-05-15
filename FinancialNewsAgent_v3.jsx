import { useState, useEffect, useCallback } from "react";

// ─── Config ────────────────────────────────────────────────────────────────
const BACKEND_URL = "http://localhost:8000";  // change to your deployed URL

const PIPELINE_STAGES = [
  { id: "collect",    label: "Collector",   icon: "ti-satellite",        desc: "Fetching from Finnhub · NewsAPI · Polygon" },
  { id: "clean",      label: "Cleaner",     icon: "ti-filter",           desc: "Embedding dedupe via sentence-transformers" },
  { id: "sentiment",  label: "Sentiment",   icon: "ti-brain",            desc: "FinBERT deterministic scoring" },
  { id: "events",     label: "Events",      icon: "ti-bolt",             desc: "Rule-based event extraction" },
  { id: "market",     label: "Market",      icon: "ti-trending-up",      desc: "OHLCV · returns · volatility regime" },
  { id: "impact",     label: "Impact",      icon: "ti-crosshair",        desc: "Event impact scoring formula" },
  { id: "compress",   label: "Compress",    icon: "ti-layers-intersect", desc: "Narrative cluster compression" },
  { id: "report",     label: "Report",      icon: "ti-report-analytics", desc: "Claude reasoning on real data" },
  { id: "prediction", label: "Prediction",  icon: "ti-chart-line",       desc: "News-grounded price range" },
];

const TIME_WINDOWS = [
  { label: "Today",       days: 1  },
  { label: "Yesterday",   days: 2  },
  { label: "Last 7 days", days: 7  },
  { label: "Last 30 days",days: 30 },
];

// Claude fallback system prompt (used when backend is offline)
const FALLBACK_SYSTEM_PROMPT = `You are a financial news research AI with web search. Search for REAL recent news about the given ticker, then return ONLY a valid JSON object — no markdown, no backticks.

Structure:
{
  "data_mode": "real" or "limited",
  "data_quality_note": "<one sentence>",
  "articles_analyzed": <int>,
  "unique_sources": <int>,
  "duplicates_removed": <int>,
  "overall_sentiment_score": <float -1 to 1>,
  "overall_sentiment_label": "Bullish" or "Bearish" or "Neutral" or "Mixed",
  "sentiment_breakdown": [{"label":"Bullish","count":<int>,"pct":<float>,"score":0.7},{"label":"Neutral","count":<int>,"pct":<float>,"score":0.0},{"label":"Bearish","count":<int>,"pct":<float>,"score":-0.6}],
  "key_events": [{"type":"Earnings" or "Regulation" or "Product" or "Partnership" or "Macro" or "Supply Chain" or "Analyst","description":"<sentence>","impact":"High" or "Medium" or "Low","impact_score":<float 0-1>}],
  "dominant_narrative": "<sentence>",
  "what_happened": "<two sentences>",
  "price_movers": "<sentence>",
  "source_reliability": [{"source":"<name>","articles":<int>,"reliability_score":<int>,"tier":"Tier 1" or "Tier 2" or "Tier 3" or "Social" or "Primary"}],
  "articles": [{"headline":"<under 12 words>","source":"<name>","published_at":"<date>","sentiment":<float>,"sentiment_label":"Bullish" or "Bearish" or "Neutral","event_type":"<type>" or null,"reliability_score":<int>,"impact_score":<float>}],
  "_pipeline_meta": {"run_id":"fallback","raw_articles":<int>,"after_dedupe":<int>,"duplicates_removed":<int>,"clusters_to_claude":<int>,"sources":[],"volatility_regime":"medium","top_impact_events":[],"data_mode":"fallback","elapsed_s":0},
  "price_prediction": {"last_close":<float>,"low":<float>,"base":<float>,"high":<float>,"change_pct_low":<float>,"change_pct_base":<float>,"change_pct_high":<float>,"confidence":<int>,"bias":"Bullish" or "Bearish" or "Neutral","volatility_regime":"medium","reasoning":"<two sentences>","upside_catalyst":"<sentence>","downside_risk":"<sentence>","disclaimer":"Web search fallback mode. Not financial advice."}
}
Include 4 key_events, 7 articles. Use web search for real headlines.`;

// ─── API client ─────────────────────────────────────────────────────────────

async function checkBackendHealth() {
  try {
    const r = await fetch(`${BACKEND_URL}/health`, { signal: AbortSignal.timeout(3000) });
    if (!r.ok) return { online: false };
    return { online: true, ...(await r.json()) };
  } catch {
    return { online: false };
  }
}

async function fetchFromBackend(ticker, days) {
  const r = await fetch(`${BACKEND_URL}/research/${ticker}?days=${days}`, {
    signal: AbortSignal.timeout(120000),
  });
  if (!r.ok) throw new Error(`Backend ${r.status}: ${r.statusText}`);
  return r.json();
}

async function fetchHistory(ticker) {
  try {
    const r = await fetch(`${BACKEND_URL}/history/${ticker}?limit=8`, { signal: AbortSignal.timeout(5000) });
    if (!r.ok) return [];
    return r.json();
  } catch { return []; }
}

async function fetchAnalogs(ticker, eventType) {
  try {
    const r = await fetch(`${BACKEND_URL}/analogs/${ticker}/${eventType}`, { signal: AbortSignal.timeout(5000) });
    if (!r.ok) return [];
    return r.json();
  } catch { return []; }
}

async function fetchFromClaude(ticker, days) {
  const windowLabel = TIME_WINDOWS.find(w => w.days === days)?.label ?? `${days} days`;
  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "claude-sonnet-4-20250514",
      max_tokens: 4000,
      system: FALLBACK_SYSTEM_PROMPT,
      tools: [{ type: "web_search_20250305", name: "web_search" }],
      messages: [{ role: "user", content: `Ticker: ${ticker}. Time window: ${windowLabel}. Search for real news then return the JSON report.` }],
    }),
  });
  const data = await r.json();
  if (data.error) throw new Error(data.error.message);
  const text = (data.content ?? []).map(b => b.type === "text" ? b.text : "").filter(Boolean).join("");
  const clean = text.replace(/```json|```/g, "").trim();
  const s = clean.indexOf("{"), e = clean.lastIndexOf("}");
  if (s === -1) throw new Error("No JSON in response");
  return JSON.parse(clean.slice(s, e + 1));
}

// ─── Small UI helpers ────────────────────────────────────────────────────────

function Tag({ children, color = "secondary", size = 11 }) {
  return (
    <span style={{ fontSize: size, padding: "2px 8px", borderRadius: "var(--border-radius-md)", background: `var(--color-background-${color})`, color: `var(--color-text-${color})`, border: `0.5px solid var(--color-border-tertiary)`, whiteSpace: "nowrap" }}>
      {children}
    </span>
  );
}

function SentimentBar({ score, label }) {
  const pct   = Math.round(((score + 1) / 2) * 100);
  const color = score > 0.2 ? "#1D9E75" : score < -0.2 ? "#E24B4A" : "#BA7517";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <div style={{ flex: 1, height: 6, background: "var(--color-background-secondary)", borderRadius: 99, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 99, transition: "width 1s ease" }} />
      </div>
      <span style={{ fontSize: 12, fontWeight: 500, color, minWidth: 46 }}>{label}</span>
    </div>
  );
}

function Card({ children, style = {} }) {
  return (
    <div style={{ background: "var(--color-background-primary)", border: "0.5px solid var(--color-border-tertiary)", borderRadius: "var(--border-radius-lg)", ...style }}>
      {children}
    </div>
  );
}

function SectionLabel({ icon, children, style = {} }) {
  return (
    <p style={{ margin: "0 0 12px", fontSize: 12, fontWeight: 500, color: "var(--color-text-secondary)", textTransform: "uppercase", letterSpacing: "0.06em", display: "flex", alignItems: "center", gap: 6, ...style }}>
      {icon && <i className={`ti ${icon}`} style={{ fontSize: 13 }} aria-hidden="true" />}
      {children}
    </p>
  );
}

// ─── Backend status bar ──────────────────────────────────────────────────────

function BackendStatusBar({ health, mode, onRetry }) {
  if (!health) return null;
  const isOnline = health.online;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 14px", borderRadius: "var(--border-radius-md)", background: isOnline ? "var(--color-background-success)" : "var(--color-background-warning)", marginBottom: 16, border: `0.5px solid ${isOnline ? "#5DCAA533" : "#EF9F2733"}` }}>
      <i className={`ti ${isOnline ? "ti-server" : "ti-server-off"}`} style={{ fontSize: 14, color: isOnline ? "var(--color-text-success)" : "var(--color-text-warning)" }} aria-hidden="true" />
      <div style={{ flex: 1 }}>
        <span style={{ fontSize: 12, fontWeight: 500, color: isOnline ? "var(--color-text-success)" : "var(--color-text-warning)" }}>
          {isOnline ? `Backend online · v${health.version ?? "3.0"} · DB ${health.db ? "✓" : "✗"} · Qdrant ${health.qdrant ? "✓" : "✗"}` : "Backend offline — using Claude web search fallback"}
        </span>
      </div>
      <span style={{ fontSize: 11, color: isOnline ? "var(--color-text-success)" : "var(--color-text-warning)", opacity: 0.75 }}>
        {isOnline ? `${BACKEND_URL}` : "Claude API"}
      </span>
      {!isOnline && (
        <button onClick={onRetry} style={{ fontSize: 11, padding: "2px 10px", background: "transparent" }}>
          <i className="ti ti-refresh" style={{ fontSize: 12 }} aria-hidden="true" /> retry
        </button>
      )}
    </div>
  );
}

// ─── Pipeline tracker ────────────────────────────────────────────────────────

function PipelineTracker({ stages, running, currentStage, stageStatus, backendMode }) {
  const displayStages = backendMode
    ? stages
    : stages.filter(s => ["collect","clean","sentiment","events","report","prediction"].includes(s.id));

  return (
    <div style={{ display: "flex", gap: 0, marginBottom: 20, background: "var(--color-background-secondary)", borderRadius: "var(--border-radius-lg)", overflow: "hidden", border: "0.5px solid var(--color-border-tertiary)" }}>
      {displayStages.map((s, i) => {
        const isDone   = stageStatus[s.id] === "done";
        const isActive = running && currentStage === i;
        return (
          <div key={s.id} title={s.desc} style={{ flex: 1, padding: "10px 4px", textAlign: "center", borderRight: i < displayStages.length - 1 ? "0.5px solid var(--color-border-tertiary)" : "none", transition: "background 0.3s", background: isDone ? "var(--color-background-success)" : isActive ? "var(--color-background-info)" : "transparent" }}>
            <i className={`ti ${isDone ? "ti-check" : isActive ? "ti-loader-2" : s.icon}`} style={{ fontSize: 13, display: "block", margin: "0 auto 4px", color: isDone ? "var(--color-text-success)" : isActive ? "var(--color-text-info)" : "var(--color-text-tertiary)" }} aria-hidden="true" />
            <span style={{ fontSize: 8, color: isDone ? "var(--color-text-success)" : isActive ? "var(--color-text-info)" : "var(--color-text-tertiary)", lineHeight: 1.3, display: "block" }}>{s.label}</span>
          </div>
        );
      })}
    </div>
  );
}

// ─── Pipeline meta panel ─────────────────────────────────────────────────────

function PipelineMetaPanel({ meta }) {
  if (!meta) return null;
  const { run_id, raw_articles, after_dedupe, duplicates_removed, clusters_to_claude,
          sources, volatility_regime, top_impact_events, elapsed_s, run_at } = meta;

  const volColor = volatility_regime === "high" ? "#E24B4A" : volatility_regime === "low" ? "#1D9E75" : "#BA7517";

  return (
    <Card style={{ padding: "16px 18px", marginBottom: 20 }}>
      <SectionLabel icon="ti-cpu">Pipeline execution trace</SectionLabel>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 8, marginBottom: 14 }}>
        {[
          { label: "Raw collected",       value: raw_articles,       icon: "ti-news" },
          { label: "After dedupe",        value: after_dedupe,       icon: "ti-copy-off" },
          { label: "Dupes removed",       value: duplicates_removed, icon: "ti-x" },
          { label: "Clusters → Claude",   value: clusters_to_claude, icon: "ti-layers-intersect" },
          { label: "Pipeline time",       value: elapsed_s != null ? `${elapsed_s}s` : "—", icon: "ti-clock" },
        ].map(m => (
          <div key={m.label} style={{ background: "var(--color-background-secondary)", borderRadius: "var(--border-radius-md)", padding: "10px 12px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 4 }}>
              <i className={`ti ${m.icon}`} style={{ fontSize: 12, color: "var(--color-text-tertiary)" }} aria-hidden="true" />
              <span style={{ fontSize: 10, color: "var(--color-text-tertiary)" }}>{m.label}</span>
            </div>
            <span style={{ fontSize: 18, fontWeight: 500 }}>{m.value ?? "—"}</span>
          </div>
        ))}
        <div style={{ background: "var(--color-background-secondary)", borderRadius: "var(--border-radius-md)", padding: "10px 12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 4 }}>
            <i className="ti ti-activity" style={{ fontSize: 12, color: "var(--color-text-tertiary)" }} aria-hidden="true" />
            <span style={{ fontSize: 10, color: "var(--color-text-tertiary)" }}>Vol regime</span>
          </div>
          <span style={{ fontSize: 18, fontWeight: 500, color: volColor, textTransform: "capitalize" }}>{volatility_regime ?? "—"}</span>
        </div>
      </div>

      {sources?.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <span style={{ fontSize: 11, color: "var(--color-text-tertiary)", marginRight: 8 }}>Sources ingested:</span>
          <span style={{ display: "inline-flex", flexWrap: "wrap", gap: 4 }}>
            {sources.map(s => <Tag key={s}>{s}</Tag>)}
          </span>
        </div>
      )}

      {top_impact_events?.length > 0 && (
        <div>
          <span style={{ fontSize: 11, color: "var(--color-text-tertiary)", display: "block", marginBottom: 6 }}>Top impact events (by formula score):</span>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {top_impact_events.map((ev, i) => (
              <div key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start", padding: "8px 10px", background: "var(--color-background-secondary)", borderRadius: "var(--border-radius-md)" }}>
                <span style={{ fontSize: 11, fontWeight: 500, color: "var(--color-text-tertiary)", minWidth: 20 }}>#{i + 1}</span>
                <div style={{ flex: 1 }}>
                  <p style={{ margin: "0 0 3px", fontSize: 13, fontWeight: 500 }}>{ev.headline}</p>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    <Tag>{ev.source}</Tag>
                    {ev.event && <Tag>{ev.event}</Tag>}
                    <Tag color="warning">impact {(ev.impact * 100).toFixed(0)}</Tag>
                    {ev.abnormal_return != null && (
                      <Tag color={ev.abnormal_return > 0 ? "success" : "danger"}>
                        return {ev.abnormal_return > 0 ? "+" : ""}{ev.abnormal_return.toFixed(2)}%
                      </Tag>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {run_at && (
        <p style={{ margin: "10px 0 0", fontSize: 10, color: "var(--color-text-tertiary)" }}>
          Run ID: {run_id ?? "—"} · {run_at ? new Date(run_at).toLocaleString() : ""}
        </p>
      )}
    </Card>
  );
}

// ─── History panel ───────────────────────────────────────────────────────────

function HistoryPanel({ history, onLoad }) {
  if (!history?.length) return null;
  return (
    <Card style={{ padding: "14px 18px", marginBottom: 20 }}>
      <SectionLabel icon="ti-history">Previous reports (from DB)</SectionLabel>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {history.map(h => (
          <div key={h.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", background: "var(--color-background-secondary)", borderRadius: "var(--border-radius-md)" }}>
            <i className="ti ti-file-analytics" style={{ fontSize: 14, color: "var(--color-text-tertiary)" }} aria-hidden="true" />
            <div style={{ flex: 1 }}>
              <span style={{ fontSize: 13 }}>{h.time_window} window</span>
              <span style={{ fontSize: 11, color: "var(--color-text-tertiary)", marginLeft: 8 }}>
                {h.articles_ct} articles · {new Date(h.created_at).toLocaleDateString()}
              </span>
            </div>
            <Tag color={h.data_mode === "real" ? "success" : "warning"}>{h.data_mode}</Tag>
            <button onClick={() => onLoad(h)} style={{ fontSize: 11, padding: "2px 10px" }}>load</button>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ─── Analogs panel ───────────────────────────────────────────────────────────

function AnalogsPanel({ analogs, eventType }) {
  if (!analogs?.length) return null;
  return (
    <Card style={{ padding: "16px 18px", marginBottom: 20 }}>
      <SectionLabel icon="ti-clock-rewind">Historical analogs — {eventType} events</SectionLabel>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {analogs.map((a, i) => (
          <div key={i} style={{ padding: "10px 12px", background: "var(--color-background-secondary)", borderRadius: "var(--border-radius-md)" }}>
            <p style={{ margin: "0 0 4px", fontSize: 13, fontWeight: 500 }}>{a.headline}</p>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              <Tag>{a.published_at ? new Date(a.published_at).toLocaleDateString() : "—"}</Tag>
              {a.sentiment_score != null && (
                <Tag color={a.sentiment_score > 0 ? "success" : a.sentiment_score < 0 ? "danger" : "secondary"}>
                  sentiment {a.sentiment_score > 0 ? "+" : ""}{a.sentiment_score?.toFixed(2)}
                </Tag>
              )}
              {a.impact_score != null && <Tag color="warning">impact {(a.impact_score * 100).toFixed(0)}</Tag>}
              {a.close != null && <Tag>close ${a.close?.toFixed(2)}</Tag>}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ─── Data mode badge ─────────────────────────────────────────────────────────

function DataModeBadge({ mode, note, backendMode }) {
  const cfg = {
    real:     { color: "var(--color-text-success)", bg: "var(--color-background-success)", icon: "ti-database", label: "Real data — backend pipeline" },
    limited:  { color: "var(--color-text-warning)", bg: "var(--color-background-warning)", icon: "ti-wifi-2",   label: "Limited data" },
    fallback: { color: "var(--color-text-warning)", bg: "var(--color-background-warning)", icon: "ti-cloud",    label: "Claude web search fallback" },
    simulated:{ color: "var(--color-text-danger)",  bg: "var(--color-background-danger)",  icon: "ti-alert-triangle", label: "Simulated — no real data" },
  }[mode] ?? { color: "var(--color-text-secondary)", bg: "var(--color-background-secondary)", icon: "ti-question-mark", label: "Unknown" };
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "10px 14px", borderRadius: "var(--border-radius-md)", background: cfg.bg, marginBottom: 16 }}>
      <i className={`ti ${cfg.icon}`} style={{ fontSize: 14, color: cfg.color, marginTop: 1 }} aria-hidden="true" />
      <div>
        <span style={{ fontSize: 12, fontWeight: 500, color: cfg.color }}>{cfg.label}</span>
        {note && <p style={{ margin: "3px 0 0", fontSize: 12, color: cfg.color, opacity: 0.8 }}>{note}</p>}
      </div>
    </div>
  );
}

// ─── Source reliability ───────────────────────────────────────────────────────

function SourceReliabilityPanel({ sources }) {
  if (!sources?.length) return null;
  return (
    <Card style={{ padding: "16px 18px", marginBottom: 20 }}>
      <SectionLabel icon="ti-shield-check">Source reliability scoring</SectionLabel>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {[...sources].sort((a, b) => b.reliability_score - a.reliability_score).map(s => (
          <div key={s.source} style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 13, minWidth: 130 }}>{s.source}</span>
            <Tag>{s.tier}</Tag>
            <div style={{ flex: 1, height: 5, background: "var(--color-background-secondary)", borderRadius: 99, overflow: "hidden" }}>
              <div style={{ width: `${s.reliability_score}%`, height: "100%", background: s.reliability_score >= 85 ? "#1D9E75" : s.reliability_score >= 65 ? "#BA7517" : "#E24B4A", borderRadius: 99 }} />
            </div>
            <span style={{ fontSize: 12, fontWeight: 500, minWidth: 26, textAlign: "right", color: s.reliability_score >= 85 ? "#1D9E75" : s.reliability_score >= 65 ? "#BA7517" : "#E24B4A" }}>{s.reliability_score}</span>
            <span style={{ fontSize: 11, color: "var(--color-text-tertiary)", minWidth: 40 }}>{s.articles} art.</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ─── Article card ─────────────────────────────────────────────────────────────

function ArticleCard({ article, idx, onAnalogSearch }) {
  const sentColor = article.sentiment > 0.2 ? "var(--color-text-success)" : article.sentiment < -0.2 ? "var(--color-text-danger)" : "var(--color-text-warning)";
  const sentBg    = article.sentiment > 0.2 ? "var(--color-background-success)" : article.sentiment < -0.2 ? "var(--color-background-danger)" : "var(--color-background-warning)";
  const rel = article.reliability_score ?? 70;
  return (
    <div style={{ padding: "14px 16px", borderBottom: "0.5px solid var(--color-border-tertiary)", display: "flex", gap: 14 }}>
      <span style={{ fontSize: 11, color: "var(--color-text-tertiary)", minWidth: 18, paddingTop: 2 }}>{idx + 1}</span>
      <div style={{ flex: 1 }}>
        <p style={{ margin: "0 0 6px", fontSize: 14, fontWeight: 500, lineHeight: 1.45 }}>{article.headline}</p>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
          <span style={{ fontSize: 11, color: "var(--color-text-tertiary)" }}>{article.source}</span>
          <span style={{ fontSize: 11, color: "var(--color-text-tertiary)" }}>·</span>
          <span style={{ fontSize: 11, color: "var(--color-text-tertiary)" }}>{article.published_at}</span>
          <span style={{ fontSize: 11, color: "var(--color-text-tertiary)" }}>· rel {rel}</span>
          {article.impact_score != null && <Tag color="warning">impact {(article.impact_score * 100).toFixed(0)}</Tag>}
          {article.event_type && (
            <button onClick={() => onAnalogSearch?.(article.event_type)}
              style={{ fontSize: 10, padding: "1px 7px", background: "var(--color-background-secondary)", border: "0.5px solid var(--color-border-secondary)", borderRadius: "var(--border-radius-md)", color: "var(--color-text-secondary)", cursor: "pointer" }}
              title="Search historical analogs for this event type">
              {article.event_type} <i className="ti ti-clock-rewind" style={{ fontSize: 10 }} aria-hidden="true" />
            </button>
          )}
          <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: "var(--border-radius-md)", background: sentBg, color: sentColor }}>{article.sentiment_label}</span>
        </div>
      </div>
    </div>
  );
}

// ─── Price range gauge ────────────────────────────────────────────────────────

function PriceRangeGauge({ pred }) {
  if (!pred) return null;
  const { last_close, low, base, high, change_pct_low, change_pct_base, change_pct_high,
          confidence, bias, volatility_regime, reasoning, upside_catalyst, downside_risk, disclaimer } = pred;

  const span = high - low;
  const basePct  = span > 0 ? Math.max(0, Math.min(100, ((base - low) / span) * 100)) : 50;
  const closePct = span > 0 ? Math.max(0, Math.min(100, ((last_close - low) / span) * 100)) : 50;
  const bc = bias === "Bullish" ? "#1D9E75" : bias === "Bearish" ? "#E24B4A" : "#BA7517";
  const bb = bias === "Bullish" ? "#E1F5EE" : bias === "Bearish" ? "#FCEBEB" : "#FAEEDA";
  const fmt    = v => v != null ? `$${Number(v).toFixed(2)}` : "—";
  const fmtPct = v => v != null ? `${v > 0 ? "+" : ""}${Number(v).toFixed(1)}%` : "—";
  const volColor = volatility_regime === "high" ? "#E24B4A" : volatility_regime === "low" ? "#1D9E75" : "#BA7517";

  return (
    <Card style={{ padding: "20px 20px 16px", marginBottom: 20 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 18 }}>
        <i className="ti ti-chart-line" style={{ fontSize: 16, color: "var(--color-text-secondary)" }} aria-hidden="true" />
        <SectionLabel style={{ margin: 0 }}>Today's price range — news-driven model</SectionLabel>
        <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          {volatility_regime && <span style={{ fontSize: 11, padding: "3px 8px", borderRadius: "var(--border-radius-md)", background: `${volColor}18`, color: volColor }}>vol: {volatility_regime}</span>}
          <span style={{ fontSize: 11, padding: "3px 10px", borderRadius: "var(--border-radius-md)", background: bb, color: bc, fontWeight: 500 }}>{bias} bias</span>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 22 }}>
        {[
          { label: "Bear case", price: low,  chg: change_pct_low,  color: "#E24B4A", bg: "#FCEBEB", bold: false },
          { label: "Base case", price: base, chg: change_pct_base, color: bc, bg: bb,       bold: true },
          { label: "Bull case", price: high, chg: change_pct_high, color: "#1D9E75", bg: "#E1F5EE", bold: false },
        ].map(s => (
          <div key={s.label} style={{ textAlign: "center", padding: "12px 8px", borderRadius: "var(--border-radius-md)", background: s.bold ? s.bg : "var(--color-background-secondary)", border: s.bold ? `1.5px solid ${s.color}33` : "0.5px solid var(--color-border-tertiary)" }}>
            <div style={{ fontSize: 11, color: "var(--color-text-tertiary)", marginBottom: 6 }}>{s.label}</div>
            <div style={{ fontSize: s.bold ? 22 : 18, fontWeight: s.bold ? 500 : 400, color: s.color }}>{fmt(s.price)}</div>
            <div style={{ fontSize: 12, color: s.color, marginTop: 3 }}>{fmtPct(s.chg)}</div>
          </div>
        ))}
      </div>

      <div style={{ marginBottom: 8 }}>
        <div style={{ position: "relative", height: 10, borderRadius: 99, background: "linear-gradient(to right, #FCEBEB 0%, #FAEEDA 40%, #E1F5EE 100%)" }}>
          <div style={{ position: "absolute", left: `${closePct}%`, top: "50%", transform: "translate(-50%,-50%)", width: 10, height: 10, borderRadius: "50%", background: "var(--color-text-tertiary)", border: "2px solid var(--color-background-primary)", zIndex: 1 }} />
          <div style={{ position: "absolute", left: `${basePct}%`,  top: "50%", transform: "translate(-50%,-50%)", width: 14, height: 14, borderRadius: "50%", background: bc, border: "2px solid var(--color-background-primary)", zIndex: 2 }} />
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontSize: 11, color: "var(--color-text-tertiary)" }}>
          <span>{fmt(low)}</span>
          <span style={{ display: "flex", gap: 10 }}>
            <span style={{ display: "flex", alignItems: "center", gap: 3 }}><span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: "var(--color-text-tertiary)" }} /> prev close {fmt(last_close)}</span>
            <span style={{ display: "flex", alignItems: "center", gap: 3 }}><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: "50%", background: bc }} /> target {fmt(base)}</span>
          </span>
          <span>{fmt(high)}</span>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "14px 0" }}>
        <span style={{ fontSize: 11, color: "var(--color-text-tertiary)", minWidth: 90 }}>Model confidence</span>
        <div style={{ flex: 1, height: 5, background: "var(--color-background-secondary)", borderRadius: 99, overflow: "hidden" }}>
          <div style={{ width: `${confidence}%`, height: "100%", background: bc, borderRadius: 99 }} />
        </div>
        <span style={{ fontSize: 12, fontWeight: 500, color: bc, minWidth: 32 }}>{confidence}%</span>
        <span style={{ fontSize: 11, color: "var(--color-text-tertiary)" }}>
          {confidence < 50 ? "· low — sparse data" : confidence < 70 ? "· moderate" : "· high signal"}
        </span>
      </div>

      <div style={{ borderTop: "0.5px solid var(--color-border-tertiary)", paddingTop: 14, display: "flex", flexDirection: "column", gap: 10 }}>
        <p style={{ margin: 0, fontSize: 13, lineHeight: 1.6, color: "var(--color-text-secondary)" }}>{reasoning}</p>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <div style={{ padding: "10px 12px", borderRadius: "var(--border-radius-md)", background: "#E1F5EE" }}>
            <div style={{ fontSize: 10, fontWeight: 500, color: "#0F6E56", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.06em" }}>Upside catalyst</div>
            <p style={{ margin: 0, fontSize: 12, color: "#085041", lineHeight: 1.5 }}>{upside_catalyst}</p>
          </div>
          <div style={{ padding: "10px 12px", borderRadius: "var(--border-radius-md)", background: "#FCEBEB" }}>
            <div style={{ fontSize: 10, fontWeight: 500, color: "#993C1D", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.06em" }}>Downside risk</div>
            <p style={{ margin: 0, fontSize: 12, color: "#4A1B0C", lineHeight: 1.5 }}>{downside_risk}</p>
          </div>
        </div>
        <p style={{ margin: 0, fontSize: 10, color: "var(--color-text-tertiary)", fontStyle: "italic" }}>{disclaimer}</p>
      </div>
    </Card>
  );
}

// ─── Report section ───────────────────────────────────────────────────────────

function ReportSection({ report, ticker, onAnalogSearch }) {
  if (!report) return null;
  const sentScore = report.overall_sentiment_score ?? 0;
  const sentColor = sentScore > 0.2 ? "#1D9E75" : sentScore < -0.2 ? "#E24B4A" : "#BA7517";

  return (
    <div style={{ marginTop: 24 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        <i className="ti ti-report-analytics" style={{ fontSize: 18, color: "var(--color-text-secondary)" }} aria-hidden="true" />
        <h2 style={{ margin: 0, fontSize: 16, fontWeight: 500 }}>{ticker}</h2>
        <span style={{ marginLeft: "auto", fontSize: 12, padding: "3px 10px", borderRadius: "var(--border-radius-md)", background: sentScore > 0.2 ? "#E1F5EE" : sentScore < -0.2 ? "#FCEBEB" : "#FAEEDA", color: sentColor, fontWeight: 500 }}>
          {report.overall_sentiment_label} {sentScore > 0 ? "+" : ""}{(sentScore * 100).toFixed(0)}
        </span>
      </div>

      <DataModeBadge mode={report.data_mode} note={report.data_quality_note} />

      {/* Metric cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 10, marginBottom: 20 }}>
        {[
          { label: "Articles",   value: report.articles_analyzed,  icon: "ti-article" },
          { label: "Sources",    value: report.unique_sources,      icon: "ti-building-broadcast-tower" },
          { label: "Key events", value: report.key_events?.length ?? 0, icon: "ti-bolt" },
          { label: "Dupes removed", value: report.duplicates_removed, icon: "ti-copy-off" },
        ].map(m => (
          <div key={m.label} style={{ background: "var(--color-background-secondary)", borderRadius: "var(--border-radius-md)", padding: "12px 14px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 5 }}>
              <i className={`ti ${m.icon}`} style={{ fontSize: 13, color: "var(--color-text-tertiary)" }} aria-hidden="true" />
              <span style={{ fontSize: 10, color: "var(--color-text-secondary)" }}>{m.label}</span>
            </div>
            <span style={{ fontSize: 22, fontWeight: 500 }}>{m.value}</span>
          </div>
        ))}
      </div>

      {/* Sentiment + Events */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 20 }}>
        <Card style={{ padding: "16px 18px" }}>
          <SectionLabel>Sentiment breakdown</SectionLabel>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {(report.sentiment_breakdown ?? []).map(s => (
              <div key={s.label}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                  <span style={{ fontSize: 13 }}>{s.label}</span>
                  <span style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>{s.count}</span>
                </div>
                <SentimentBar score={s.score} label={`${Math.round(s.pct)}%`} />
              </div>
            ))}
          </div>
        </Card>

        <Card style={{ padding: "16px 18px" }}>
          <SectionLabel>Key events</SectionLabel>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {(report.key_events ?? []).map((ev, i) => {
              const ic = ev.impact === "High" ? "#E24B4A" : ev.impact === "Medium" ? "#BA7517" : "#888780";
              return (
                <div key={i} style={{ display: "flex", gap: 7, alignItems: "flex-start" }}>
                  <Tag>{ev.type}</Tag>
                  <span style={{ fontSize: 11, padding: "2px 6px", borderRadius: "var(--border-radius-md)", background: `${ic}18`, color: ic, whiteSpace: "nowrap" }}>{ev.impact}</span>
                  {ev.impact_score != null && <Tag color="warning">{(ev.impact_score * 100).toFixed(0)}</Tag>}
                  <span style={{ fontSize: 12, lineHeight: 1.4 }}>{ev.description}</span>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      {/* Narrative */}
      <Card style={{ padding: "16px 18px", marginBottom: 20 }}>
        <SectionLabel>Dominant narrative</SectionLabel>
        <p style={{ margin: "0 0 14px", fontSize: 15, lineHeight: 1.6 }}>{report.dominant_narrative}</p>
        <div style={{ borderTop: "0.5px solid var(--color-border-tertiary)", paddingTop: 12 }}>
          <p style={{ margin: "0 0 5px", fontSize: 12, color: "var(--color-text-secondary)" }}>What happened?</p>
          <p style={{ margin: "0 0 10px", fontSize: 14, lineHeight: 1.6 }}>{report.what_happened}</p>
          <p style={{ margin: "0 0 5px", fontSize: 12, color: "var(--color-text-secondary)" }}>Which events likely moved price?</p>
          <p style={{ margin: 0, fontSize: 14, lineHeight: 1.6 }}>{report.price_movers}</p>
        </div>
      </Card>

      <PipelineMetaPanel meta={report._pipeline_meta} />
      <SourceReliabilityPanel sources={report.source_reliability} />
      <PriceRangeGauge pred={report.price_prediction} />

      {/* Articles */}
      <Card style={{ overflow: "hidden" }}>
        <p style={{ margin: 0, padding: "14px 16px 0", fontSize: 12, fontWeight: 500, color: "var(--color-text-secondary)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
          Articles — sorted by impact score
        </p>
        {(report.articles ?? [])
          .sort((a, b) => (b.impact_score ?? 0) - (a.impact_score ?? 0))
          .map((a, i) => <ArticleCard key={i} article={a} idx={i} onAnalogSearch={onAnalogSearch} />)}
      </Card>
    </div>
  );
}

// ─── Main app ─────────────────────────────────────────────────────────────────

export default function FinancialNewsAgent() {
  const [ticker,       setTicker]      = useState("NVDA");
  const [timeWindow,   setTimeWindow]  = useState(TIME_WINDOWS[2]);
  const [running,      setRunning]     = useState(false);
  const [stage,        setStage]       = useState(-1);
  const [stageStatus,  setStageStatus] = useState({});
  const [report,       setReport]      = useState(null);
  const [error,        setError]       = useState(null);
  const [health,       setHealth]      = useState(null);
  const [history,      setHistory]     = useState([]);
  const [analogs,      setAnalogs]     = useState(null);
  const [analogEvent,  setAnalogEvent] = useState(null);
  const [backendMode,  setBackendMode] = useState(false);

  // Check backend health on mount
  const checkHealth = useCallback(async () => {
    const h = await checkBackendHealth();
    setHealth(h);
    setBackendMode(h.online);
  }, []);

  useEffect(() => { checkHealth(); }, [checkHealth]);

  async function runPipeline() {
    if (!ticker.trim()) return;
    setRunning(true);
    setStage(0);
    setStageStatus({});
    setReport(null);
    setError(null);
    setAnalogs(null);
    setAnalogEvent(null);

    const sym = ticker.trim().toUpperCase();

    try {
      if (backendMode) {
        // ── Backend path: real pipeline ──────────────────────────────────
        const stageIds = PIPELINE_STAGES.map(s => s.id);
        // Poll every 1.5s to animate stages; backend runs async
        let si = 0;
        const ticker2 = setInterval(() => {
          if (si < stageIds.length - 1) {
            setStage(si);
            si++;
          }
        }, 1400);

        try {
          const result = await fetchFromBackend(sym, timeWindow.days);
          clearInterval(ticker2);
          // Mark all done
          const done = {};
          PIPELINE_STAGES.forEach(s => { done[s.id] = "done"; });
          setStageStatus(done);
          setReport(result);

          // Load history in background
          fetchHistory(sym).then(setHistory);
        } catch (e) {
          clearInterval(ticker2);
          throw e;
        }
      } else {
        // ── Fallback path: Claude web search ─────────────────────────────
        const fallbackStages = ["collect","clean","sentiment","events","report","prediction"];
        for (let i = 0; i < fallbackStages.length; i++) {
          setStage(i);
          await new Promise(r => setTimeout(r, 700 + Math.random() * 400));
          setStageStatus(prev => ({ ...prev, [fallbackStages[i]]: "done" }));
        }
        const result = await fetchFromClaude(sym, timeWindow.days);
        setReport(result);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setRunning(false);
      setStage(-1);
    }
  }

  async function handleAnalogSearch(eventType) {
    if (!backendMode) return;
    setAnalogEvent(eventType);
    const results = await fetchAnalogs(ticker.trim().toUpperCase(), eventType);
    setAnalogs(results);
    // Scroll to analogs
    setTimeout(() => document.getElementById("analogs-anchor")?.scrollIntoView({ behavior: "smooth" }), 100);
  }

  const currentStageIdx = PIPELINE_STAGES.findIndex((s, i) => i === stage);

  return (
    <div style={{ padding: "1.5rem 0", maxWidth: 720, margin: "0 auto" }}>
      <h2 className="sr-only">Financial News Research Agent v3</h2>

      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
          <i className="ti ti-chart-candle" style={{ fontSize: 20, color: "var(--color-text-secondary)" }} aria-hidden="true" />
          <span style={{ fontSize: 18, fontWeight: 500 }}>Financial News Research</span>
          <Tag color="success" size={10}>v3 · connected</Tag>
        </div>
        <p style={{ margin: 0, fontSize: 13, color: "var(--color-text-secondary)" }}>
          {backendMode
            ? "Finnhub · NewsAPI · Polygon → FinBERT → Qdrant → impact scoring → Claude synthesis"
            : "Claude web search → sentiment → events → report (backend offline)"}
        </p>
      </div>

      {/* Backend status */}
      <BackendStatusBar health={health} mode={backendMode} onRetry={checkHealth} />

      {/* Controls */}
      <div style={{ display: "flex", gap: 10, marginBottom: 18, flexWrap: "wrap" }}>
        <input
          type="text"
          value={ticker}
          onChange={e => setTicker(e.target.value.toUpperCase())}
          placeholder="NVDA"
          disabled={running}
          style={{ width: 100, fontFamily: "var(--font-mono)", fontSize: 15, letterSpacing: "0.05em" }}
          onKeyDown={e => e.key === "Enter" && !running && runPipeline()}
        />
        <select
          value={timeWindow.label}
          onChange={e => setTimeWindow(TIME_WINDOWS.find(w => w.label === e.target.value))}
          disabled={running}
          style={{ flex: 1, minWidth: 140 }}
        >
          {TIME_WINDOWS.map(w => <option key={w.label}>{w.label}</option>)}
        </select>
        <button onClick={runPipeline} disabled={running || !ticker.trim()} style={{ display: "flex", alignItems: "center", gap: 6, padding: "0 18px" }}>
          {running
            ? <><i className="ti ti-loader-2" style={{ fontSize: 14 }} aria-hidden="true" /> Running…</>
            : <><i className="ti ti-player-play" style={{ fontSize: 14 }} aria-hidden="true" /> Run pipeline ↗</>}
        </button>
      </div>

      {/* Pipeline tracker */}
      <PipelineTracker
        stages={PIPELINE_STAGES}
        running={running}
        currentStage={stage}
        stageStatus={stageStatus}
        backendMode={backendMode}
      />

      {/* Active stage indicator */}
      {running && stage >= 0 && stage < PIPELINE_STAGES.length && (
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "11px 14px", background: "var(--color-background-info)", borderRadius: "var(--border-radius-md)", marginBottom: 18 }}>
          <i className="ti ti-loader-2" style={{ fontSize: 15, color: "var(--color-text-info)" }} aria-hidden="true" />
          <span style={{ fontSize: 14, fontWeight: 500, color: "var(--color-text-info)" }}>{PIPELINE_STAGES[stage]?.label}</span>
          <span style={{ fontSize: 13, color: "var(--color-text-info)" }}>— {PIPELINE_STAGES[stage]?.desc}</span>
          {backendMode && <Tag color="info" size={10}>backend</Tag>}
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{ padding: "12px 16px", background: "var(--color-background-danger)", borderRadius: "var(--border-radius-md)", marginBottom: 18, color: "var(--color-text-danger)", fontSize: 14 }}>
          <i className="ti ti-alert-circle" style={{ marginRight: 8 }} aria-hidden="true" />{error}
          {backendMode && <span style={{ marginLeft: 10, fontSize: 12 }}>— check that backend is running at {BACKEND_URL}</span>}
        </div>
      )}

      {/* Empty state */}
      {!running && !report && !error && (
        <div style={{ textAlign: "center", padding: "40px 20px", color: "var(--color-text-tertiary)" }}>
          <i className="ti ti-telescope" style={{ fontSize: 32, display: "block", margin: "0 auto 12px" }} aria-hidden="true" />
          <p style={{ margin: "0 0 6px", fontSize: 14 }}>Enter a ticker and run the pipeline</p>
          <p style={{ margin: 0, fontSize: 12 }}>
            {backendMode
              ? "Connected to real backend — Finnhub · NewsAPI · Polygon · FinBERT · Qdrant"
              : "Using Claude web search fallback — start backend for full pipeline"}
          </p>
        </div>
      )}

      {/* History (backend only) */}
      {backendMode && history.length > 0 && !report && (
        <HistoryPanel history={history} onLoad={r => setReport(r.report_json)} />
      )}

      {/* Main report */}
      <ReportSection report={report} ticker={ticker} onAnalogSearch={handleAnalogSearch} />

      {/* Historical analogs (backend only) */}
      <div id="analogs-anchor" />
      {backendMode && analogs && (
        <AnalogsPanel analogs={analogs} eventType={analogEvent} />
      )}

      {!backendMode && report && (
        <div style={{ padding: "10px 14px", background: "var(--color-background-secondary)", borderRadius: "var(--border-radius-md)", marginTop: 16, fontSize: 12, color: "var(--color-text-secondary)" }}>
          <i className="ti ti-info-circle" style={{ marginRight: 6 }} aria-hidden="true" />
          Historical analog search requires the backend (PostgreSQL + Qdrant). Start the backend to unlock event memory.
        </div>
      )}
    </div>
  );
}
