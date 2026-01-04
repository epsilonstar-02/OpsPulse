import { useState, useEffect, useCallback, useRef } from 'react';

// Determine WebSocket URL based on environment
function getWebSocketURL() {
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL;
  }
  
  if (import.meta.env.DEV) {
    return 'ws://localhost:8001';
  }
  
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  return `${protocol}//${host}`;
}

const WS_BASE_URL = getWebSocketURL();

const INITIAL_RECONNECT_DELAY = 2000;
const MAX_RECONNECT_DELAY = 30000;
const MAX_RECONNECT_ATTEMPTS = 5;

/**
 * WebSocket connection states
 */
export const ConnectionState = {
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  DISCONNECTED: 'disconnected',
  ERROR: 'error',
};

/**
 * Available WebSocket channels
 */
export const Channels = {
  LOGS: 'logs',
  ALERTS: 'alerts',
  REMEDIATIONS: 'remediations',
  STATS: 'stats',
  HEALTH: 'health',
  PIPELINE: 'pipeline',
  ALL: 'all',
};

// Singleton WebSocket state
let globalWs = null;
let globalClientId = null;
let globalState = ConnectionState.DISCONNECTED;
let connectionListeners = new Set();
let messageListeners = new Set();
let reconnectTimeout = null;
let reconnectAttempts = 0;
let currentDelay = INITIAL_RECONNECT_DELAY;
let isConnecting = false;

function notifyConnectionChange(state) {
  globalState = state;
  connectionListeners.forEach(fn => fn(state));
}

function notifyMessage(msg) {
  messageListeners.forEach(fn => fn(msg));
}

function connectGlobal() {
  if (isConnecting || globalWs?.readyState === WebSocket.OPEN) {
    return;
  }
  
  isConnecting = true;
  notifyConnectionChange(ConnectionState.CONNECTING);

  try {
    globalWs = new WebSocket(`${WS_BASE_URL}/ws/live`);

    globalWs.onopen = () => {
      isConnecting = false;
      notifyConnectionChange(ConnectionState.CONNECTED);
      reconnectAttempts = 0;
      currentDelay = INITIAL_RECONNECT_DELAY;
      
      // Subscribe to all channels
      if (globalWs?.readyState === WebSocket.OPEN) {
        globalWs.send(JSON.stringify({ type: 'subscribe', channels: ['all'] }));
      }
    };

    globalWs.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'connected') {
          globalClientId = data.client_id;
        }
        notifyMessage(data);
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    globalWs.onerror = () => {
      isConnecting = false;
      notifyConnectionChange(ConnectionState.ERROR);
    };

    globalWs.onclose = () => {
      isConnecting = false;
      globalWs = null;
      globalClientId = null;
      notifyConnectionChange(ConnectionState.DISCONNECTED);
      
      if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS && connectionListeners.size > 0) {
        reconnectAttempts += 1;
        const delay = Math.min(currentDelay, MAX_RECONNECT_DELAY);
        currentDelay = delay * 2;
        
        console.log(`WebSocket reconnecting in ${delay/1000}s (attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);
        
        reconnectTimeout = setTimeout(connectGlobal, delay);
      }
    };
  } catch (e) {
    isConnecting = false;
    notifyConnectionChange(ConnectionState.ERROR);
    console.error('Failed to create WebSocket:', e);
  }
}

/**
 * Custom hook for WebSocket connection (singleton pattern)
 */
export function useWebSocket({
  channels = [Channels.ALL],
  autoConnect = true,
  onLog,
  onAlert,
  onRemediation,
  onStats,
  onHealth,
  onMessage,
} = {}) {
  const [connectionState, setConnectionState] = useState(globalState);
  const [clientId, setClientId] = useState(globalClientId);
  const [lastMessage, setLastMessage] = useState(null);
  const [error, setError] = useState(null);
  
  const callbacksRef = useRef({ onLog, onAlert, onRemediation, onStats, onHealth, onMessage });
  callbacksRef.current = { onLog, onAlert, onRemediation, onStats, onHealth, onMessage };

  useEffect(() => {
    const onConnectionChange = (state) => {
      setConnectionState(state);
      if (state === ConnectionState.CONNECTED) {
        setClientId(globalClientId);
        setError(null);
      } else if (state === ConnectionState.ERROR) {
        setError('WebSocket connection error');
      }
    };

    const onMsg = (data) => {
      setLastMessage(data);
      const { onLog, onAlert, onRemediation, onStats, onHealth, onMessage } = callbacksRef.current;
      
      onMessage?.(data);
      
      switch (data.type) {
        case 'connected':
          setClientId(data.client_id);
          break;
        case 'log':
          onLog?.(data.data || data);
          break;
        case 'alert':
          onAlert?.(data.data || data);
          break;
        case 'remediation':
          onRemediation?.(data.data || data);
          break;
        case 'stats':
          onStats?.(data.data || data);
          break;
        case 'health':
          onHealth?.(data.data || data);
          break;
        case 'error':
          setError(data.message);
          break;
      }
    };

    connectionListeners.add(onConnectionChange);
    messageListeners.add(onMsg);

    // Connect if needed
    if (autoConnect && globalState !== ConnectionState.CONNECTED && !isConnecting) {
      connectGlobal();
    }

    // Sync state
    setConnectionState(globalState);
    if (globalClientId) setClientId(globalClientId);

    return () => {
      connectionListeners.delete(onConnectionChange);
      messageListeners.delete(onMsg);
      
      // Disconnect only when no listeners remain
      if (connectionListeners.size === 0) {
        if (reconnectTimeout) {
          clearTimeout(reconnectTimeout);
          reconnectTimeout = null;
        }
        if (globalWs) {
          globalWs.close();
          globalWs = null;
        }
        reconnectAttempts = 0;
        currentDelay = INITIAL_RECONNECT_DELAY;
      }
    };
  }, [autoConnect]);

  const sendMessage = useCallback((message) => {
    if (globalWs?.readyState === WebSocket.OPEN) {
      globalWs.send(JSON.stringify(message));
      return true;
    }
    return false;
  }, []);

  const subscribe = useCallback((channelList) => {
    return sendMessage({
      type: 'subscribe',
      channels: Array.isArray(channelList) ? channelList : [channelList],
    });
  }, [sendMessage]);

  const unsubscribe = useCallback((channelList) => {
    return sendMessage({
      type: 'unsubscribe',
      channels: Array.isArray(channelList) ? channelList : [channelList],
    });
  }, [sendMessage]);

  const ping = useCallback(() => sendMessage({ type: 'ping' }), [sendMessage]);

  const connect = useCallback(() => {
    reconnectAttempts = 0;
    currentDelay = INITIAL_RECONNECT_DELAY;
    connectGlobal();
  }, []);

  const disconnect = useCallback(() => {
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
      reconnectTimeout = null;
    }
    reconnectAttempts = MAX_RECONNECT_ATTEMPTS;
    if (globalWs) {
      globalWs.close();
      globalWs = null;
    }
    setConnectionState(ConnectionState.DISCONNECTED);
    setClientId(null);
  }, []);

  return {
    connectionState,
    isConnected: connectionState === ConnectionState.CONNECTED,
    clientId,
    lastMessage,
    error,
    sendMessage,
    subscribe,
    unsubscribe,
    ping,
    connect,
    disconnect,
  };
}

export default useWebSocket;
