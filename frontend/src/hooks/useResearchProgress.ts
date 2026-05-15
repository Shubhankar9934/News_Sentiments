import { useCallback, useRef, useState } from "react";

const wsBase =
  import.meta.env.VITE_WS_BASE_URL?.replace(/\/$/, "") || "ws://localhost:8000/api/v1";

export function useResearchProgress() {
  const wsRef = useRef<WebSocket | null>(null);
  const [messages, setMessages] = useState<Array<{ stage: string; message: string }>>([]);
  const [lastError, setLastError] = useState<string | null>(null);

  const run = useCallback((ticker: string, days: number) => {
    setMessages([]);
    setLastError(null);
    wsRef.current?.close();
    const url = `${wsBase}/ws/research-progress`;
    const ws = new WebSocket(url);
    wsRef.current = ws;
    ws.onmessage = (ev) => {
      try {
        const payload = JSON.parse(ev.data as string) as {
          type: string;
          stage?: string;
          message?: string;
          detail?: string;
          data?: unknown;
        };
        if (payload.type === "progress" && payload.stage) {
          setMessages((m) => [...m, { stage: payload.stage!, message: payload.message ?? "" }]);
        }
        if (payload.type === "error") {
          setLastError(payload.detail ?? "error");
        }
      } catch {
        setLastError("invalid_ws_payload");
      }
    };
    ws.onopen = () => {
      ws.send(JSON.stringify({ action: "run", ticker, days }));
    };
    ws.onerror = () => setLastError("websocket_error");
    return ws;
  }, []);

  const close = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  return { run, close, messages, lastError };
}
