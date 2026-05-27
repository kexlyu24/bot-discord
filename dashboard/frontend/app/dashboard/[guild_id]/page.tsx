"use client";

import React, { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { 
  Play, Pause, Disc, Volume2, Search, FileText, Music, 
  Trash2, Plus, AlertCircle, RefreshCw, Layers 
} from "lucide-react";
import { useWebSocket } from "../../../hooks/use-websocket";
import PlayerControls from "../../../components/player/controls";
import { authFetch } from "../../../lib/auth-fetch";

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("Dashboard page error caught by boundary:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-bg text-text p-6 text-center space-y-4">
          <AlertCircle className="w-12 h-12 text-accent-2" />
          <h2 className="font-heading text-xl font-bold uppercase tracking-tight">Something went wrong</h2>
          <p className="font-mono text-xs text-muted max-w-md">
            {this.state.error?.message || "An unexpected error occurred in the dashboard."}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-accent text-bg hover:bg-[#b0d52b] font-heading font-bold text-xs uppercase tracking-wider rounded transition-all duration-200"
          >
            Reload Page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function GuildDashboardPage() {
  return (
    <ErrorBoundary>
      <DashboardContent />
    </ErrorBoundary>
  );
}

function DashboardContent() {
  const params = useParams();
  const router = useRouter();
  const guildId = params.guild_id as string;

  const { playerState, setPlayerState, isConnected, botDisconnected, isReconnecting } = useWebSocket(guildId);
  
  const nowPlaying = playerState?.now_playing;
  const isPlaying = playerState?.is_playing || false;
  const isPaused = playerState?.is_paused || false;
  const loopMode = playerState?.loop_mode || "off";
  const progressPercent = nowPlaying ? (nowPlaying.progress / nowPlaying.duration) * 100 : 0;

  const [activeTab, setActiveTab] = useState<"search" | "lyrics">("search");
  
  // Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [searchStatus, setSearchStatus] = useState<string | null>(null);

  // Lyrics state
  const [lyricsData, setLyricsData] = useState<{ title: string; artist: string; lyrics: string } | null>(null);
  const [isLoadingLyrics, setIsLoadingLyrics] = useState(false);
  const [lyricsError, setLyricsError] = useState<string | null>(null);

  // Volume slider state
  const [localVolume, setLocalVolume] = useState<number>(50);
  const volumeDebounceRef = useRef<NodeJS.Timeout | null>(null);

  // Update volume state when websocket returns state
  useEffect(() => {
    if (playerState) {
      setLocalVolume(playerState.volume);
    }
  }, [playerState?.volume]);

  // Fetch lyrics when track changes and lyrics tab is open
  useEffect(() => {
    if (activeTab === "lyrics" && playerState?.now_playing) {
      fetchLyrics();
    }
  }, [playerState?.now_playing?.title, activeTab]);

  // Local interval timer to increment progress every second when playing
  useEffect(() => {
    if (!isPlaying || isPaused || !nowPlaying) return;
    const interval = setInterval(() => {
      setPlayerState(prev => {
        if (!prev || !prev.now_playing) return prev;
        const currentProgress = prev.now_playing.progress;
        const duration = prev.now_playing.duration;
        if (currentProgress >= duration) {
          clearInterval(interval);
          return prev;
        }
        return {
          ...prev,
          now_playing: {
            ...prev.now_playing,
            progress: currentProgress + 1
          }
        };
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [isPlaying, isPaused, nowPlaying?.title, nowPlaying?.progress]);

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseInt(e.target.value);
    setLocalVolume(value);

    if (volumeDebounceRef.current) clearTimeout(volumeDebounceRef.current);
    volumeDebounceRef.current = setTimeout(async () => {
      try {
        await authFetch(`/api/v1/player/${guildId}/volume`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ level: value }),
        });
      } catch (err) {
        console.error("Failed to update volume:", err);
      }
    }, 250); // Debounce volume calls by 250ms
  };

  const handlePlaySong = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim() || isSearching) return;

    setIsSearching(true);
    setSearchStatus("Enqueuing...");
    try {
      const res = await authFetch(`/api/v1/player/${guildId}/play`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: searchQuery }),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setSearchStatus(`Added: ${data.data.song_added}`);
        setSearchQuery("");
        setTimeout(() => setSearchStatus(null), 3000);
      } else {
        setSearchStatus(`Error: ${data.error || "Failed to add song"}`);
      }
    } catch (err) {
      setSearchStatus("Failed to enqueue song.");
    } finally {
      setIsSearching(false);
    }
  };

  const fetchLyrics = async () => {
    if (!playerState?.now_playing) return;
    setIsLoadingLyrics(true);
    setLyricsError(null);
    try {
      const res = await authFetch(`/api/v1/player/${guildId}/lyrics`, {
        method: "POST",
      });
      const json = await res.json();
      if (res.ok && json.success) {
        setLyricsData(json.data);
      } else {
        setLyricsError(json.error || "Lyrics not found.");
      }
    } catch (err) {
      setLyricsError("Failed to load lyrics.");
    } finally {
      setIsLoadingLyrics(false);
    }
  };

  const handleRemoveTrack = async (index: number) => {
    try {
      await authFetch(`/api/v1/player/${guildId}/remove`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ index: index + 1 }),
      });
    } catch (err) {
      console.error("Failed to remove track:", err);
    }
  };

  // Convert duration/progress to readable time (e.g. 3:45)
  const formatTime = (secs: number) => {
    const minutes = Math.floor(secs / 60);
    const seconds = secs % 60;
    return `${minutes}:${seconds < 10 ? "0" : ""}${seconds}`;
  };



  return (
    <div className="flex flex-col lg:flex-row h-full min-h-screen">
      
      {/* COLUMN 1: LEFT (300px) — Queue panel */}
      <section className="w-full lg:w-[300px] border-r border-border bg-surface flex flex-col h-full lg:h-screen sticky top-0 overflow-y-auto shrink-0 select-none">
        <div className="p-6 border-b border-border flex items-center justify-between">
          <div className="space-y-1">
            <h2 className="font-heading font-bold text-xs uppercase tracking-widest text-text">Upcoming Queue</h2>
            <p className="font-mono text-[10px] text-muted">{playerState?.queue_count || 0} songs enqueued</p>
          </div>
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${isConnected ? "bg-accent" : isReconnecting ? "bg-yellow-500 animate-pulse" : "bg-accent-2"}`} />
            <span className="font-mono text-[9px] uppercase tracking-wider text-muted">
              {isConnected ? "Live" : isReconnecting ? "Reconnecting..." : "Offline"}
            </span>
          </div>
        </div>

        <div className="flex-1 p-4 space-y-3 overflow-y-auto max-h-[400px] lg:max-h-none">
          {!playerState || playerState.queue.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center text-muted space-y-2">
              <Music className="w-8 h-8 opacity-40 animate-pulse" />
              <span className="font-mono text-[10px] uppercase tracking-wider">Queue is empty</span>
            </div>
          ) : (
            playerState.queue.map((song, i) => (
              <div 
                key={i} 
                className="group relative flex gap-3 p-3 bg-bg/50 border border-border/60 hover:border-accent/40 rounded transition-all duration-200"
              >
                {song.thumbnail ? (
                  <img 
                    src={song.thumbnail} 
                    alt={song.title} 
                    className="w-10 h-10 object-cover rounded shrink-0 border border-border"
                  />
                ) : (
                  <div className="w-10 h-10 bg-surface rounded border border-border flex items-center justify-center shrink-0">
                    <Music className="w-4 h-4 text-muted" />
                  </div>
                )}
                
                <div className="space-y-1 min-w-0 flex-1 pr-6">
                  <h4 className="text-xs font-bold truncate tracking-tight text-text leading-tight group-hover:text-accent transition-colors">
                    {song.title}
                  </h4>
                  <div className="flex justify-between items-center text-[9px] font-mono text-muted uppercase">
                    <span>{song.platform}</span>
                    <span>{formatTime(song.duration)}</span>
                  </div>
                </div>

                <button
                  onClick={() => handleRemoveTrack(i)}
                  className="absolute right-2 top-2 p-1.5 bg-surface border border-border text-muted hover:text-accent-2 hover:border-accent-2 opacity-0 group-hover:opacity-100 rounded transition-all cursor-pointer"
                  title="Remove from queue"
                >
                  <Trash2 className="w-3.5 h-3.5 shrink-0" />
                </button>
              </div>
            ))
          )}
        </div>
      </section>

      {/* COLUMN 2: CENTER (flex-1) — Now Playing controls */}
      <section className="flex-1 flex flex-col justify-between p-6 md:p-12 relative overflow-hidden bg-bg">
        {/* Background Blurred album cover */}
        {nowPlaying?.thumbnail && (
          <div 
            className="absolute inset-0 bg-cover bg-center opacity-5 blur-[120px] pointer-events-none scale-150 transition-all duration-1000"
            style={{ backgroundImage: `url(${nowPlaying.thumbnail})` }}
          />
        )}

        <div className="w-full flex justify-between items-start z-10 select-none">
          <div>
            <span className="font-mono text-[10px] uppercase text-accent tracking-[0.2em]">Live Session</span>
            <h2 className="font-heading text-2xl font-bold uppercase tracking-tight mt-1">Player Room</h2>
          </div>
        </div>

        {!isConnected && (
          <div className={`mt-4 p-3 ${isReconnecting ? "bg-yellow-500/10 border-yellow-500/30 text-yellow-500" : "bg-accent-2/10 border-accent-2/30 text-accent-2"} font-mono text-xs rounded flex items-center justify-between gap-2 animate-fade-in select-none z-10`}>
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{isReconnecting ? "Disconnected from server. Reconnecting..." : "Disconnected from server. WebSocket is offline."}</span>
            </div>
            {isReconnecting && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
          </div>
        )}

        {botDisconnected && (
          <div className="mt-4 p-3 bg-accent-2/10 border border-accent-2/30 text-accent-2 font-mono text-xs rounded flex items-center gap-2 animate-fade-in select-none z-10">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>Bot was disconnected from the voice channel.</span>
          </div>
        )}

        {/* Center: Track Details */}
        <div className="my-auto py-12 flex flex-col items-center justify-center text-center space-y-8 z-10">
          {nowPlaying ? (
            <>
              {/* Spinning Vinyl Cover */}
              <div className="relative group">
                <div className="absolute inset-0 bg-accent/20 rounded-full blur-xl group-hover:bg-accent/35 transition-all duration-500 scale-95" />
                {nowPlaying.thumbnail ? (
                  <img 
                    src={nowPlaying.thumbnail} 
                    alt={nowPlaying.title} 
                    className={`w-48 h-48 md:w-56 md:h-56 object-cover rounded-full border-4 border-surface shadow-2xl relative z-10 ${
                      isPlaying && !isPaused ? "animate-spin-slow" : ""
                    }`}
                  />
                ) : (
                  <div className="w-48 h-48 md:w-56 md:h-56 bg-surface border-4 border-surface rounded-full flex items-center justify-center shadow-2xl relative z-10">
                    <Disc className="w-16 h-16 text-muted animate-spin-slow" />
                  </div>
                )}
              </div>

              {/* Title & Artist */}
              <div className="space-y-3 max-w-lg select-text">
                <h1 className="font-heading text-3xl md:text-5xl font-bold tracking-tighter uppercase leading-none text-text">
                  {nowPlaying.title}
                </h1>
                <div className="flex items-center justify-center gap-3 select-none">
                  <span className="font-mono text-xs text-muted uppercase">Requester: {nowPlaying.requester}</span>
                  <span className="px-2 py-0.5 bg-surface border border-border text-[9px] font-mono uppercase text-accent tracking-wider rounded">
                    {nowPlaying.platform}
                  </span>
                </div>
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center space-y-4">
              <Disc className="w-24 h-24 text-border animate-spin-slow" />
              <div className="space-y-1">
                <h2 className="font-heading text-xl font-bold uppercase tracking-tight text-muted">Nothing Playing</h2>
                <p className="font-mono text-xs text-muted max-w-xs leading-relaxed font-light">
                  Enqueue some tracks using the search panel on the right.
                </p>
              </div>
            </div>
          )}

          {/* Progress Slider */}
          {nowPlaying && (
            <div className="w-full max-w-xl space-y-2 select-none">
              <div className="relative h-1 w-full bg-border rounded-full overflow-hidden">
                <div 
                  className="absolute left-0 top-0 bottom-0 bg-accent rounded-full transition-all duration-1000"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
              
              <div className="flex justify-between items-center font-mono text-[10px] text-muted">
                <span>{formatTime(nowPlaying.progress)}</span>
                <span>{formatTime(nowPlaying.duration)}</span>
              </div>
            </div>
          )}
        </div>

        {/* Bottom Row Controls */}
        <div className="w-full max-w-xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6 border-t border-border/60 pt-6 z-10 select-none">
          <PlayerControls 
            guildId={guildId} 
            isPlaying={isPlaying} 
            isPaused={isPaused} 
            loopMode={loopMode} 
            disabled={!nowPlaying}
          />
          
          {/* Volume Control */}
          <div className="flex items-center gap-3 bg-surface border border-border rounded px-4 py-2 w-full md:w-auto">
            <Volume2 className="w-4 h-4 text-muted shrink-0" />
            <input 
              type="range" 
              min="0" 
              max="100" 
              value={localVolume} 
              onChange={handleVolumeChange}
              className="w-full md:w-[100px] h-1 bg-border rounded-lg appearance-none cursor-pointer accent-accent"
            />
            <span className="font-mono text-[10px] text-muted min-w-[24px] text-right">{localVolume}%</span>
          </div>
        </div>
      </section>

      {/* COLUMN 3: RIGHT (300px) — Search + Lyrics */}
      <section className="w-full lg:w-[300px] border-l border-border bg-surface flex flex-col h-full lg:h-screen sticky top-0 overflow-y-auto shrink-0 select-none">
        
        {/* Toggle Headers */}
        <div className="grid grid-cols-2 border-b border-border text-center">
          <button
            onClick={() => setActiveTab("search")}
            className={`py-6 text-xs uppercase tracking-widest font-heading font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer ${
              activeTab === "search" ? "bg-bg text-accent border-b-2 border-accent" : "text-muted hover:text-text"
            }`}
          >
            <Search className="w-3.5 h-3.5" />
            Search Add
          </button>
          <button
            onClick={() => setActiveTab("lyrics")}
            className={`py-6 text-xs uppercase tracking-widest font-heading font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer ${
              activeTab === "lyrics" ? "bg-bg text-accent border-b-2 border-accent" : "text-muted hover:text-text"
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            Live Lyrics
          </button>
        </div>

        {/* Tab Content Panel */}
        <div className="flex-1 p-6 overflow-y-auto flex flex-col justify-between">
          
          {activeTab === "search" ? (
            <div className="space-y-6">
              <form onSubmit={handlePlaySong} className="space-y-3">
                <label className="block font-heading font-bold text-[10px] uppercase tracking-wider text-muted">
                  Add to playback
                </label>
                <div className="relative">
                  <input
                    type="text"
                    placeholder="Search query or URL..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full p-3 bg-bg border border-border rounded text-xs font-mono placeholder:text-muted focus:border-accent outline-none text-text"
                  />
                </div>
                <button
                  type="submit"
                  disabled={isSearching || !searchQuery.trim()}
                  className="w-full py-3 bg-accent text-bg hover:bg-[#b0d52b] font-heading font-bold text-xs uppercase tracking-wider rounded transition-all duration-200 disabled:opacity-40 disabled:hover:bg-accent cursor-pointer"
                >
                  {isSearching ? "Loading Stream..." : "Enqueue Song"}
                </button>
              </form>

              {searchStatus && (
                <div className="p-3.5 bg-bg border border-border text-[10px] font-mono text-muted uppercase leading-relaxed rounded flex items-center gap-2 animate-fade-in">
                  <AlertCircle className="w-4 h-4 text-accent shrink-0" />
                  <span>{searchStatus}</span>
                </div>
              )}
            </div>
          ) : (
            <div className="flex-1 flex flex-col min-h-[300px]">
              {!nowPlaying ? (
                <div className="m-auto text-center text-muted space-y-2 py-8">
                  <Music className="w-8 h-8 opacity-40 mx-auto animate-pulse" />
                  <span className="font-mono text-[10px] uppercase tracking-wider block">No active track</span>
                </div>
              ) : isLoadingLyrics ? (
                <div className="m-auto text-center text-muted space-y-3 py-8">
                  <RefreshCw className="w-7 h-7 animate-spin mx-auto text-accent" />
                  <span className="font-mono text-[10px] uppercase tracking-wider block">Fetching lyrics...</span>
                </div>
              ) : lyricsError ? (
                <div className="m-auto text-center text-muted space-y-2 py-8 px-4 border border-dashed border-border rounded">
                  <AlertCircle className="w-8 h-8 text-accent-2 mx-auto" />
                  <h4 className="font-heading text-xs font-bold uppercase">{lyricsError}</h4>
                  <button 
                    onClick={fetchLyrics}
                    className="font-mono text-[9px] uppercase tracking-wider text-accent underline mt-2 cursor-pointer"
                  >
                    Retry Fetch
                  </button>
                </div>
              ) : lyricsData ? (
                <div className="space-y-4 select-text flex flex-col flex-1">
                  <div className="border-b border-border pb-3">
                    <h3 className="font-heading text-xs font-bold uppercase tracking-tight">{lyricsData.title}</h3>
                    <p className="font-mono text-[9px] text-muted uppercase">By {lyricsData.artist}</p>
                  </div>
                  
                  <div className="font-mono text-xs leading-relaxed text-muted whitespace-pre-line overflow-y-auto max-h-[450px] pr-2 scrollbar-thin">
                    {lyricsData.lyrics}
                  </div>
                </div>
              ) : (
                <div className="m-auto text-center text-muted space-y-2 py-8">
                  <FileText className="w-8 h-8 opacity-40 mx-auto" />
                  <button 
                    onClick={fetchLyrics}
                    className="font-mono text-[10px] uppercase tracking-wider text-accent underline cursor-pointer"
                  >
                    Fetch Song Lyrics
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Minimal Brand Footer */}
          <div className="border-t border-border pt-4 mt-8 flex justify-between items-center font-mono text-[8px] uppercase text-muted select-none">
            <span>Powered by Genius</span>
            <span>v1.0.0</span>
          </div>
        </div>
      </section>

    </div>
  );
}
