import { useState, useEffect, useRef, useCallback } from 'react';

const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;

export function useWebSocket(url) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const backoffRef = useRef(RECONNECT_BASE_MS);
  const isMountedRef = useRef(true);

  const defaultUrl = url || `ws://${window.location.hostname || 'localhost'}:8765`;

  const connect = useCallback(() => {
    if (!isMountedRef.current) return;

    try {
      const ws = new WebSocket(defaultUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMountedRef.current) return;
        setIsConnected(true);
        backoffRef.current = RECONNECT_BASE_MS;
      };

      ws.onmessage = (event) => {
        if (!isMountedRef.current) return;
        try {
          const parsed = JSON.parse(event.data);
          setLastMessage(parsed);
        } catch {
          // ignore non-json messages
        }
      };

      ws.onclose = () => {
        if (!isMountedRef.current) return;
        setIsConnected(false);
        wsRef.current = null;

        const delay = backoffRef.current;
        backoffRef.current = Math.min(delay * 2, RECONNECT_MAX_MS);
        reconnectTimeoutRef.current = setTimeout(connect, delay);
      };

      ws.onerror = () => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.close();
        }
      };
    } catch {
      reconnectTimeoutRef.current = setTimeout(connect, backoffRef.current);
    }
  }, [defaultUrl]);

  useEffect(() => {
    isMountedRef.current = true;
    connect();

    return () => {
      isMountedRef.current = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  const sendMessage = useCallback((msgObj) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msgObj));
      return true;
    }
    return false;
  }, []);

  return { isConnected, sendMessage, lastMessage };
}
