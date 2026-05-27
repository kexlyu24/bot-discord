"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Disc, ArrowRight, Plus } from "lucide-react";
import { SidebarGuild } from "./layout";
import { authFetch } from "../../lib/auth-fetch";

export default function GuildsPage() {
  const [guilds, setGuilds] = useState<SidebarGuild[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [clientId, setClientId] = useState<string>("your_bot_client_id");

  useEffect(() => {
    async function fetchGuildsAndSettings() {
      try {
        const res = await authFetch("/api/v1/guilds/");
        if (res.ok) {
          const json = await res.json();
          if (json.success && json.data) {
            setGuilds(json.data);
          }
        }
        
        // Fetch login url to parse Client ID if needed
        const authRes = await authFetch("/api/v1/auth/login");
        if (authRes.ok) {
          const authJson = await authRes.json();
          if (authJson.success && authJson.data?.url) {
            const urlObj = new URL(authJson.data.url);
            const cid = urlObj.searchParams.get("client_id");
            if (cid) setClientId(cid);
          }
        }
      } catch (err) {
        console.error("Failed to load guilds overview:", err);
      } finally {
        setIsLoading(false);
      }
    }
    fetchGuildsAndSettings();
  }, []);

  return (
    <div className="p-8 md:p-12 space-y-8 select-none">
      <div className="space-y-2">
        <h1 className="font-heading text-3xl font-bold tracking-tight uppercase">Select a Server</h1>
        <p className="font-mono text-xs text-muted font-light">
          Choose a server from your list where the bot is active to manage playback controls and lists.
        </p>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-[120px] bg-surface border border-border rounded animate-pulse" />
          ))}
        </div>
      ) : guilds.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 border border-dashed border-border rounded p-8 text-center space-y-4">
          <Disc className="w-12 h-12 text-muted animate-spin-slow" />
          <div className="space-y-1">
            <h3 className="font-heading text-lg font-semibold uppercase">No Active Servers Found</h3>
            <p className="font-mono text-xs text-muted max-w-sm font-light">
              We couldn't locate any servers you share with the bot. Add the bot to your server to begin.
            </p>
          </div>
          <a
            href={`https://discord.com/oauth2/authorize?client_id=${clientId}&permissions=8&scope=bot%20applications.commands`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-6 py-3 bg-accent text-bg font-heading text-xs font-bold uppercase rounded hover:shadow-[0_0_15px_rgba(200,241,53,0.25)] transition-all cursor-pointer"
          >
            Invite Bot to Server
            <Plus className="w-4 h-4" />
          </a>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {guilds.map((g) => (
            <Link
              key={g.id}
              href={`/dashboard/${g.id}`}
              className="group block p-6 bg-surface border border-border rounded hover:border-accent hover:-translate-y-1 transition-all duration-300 relative overflow-hidden"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-4">
                  {g.icon ? (
                    <img
                      src={`https://cdn.discordapp.com/icons/${g.id}/${g.icon}.png`}
                      alt={g.name}
                      className="w-12 h-12 rounded-full border border-border group-hover:border-accent transition-colors shrink-0 animate-fade-in"
                    />
                  ) : (
                    <div className="w-12 h-12 bg-surface-2 border border-border rounded-full flex items-center justify-center text-sm font-bold text-muted uppercase group-hover:border-accent transition-colors shrink-0">
                      {g.name.substring(0, 2)}
                    </div>
                  )}
                  
                  <div className="space-y-1 truncate">
                    <h3 className="font-heading text-sm font-bold uppercase tracking-tight group-hover:text-accent transition-colors truncate">
                      {g.name}
                    </h3>
                    <div className="flex items-center gap-2">
                      <div className={`w-1.5 h-1.5 rounded-full ${g.is_playing ? "bg-accent animate-pulse" : "bg-muted"}`} />
                      <span className="font-mono text-[10px] text-muted uppercase tracking-wider">
                        {g.is_playing ? "Playing" : "Idle"}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="p-2 bg-surface-2 border border-border rounded text-muted group-hover:text-accent group-hover:border-accent transition-colors cursor-pointer">
                  <ArrowRight className="w-4 h-4" />
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
