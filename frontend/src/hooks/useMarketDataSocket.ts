/**
 * WebSocket client for the Reverse BWB Trading Workstation live feed.
 *
 *   ws://.../api/v1/ws/market-data
 *
 * Two message types:
 *   { type: "tick", ... }                  — emitted every flushed price tick
 *   { type: "opportunity_version", ... }   — emitted when a new generator cycle lands
 *
 * Cache strategy:
 *   * `tick`  -> patches the cached `useLiveMarketData` bundle in place; we
 *     never refetch on a tick.
 *   * `opportunity_version` -> invalidates the per-ticker opportunity slice
 *     so the next render pulls the fresh row set over REST.
 *
 * Reconnect: exponential backoff capped at 30s. The hook is fail-soft —
 * if the socket never comes up the 4s `useLiveMarketData` poll fallback
 * keeps the dashboard alive.
 */

import { useEffect, useRef, useState } from "react";

import { useQueryClient } from "@tanstack/react-query";

import { DASHBOARD_LIVE_QUERY_KEY } from "@/hooks/useLiveMarketData";
import type {
  DashboardLiveBundle,
  DashboardLiveTickerEntry,
} from "@/types/schemas";

type ConnectionState = "idle" | "connecting" | "open" | "closed";

const DEFAULT_WS_BASE =
  import.meta.env.VITE_WS_BASE_URL?.replace(/\/$/, "") ||
  "ws://localhost:8000/api/v1";

type Options = {
  /** Tickers to subscribe to; empty/undefined = subscribe to all. */
  tickers?: string[];
  /** When false, the hook stays idle (useful for tests). */
  enabled?: boolean;
};

type TickPayload = {
  type: "tick";
  ticker: string;
  last: number | null;
  bid: number | null;
  ask: number | null;
  change_abs: number | null;
  change_pct: number | null;
  volume: number | null;
  feed_status: string;
  ts: string | null;
};

type OpportunityVersionPayload = {
  type: "opportunity_version";
  ticker: string;
  side: "call" | "put";
  opportunity_version: string;
  count: number;
  ts: string;
};

type WsMessage = TickPayload | OpportunityVersionPayload;

export type MarketDataSocketStatus = {
  state: ConnectionState;
  attempt: number;
  lastError: string | null;
};

const BACKOFF_INITIAL_MS = 500;
const BACKOFF_MAX_MS = 30_000;

export function useMarketDataSocket(opts: Options = {}): MarketDataSocketStatus {
  const { tickers, enabled = true } = opts;
  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const attemptRef = useRef(0);
  const stoppedRef = useRef(false);
  const [status, setStatus] = useState<MarketDataSocketStatus>({
    state: "idle",
    attempt: 0,
    lastError: null,
  });

  // Subscription set as a stable string key so changes only re-subscribe
  // the existing socket without reconnecting.
  const tickerKey = (tickers ?? []).map((t) => t.toUpperCase()).sort().join(",");

  useEffect(() => {
    if (!enabled) {
      stoppedRef.current = true;
      cleanup();
      return;
    }
    stoppedRef.current = false;
    connect();
    return () => {
      stoppedRef.current = true;
      cleanup();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  // When the subscription set changes, send an updated subscribe message
  // over the existing socket.
  useEffect(() => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(
      JSON.stringify({
        action: "subscribe",
        tickers: tickers ?? [],
      }),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tickerKey]);

  function connect() {
    if (stoppedRef.current) return;
    cleanup();
    setStatus((s) => ({ ...s, state: "connecting" }));
    let ws: WebSocket;
    try {
      ws = new WebSocket(`${DEFAULT_WS_BASE}/ws/market-data`);
    } catch (err) {
      scheduleReconnect((err as Error)?.message ?? "construct_failed");
      return;
    }
    wsRef.current = ws;

    ws.addEventListener("open", () => {
      attemptRef.current = 0;
      setStatus({ state: "open", attempt: 0, lastError: null });
      ws.send(
        JSON.stringify({
          action: "subscribe",
          tickers: tickers ?? [],
        }),
      );
    });

    ws.addEventListener("message", (evt) => {
      try {
        const msg = JSON.parse(String(evt.data)) as WsMessage;
        handleMessage(queryClient, msg);
      } catch {
        // Ignore — server may emit pings or unexpected payloads.
      }
    });

    ws.addEventListener("error", () => {
      // The browser tags the actual cause to `close`; we capture it there.
    });

    ws.addEventListener("close", (evt) => {
      wsRef.current = null;
      scheduleReconnect(`close:${evt.code}`);
    });
  }

  function scheduleReconnect(reason: string) {
    setStatus({
      state: "closed",
      attempt: attemptRef.current,
      lastError: reason,
    });
    if (stoppedRef.current) return;
    const delay = Math.min(
      BACKOFF_MAX_MS,
      BACKOFF_INITIAL_MS * Math.pow(2, attemptRef.current),
    );
    attemptRef.current += 1;
    timerRef.current = setTimeout(connect, delay);
  }

  function cleanup() {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    const ws = wsRef.current;
    wsRef.current = null;
    if (ws && ws.readyState === WebSocket.OPEN) {
      try {
        ws.close();
      } catch {
        // ignore
      }
    }
  }

  return status;
}

function handleMessage(
  queryClient: ReturnType<typeof useQueryClient>,
  msg: WsMessage,
) {
  if (msg.type === "tick") {
    patchTick(queryClient, msg);
    return;
  }
  if (msg.type === "opportunity_version") {
    // The cheapest cache strategy: bust the bulk live query so the next
    // render fetches the new rows in one round-trip for every ticker.
    queryClient.invalidateQueries({ queryKey: DASHBOARD_LIVE_QUERY_KEY });
    return;
  }
}

function patchTick(
  queryClient: ReturnType<typeof useQueryClient>,
  msg: TickPayload,
) {
  queryClient.setQueryData<DashboardLiveBundle | undefined>(
    DASHBOARD_LIVE_QUERY_KEY,
    (prev) => {
      if (!prev) return prev;
      const ticker = msg.ticker.toUpperCase();
      const existing = prev.tickers[ticker];
      const quote = {
        ticker,
        last_price: msg.last,
        bid: msg.bid,
        ask: msg.ask,
        change_abs: msg.change_abs,
        change_pct: msg.change_pct,
        volume: msg.volume,
        prev_close: existing?.quote?.prev_close ?? null,
        feed_status:
          (msg.feed_status as DashboardLiveBundle["feed_status"]) ?? "live",
        updated_at: msg.ts ?? null,
      };
      const nextEntry: DashboardLiveTickerEntry = {
        ticker,
        quote: quote as DashboardLiveTickerEntry["quote"],
        opportunities: existing?.opportunities ?? null,
      };
      return {
        ...prev,
        prices_updated_at: msg.ts ?? prev.prices_updated_at,
        tickers: {
          ...prev.tickers,
          [ticker]: nextEntry,
        },
      };
    },
  );
}
