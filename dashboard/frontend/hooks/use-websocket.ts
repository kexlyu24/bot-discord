import { useEffect, useState, useRef } from "react";
import { getAuthToken } from "../lib/auth-fetch";

export interface SongState {
  title: string;
  url: string;
  platform: string;
  thumbnail: string;
  duration: number;
  progress: number;
  requester: string;
}

export interface PlayerState {
  is_playing: boolean;
  is_paused: boolean;
  now_playing: SongState | null;
  queue: SongState[];
  volume: number;
  loop_mode: "off" | "song" | "queue";
  queue_count: number;
}

export function useWebSocket(guildId: string | null) {
  const [playerState, setPlayerState] = useState<PlayerState | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [botDisconnected, setBotDisconnected] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectDelayRef = useRef(1000);

  useEffect(() => {
    if (!guildId) return;

    setBotDisconnected(false);
    setIsReconnecting(false);
    let isMounted = true;

    async function connect() {
      try {
        // Read JWT directly from localStorage — no /auth/token endpoint needed
        const token = getAuthToken();
        if (!token) {
          throw new Error("No access_token in localStorage");
        }

        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const host = window.location.hostname === "localhost" ? "localhost:8000" : window.location.host;
        const wsUrl = `${protocol}//${host}/api/v1/ws/client/${guildId}?token=${token}`;
        const ws = new WebSocket(wsUrl);
        socketRef.current = ws;

        ws.onopen = () => {
          if (!isMounted) {
            ws.close();
            return;
          }
          setIsConnected(true);
          setIsReconnecting(false);
          reconnectDelayRef.current = 1000;
        };

        ws.onmessage = (event) => {
          if (!isMounted) return;
          try {
            const data = JSON.parse(event.data);

            if (data.event === "player_stopped") {
              setPlayerState(null);
              setBotDisconnected(true);
            } else if (["state_update", "song_started", "song_ended", "queue_updated"].includes(data.event)) {
              setPlayerState(data.data);
              setBotDisconnected(false);
            } else if (data.event === "ping") {
              ws.send("pong");
            }
          } catch (err) {
            console.error("[WS] Failed to parse WebSocket message JSON:", err, event.data);
          }
        };

        ws.onclose = () => {
          if (!isMounted) return;
          console.warn("[WS] Disconnected");
          setIsConnected(false);
          scheduleReconnect();
        };

        ws.onerror = (err) => {
          try {
            console.warn("[WS] Connection interrupted, reconnecting...");
            if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
              ws.close();
            }
          } catch {
            // ignore
          }
        };
      } catch (err) {
        console.warn("WebSocket connection setup error:", err);
        setIsConnected(false);
        scheduleReconnect();
      }
    }

    function scheduleReconnect() {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      setIsReconnecting(true);
      reconnectTimeoutRef.current = setTimeout(() => {
        if (isMounted) {
          reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, 30000);
          connect();
        }
      }, reconnectDelayRef.current);
    }

    connect();

    return () => {
      isMounted = false;
      if (socketRef.current) {
        socketRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [guildId]);

  return { playerState, setPlayerState, isConnected, botDisconnected, isReconnecting };
}
