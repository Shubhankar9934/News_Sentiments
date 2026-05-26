/**
 * useMarketDataSocket hook tests.
 *
 *   * On `tick` payloads, the existing dashboard-live cache is patched
 *     in place (no network round-trip).
 *   * On `opportunity_version` payloads, the dashboard-live query is
 *     invalidated so the next render refetches.
 *   * The hook backs off and reconnects on close.
 *
 * jsdom does not ship a WebSocket — we install a tiny in-memory mock
 * that exposes the standard 4-callback contract.
 */

import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

import { DASHBOARD_LIVE_QUERY_KEY } from "@/hooks/useLiveMarketData";
import { useMarketDataSocket } from "@/hooks/useMarketDataSocket";
import type { DashboardLiveBundle } from "@/types/schemas";

// --------------------------------------------------------------- Mock socket
type Listener = (evt: { data?: string; code?: number }) => void;

class MockWebSocket {
  static OPEN = 1;
  static instances: MockWebSocket[] = [];

  readyState = 0;
  url: string;
  sent: string[] = [];
  private listeners: Record<string, Listener[]> = {};

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
    setTimeout(() => this.simulateOpen(), 0);
  }

  addEventListener(type: string, listener: Listener) {
    (this.listeners[type] ||= []).push(listener);
  }

  removeEventListener(type: string, listener: Listener) {
    this.listeners[type] = (this.listeners[type] || []).filter(
      (l) => l !== listener,
    );
  }

  send(data: string) {
    this.sent.push(data);
  }

  close(code = 1000) {
    this.readyState = 3;
    (this.listeners["close"] || []).forEach((l) => l({ code }));
  }

  simulateOpen() {
    this.readyState = MockWebSocket.OPEN;
    (this.listeners["open"] || []).forEach((l) => l({}));
  }

  simulateMessage(data: object) {
    (this.listeners["message"] || []).forEach((l) =>
      l({ data: JSON.stringify(data) }),
    );
  }

  simulateClose(code = 1006) {
    this.readyState = 3;
    (this.listeners["close"] || []).forEach((l) => l({ code }));
  }
}

const originalWebSocket = globalThis.WebSocket;

beforeEach(() => {
  MockWebSocket.instances.length = 0;
  // @ts-expect-error - browser API stub for jsdom.
  globalThis.WebSocket = MockWebSocket;
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  globalThis.WebSocket = originalWebSocket;
  vi.restoreAllMocks();
});

function seedBundle(qc: QueryClient) {
  const bundle: DashboardLiveBundle = {
    feed_status: "live",
    prices_updated_at: "2026-05-25T08:30:00Z",
    opportunities_updated_at: "2026-05-25T08:29:30Z",
    tickers: {
      SPY: {
        ticker: "SPY",
        quote: {
          ticker: "SPY",
          last_price: 745.64,
          bid: 745.6,
          ask: 745.66,
          change_abs: 1.5,
          change_pct: 0.2,
          volume: 12345678,
          prev_close: 744.14,
          feed_status: "live",
          updated_at: "2026-05-25T08:30:00Z",
        },
        opportunities: null,
      },
    },
  };
  qc.setQueryData(DASHBOARD_LIVE_QUERY_KEY, bundle);
}

function makeWrapper(qc: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("useMarketDataSocket", () => {
  it("patches the cached bundle when a tick arrives", async () => {
    const qc = new QueryClient();
    seedBundle(qc);
    renderHook(() => useMarketDataSocket({ tickers: ["SPY"] }), {
      wrapper: makeWrapper(qc),
    });
    // Flush the constructor's setTimeout that opens the socket.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });
    const ws = MockWebSocket.instances[0];
    expect(ws).toBeDefined();
    // Subscribe message is sent on open.
    expect(ws.sent.find((s) => s.includes("subscribe"))).toBeDefined();

    act(() => {
      ws.simulateMessage({
        type: "tick",
        ticker: "SPY",
        last: 750.25,
        bid: 750.2,
        ask: 750.3,
        change_abs: 6.11,
        change_pct: 0.82,
        volume: 22345678,
        feed_status: "live",
        ts: "2026-05-25T08:31:00Z",
      });
    });

    const patched = qc.getQueryData<DashboardLiveBundle>(DASHBOARD_LIVE_QUERY_KEY);
    expect(patched).toBeDefined();
    expect(patched?.tickers.SPY?.quote?.last_price).toBe(750.25);
    expect(patched?.tickers.SPY?.quote?.prev_close).toBe(744.14);
  });

  it("invalidates the live query when opportunity_version arrives", async () => {
    const qc = new QueryClient();
    seedBundle(qc);
    const spy = vi.spyOn(qc, "invalidateQueries");

    renderHook(() => useMarketDataSocket({ tickers: ["SPY"] }), {
      wrapper: makeWrapper(qc),
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });
    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.simulateMessage({
        type: "opportunity_version",
        ticker: "SPY",
        side: "call",
        opportunity_version: "abc",
        count: 42,
        ts: "2026-05-25T08:31:00Z",
      });
    });
    expect(spy).toHaveBeenCalledWith({
      queryKey: DASHBOARD_LIVE_QUERY_KEY,
    });
  });

  it("attempts to reconnect after a close", async () => {
    const qc = new QueryClient();
    renderHook(() => useMarketDataSocket({ tickers: [] }), {
      wrapper: makeWrapper(qc),
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });
    expect(MockWebSocket.instances.length).toBe(1);

    act(() => {
      MockWebSocket.instances[0].simulateClose(1006);
    });
    // Backoff timer fires.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(MockWebSocket.instances.length).toBeGreaterThanOrEqual(2);
  });

  it("does not connect when enabled=false", async () => {
    const qc = new QueryClient();
    renderHook(() => useMarketDataSocket({ enabled: false }), {
      wrapper: makeWrapper(qc),
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });
    expect(MockWebSocket.instances.length).toBe(0);
  });
});
