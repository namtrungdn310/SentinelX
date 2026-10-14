/**
 * React Hook managing WebSocket connection with auto-reconnect and latency ping.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type { RealtimeMessage } from './types';

interface UseWebSocketOptions {
  onMessage?: (msg: RealtimeMessage) => void;
}

export function useWebSocket({ onMessage }: UseWebSocketOptions = {}) {
  const [isConnected, setIsConnected] = useState(false);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [lastMessage, setLastMessage] = useState<RealtimeMessage | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const pingIntervalRef = useRef<number | null>(null);
  const pingStartRef = useRef<number | null>(null);
  const isMountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!isMountedRef.current) return;

    // Use current host and proxy to ws://.../api/v1/ws
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/v1/ws`;

    try {
      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onopen = () => {
        if (!isMountedRef.current) return;
        setIsConnected(true);

        // Start periodic ping to track latency
        pingIntervalRef.current = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            pingStartRef.current = performance.now();
            ws.send(JSON.stringify({ event: 'ping' }));
          }
        }, 8000);
      };

      ws.onmessage = (event) => {
        if (!isMountedRef.current) return;
        try {
          const parsed: RealtimeMessage = JSON.parse(event.data);

          if (parsed.event === 'pong' && pingStartRef.current) {
            const rtt = Math.round(performance.now() - pingStartRef.current);
            setLatencyMs(rtt);
            pingStartRef.current = null;
            return;
          }

          setLastMessage(parsed);
          if (onMessage) {
            onMessage(parsed);
          }
        } catch {
          // Ignore non-JSON frame
        }
      };

      ws.onclose = () => {
        if (!isMountedRef.current) return;
        setIsConnected(false);
        setLatencyMs(null);
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
        }

        // Auto-reconnect after 3 seconds
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      // Reconnect on initial error
      reconnectTimeoutRef.current = window.setTimeout(connect, 3000);
    }
  }, [onMessage]);

  useEffect(() => {
    isMountedRef.current = true;
    connect();

    return () => {
      isMountedRef.current = false;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      if (socketRef.current) socketRef.current.close();
    };
  }, [connect]);

  return {
    isConnected,
    latencyMs,
    lastMessage,
    reconnect: connect,
  };
}
