"use client";

import { useState } from "react";
import { Play, Pause, Square, SkipForward, SkipBack, Repeat, Repeat1 } from "lucide-react";
import { authFetch } from "../../lib/auth-fetch";

interface PlayerControlsProps {
  guildId: string;
  isPlaying: boolean;
  isPaused: boolean;
  loopMode: "off" | "song" | "queue";
  disabled?: boolean;
  onActionSuccess?: () => void;
}

export default function PlayerControls({
  guildId,
  isPlaying,
  isPaused,
  loopMode,
  disabled = false,
  onActionSuccess
}: PlayerControlsProps) {
  const [loading, setLoading] = useState<string | null>(null);

  const triggerAction = async (endpoint: string, actionName: string, body?: object) => {
    if (disabled || loading) return;
    setLoading(actionName);
    try {
      const res = await authFetch(`/api/v1/player/${guildId}/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (res.ok) {
        if (onActionSuccess) onActionSuccess();
      }
    } catch (err) {
      console.error(`Failed to execute player action ${actionName}:`, err);
    } finally {
      setLoading(null);
    }
  };

  const handlePlayPause = () => {
    if (isPaused) {
      triggerAction("resume", "resume");
    } else {
      triggerAction("pause", "pause");
    }
  };

  const handleLoopCycle = () => {
    let nextMode: "off" | "song" | "queue" = "off";
    if (loopMode === "off") nextMode = "song";
    else if (loopMode === "song") nextMode = "queue";
    triggerAction("loop", "loop", { mode: nextMode });
  };

  return (
    <div className="flex items-center gap-6 md:gap-8 justify-center select-none py-4">
      {/* ⏮ PREVIOUS */}
      <button
        onClick={() => triggerAction("previous", "previous")}
        disabled={disabled || loading !== null}
        className="p-3 bg-surface border border-border text-muted hover:text-accent hover:border-accent disabled:opacity-40 disabled:hover:text-muted disabled:hover:border-border rounded-full hover:scale-105 transition-all duration-200 cursor-pointer"
        title="Previous Song"
      >
        <SkipBack className="w-5 h-5 shrink-0" />
      </button>

      {/* ⏸/▶ PLAY / PAUSE */}
      <button
        onClick={handlePlayPause}
        disabled={disabled || loading !== null}
        className={`p-5 rounded-full hover:scale-105 transition-all duration-200 cursor-pointer ${
          isPaused || !isPlaying
            ? "bg-accent text-bg hover:bg-[#b0d52b] hover:shadow-[0_0_15px_rgba(200,241,53,0.35)]"
            : "bg-surface border border-border text-text hover:border-accent hover:text-accent"
        }`}
        title={isPaused || !isPlaying ? "Resume" : "Pause"}
      >
        {isPaused || !isPlaying ? (
          <Play className="w-6 h-6 fill-current shrink-0" />
        ) : (
          <Pause className="w-6 h-6 fill-current shrink-0" />
        )}
      </button>

      {/* ⏹ STOP */}
      <button
        onClick={() => triggerAction("stop", "stop")}
        disabled={disabled || loading !== null}
        className="p-3 bg-surface border border-border text-muted hover:text-accent-2 hover:border-accent-2 disabled:opacity-40 disabled:hover:text-muted disabled:hover:border-border rounded-full hover:scale-105 transition-all duration-200 cursor-pointer"
        title="Stop & Clear Queue"
      >
        <Square className="w-5 h-5 shrink-0" />
      </button>

      {/* ⏭ SKIP */}
      <button
        onClick={() => triggerAction("skip", "skip")}
        disabled={disabled || loading !== null}
        className="p-3 bg-surface border border-border text-muted hover:text-accent hover:border-accent disabled:opacity-40 disabled:hover:text-muted disabled:hover:border-border rounded-full hover:scale-105 transition-all duration-200 cursor-pointer"
        title="Skip Song"
      >
        <SkipForward className="w-5 h-5 shrink-0" />
      </button>

      {/* 🔁 LOOP */}
      <button
        onClick={handleLoopCycle}
        disabled={disabled || loading !== null}
        className={`p-3 bg-surface border rounded-full hover:scale-105 transition-all duration-200 cursor-pointer ${
          loopMode !== "off"
            ? "border-accent text-accent hover:bg-accent/10"
            : "border-border text-muted hover:text-accent hover:border-accent"
        }`}
        title={`Loop mode: ${loopMode.toUpperCase()}`}
      >
        {loopMode === "song" ? (
          <Repeat1 className="w-5 h-5 shrink-0" />
        ) : (
          <Repeat className="w-5 h-5 shrink-0" />
        )}
      </button>
    </div>
  );
}
