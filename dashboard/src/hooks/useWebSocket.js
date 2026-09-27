import { useState, useEffect, useRef, useCallback } from 'react';

const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;

export function useWebSocket(url) {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef(null);
  const messageListenersRef = useRef(new Set());
  const connectionListenersRef = useRef(new Set());
  const reconnectTimeoutRef = useRef(null);
  const backoffRef = useRef(RECONNECT_BASE_MS);
  const isMountedRef = useRef(true);

  const defaultUrl = url || `ws://${window.location.hostname || 'localhost'}:8765`;

  const connect = useCallback(function openSocket() {
    if (!isMountedRef.current) return;

    try {
      const ws = new WebSocket(defaultUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMountedRef.current || wsRef.current !== ws) return;
        setIsConnected(true);
        backoffRef.current = RECONNECT_BASE_MS;
        connectionListenersRef.current.forEach((listener) => listener(true));
      };

      ws.onmessage = (event) => {
        if (!isMountedRef.current || wsRef.current !== ws) return;
        try {
          const parsed = JSON.parse(event.data);
          messageListenersRef.current.forEach((listener) => listener(parsed));
        } catch {
          // ignore non-json messages
        }
      };

      ws.onclose = () => {
        if (!isMountedRef.current || wsRef.current !== ws) return;
        setIsConnected(false);
        wsRef.current = null;
        connectionListenersRef.current.forEach((listener) => listener(false));

        const delay = backoffRef.current;
        backoffRef.current = Math.min(delay * 2, RECONNECT_MAX_MS);
        reconnectTimeoutRef.current = setTimeout(openSocket, delay);
      };

      ws.onerror = () => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.close();
        }
      };
    } catch {
      reconnectTimeoutRef.current = setTimeout(openSocket, backoffRef.current);
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

  const subscribeMessage = useCallback((listener) => {
    messageListenersRef.current.add(listener);
    return () => messageListenersRef.current.delete(listener);
  }, []);

  const subscribeConnection = useCallback((listener) => {
    connectionListenersRef.current.add(listener);
    return () => connectionListenersRef.current.delete(listener);
  }, []);

  return { isConnected, sendMessage, subscribeMessage, subscribeConnection };
}
