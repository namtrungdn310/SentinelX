import { useEffect, useState } from "react";
import type { RealtimeMessage } from "./types";

interface Options {
  onMessage?: (message: RealtimeMessage) => void;
  enabled?: boolean;
}
export function useWebSocket({ onMessage, enabled = true }: Options = {}) {
  const [connection, setConnection] = useState<{
    socket: WebSocket;
    latencyMs: number | null;
  } | null>(null);
  const [lastMessage, setLastMessage] = useState<RealtimeMessage | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    let disposed = false;
    let socket: WebSocket | null = null;
    let retry: number | undefined;
    let ping: number | undefined;
    let started: number | null = null;
    function connect() {
      if (disposed) return;
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const current = new WebSocket(
        `${protocol}//${window.location.host}/api/v1/ws`,
      );
      socket = current;
      current.onopen = () => {
        if (disposed) return;
        setConnection({ socket: current, latencyMs: null });
        ping = window.setInterval(() => {
          if (current.readyState === WebSocket.OPEN) {
            started = performance.now();
            current.send(JSON.stringify({ event: "ping" }));
          }
        }, 8000);
      };
      current.onmessage = (event) => {
        if (disposed) return;
        try {
          const message = JSON.parse(event.data) as RealtimeMessage;
          if (
            !message ||
            typeof message.event !== "string" ||
            !message.data ||
            typeof message.data !== "object"
          )
            return;
          if (message.event === "pong") {
            if (started !== null) {
              const latencyMs = Math.round(performance.now() - started);
              setConnection({ socket: current, latencyMs });
              started = null;
            }
            return;
          }
          setLastMessage(message);
          onMessage?.(message);
        } catch {
          /* Ignore malformed frames; keep the connection alive. */
        }
      };
      current.onclose = () => {
        if (disposed) return;
        setConnection(null);
        window.clearInterval(ping);
        retry = window.setTimeout(connect, 3000);
      };
      current.onerror = () => current.close();
    }
    connect();
    return () => {
      disposed = true;
      window.clearTimeout(retry);
      window.clearInterval(ping);
      socket?.close();
    };
  }, [enabled, onMessage, attempt]);

  const isConnected =
    enabled && connection?.socket.readyState === WebSocket.OPEN;
  return {
    isConnected,
    latencyMs: isConnected ? (connection?.latencyMs ?? null) : null,
    lastMessage,
    reconnect: () => setAttempt((previous) => previous + 1),
  };
}
