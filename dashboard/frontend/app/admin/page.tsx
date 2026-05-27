"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Disc, Activity, HardDrive, Server, ShieldCheck, Trash2, ArrowRight } from "lucide-react";
import { useAuth } from "../../hooks/use-auth";
import { authFetch } from "../../lib/auth-fetch";

interface SystemHealth {
  cpu_percent: number;
  ram_used_mb: number;
  ram_total_mb: number;
  ram_percent: number;
  uptime_seconds: number;
}

interface AdminGuild {
  id: string;
  name: string;
  member_count: number;
  active_queue_count: number;
  is_playing: boolean;
}

export default function AdminPage() {
  const { user, isAdmin, isLoading } = useAuth();
  const router = useRouter();
  
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [servers, setServers] = useState<AdminGuild[]>([]);
  const [isLoadingStats, setIsLoadingStats] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && (!user || !user.is_admin)) {
      router.push("/dashboard");
    }
  }, [user, isLoading, router]);

  // Polling for health check statistics
  useEffect(() => {
    if (!user || !user.is_admin) return;

    async function fetchStats() {
      try {
        const healthRes = await authFetch("/api/v1/admin/health");
        if (healthRes.ok) {
          const json = await healthRes.json();
          if (json.success && json.data) setHealth(json.data);
        }

        const serversRes = await authFetch("/api/v1/admin/servers");
        if (serversRes.ok) {
          const json = await serversRes.json();
          if (json.success && json.data) setServers(json.data);
        }
      } catch (err) {
        console.error("Failed to load admin statistics:", err);
      } finally {
        setIsLoadingStats(false);
      }
    }

    fetchStats();
    const interval = setInterval(fetchStats, 5000); // Refreshes every 5 seconds
    return () => clearInterval(interval);
  }, [user]);

  const handleLeaveServer = async (guildId: string) => {
    if (actionLoading) return;
    const confirmLeave = confirm("Are you sure you want to force the bot to leave this server?");
    if (!confirmLeave) return;

    setActionLoading(guildId);
    try {
      const res = await authFetch(`/api/v1/admin/servers/${guildId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setServers(servers.filter(s => s.id !== guildId));
      }
    } catch (err) {
      console.error("Failed to force bot to leave server:", err);
    } finally {
      setActionLoading(null);
    }
  };

  const formatUptime = (totalSeconds: number) => {
    const d = Math.floor(totalSeconds / (3600 * 24));
    const h = Math.floor((totalSeconds % (3600 * 24)) / 3600);
    const m = Math.floor((totalSeconds % 3600) / 60);
    return `${d}d ${h}h ${m}m`;
  };

  if (isLoading || !user || !user.is_admin) {
    return (
      <div className="min-h-screen bg-bg text-text flex items-center justify-center">
        <Disc className="w-8 h-8 text-accent animate-spin-slow" />
      </div>
    );
  }

  const activePlayers = servers.filter(s => s.is_playing).length;

  return (
    <div className="p-8 md:p-12 space-y-12 select-none max-w-6xl mx-auto">
      
      {/* Page Header */}
      <div className="flex items-center justify-between border-b border-border pb-6">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-[#FFA000]" />
            <span className="font-mono text-[10px] uppercase tracking-widest text-[#FFA000]">Owner Access Only</span>
          </div>
          <h1 className="font-heading text-3xl font-bold tracking-tight uppercase">Admin Diagnostics</h1>
        </div>
      </div>

      {/* Diagnostics Metrics Grid */}
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 font-mono">
        
        {/* TOTAL SERVERS */}
        <div className="p-6 bg-surface border border-border rounded space-y-4">
          <div className="flex justify-between items-center text-muted">
            <span className="text-[10px] uppercase tracking-wider">Total Servers</span>
            <Server className="w-4 h-4 text-accent" />
          </div>
          <div className="space-y-0.5">
            <div className="text-3xl font-bold text-text">{servers.length}</div>
            <div className="text-[9px] text-muted">Bot presence count</div>
          </div>
        </div>

        {/* ACTIVE PLAYERS */}
        <div className="p-6 bg-surface border border-border rounded space-y-4">
          <div className="flex justify-between items-center text-muted">
            <span className="text-[10px] uppercase tracking-wider">Active Streamers</span>
            <Disc className="w-4 h-4 text-accent animate-spin-slow" />
          </div>
          <div className="space-y-0.5">
            <div className="text-3xl font-bold text-text">{activePlayers}</div>
            <div className="text-[9px] text-muted">Active playback rooms</div>
          </div>
        </div>

        {/* CPU USAGE */}
        <div className="p-6 bg-surface border border-border rounded space-y-4">
          <div className="flex justify-between items-center text-muted">
            <span className="text-[10px] uppercase tracking-wider">CPU Util</span>
            <Activity className="w-4 h-4 text-accent" />
          </div>
          <div className="space-y-0.5">
            <div className="text-3xl font-bold text-text">
              {isLoadingStats ? "..." : `${health?.cpu_percent || 0}%`}
            </div>
            <div className="text-[9px] text-muted">Host process load</div>
          </div>
        </div>

        {/* RAM USAGE */}
        <div className="p-6 bg-surface border border-border rounded space-y-4">
          <div className="flex justify-between items-center text-muted">
            <span className="text-[10px] uppercase tracking-wider">Memory allocation</span>
            <HardDrive className="w-4 h-4 text-accent" />
          </div>
          <div className="space-y-0.5">
            <div className="text-3xl font-bold text-text">
              {isLoadingStats ? "..." : `${health?.ram_used_mb || 0} MB`}
            </div>
            <div className="text-[9px] text-muted">
              Of {health?.ram_total_mb || 0} MB total ({health?.ram_percent || 0}%)
            </div>
          </div>
        </div>
      </section>

      {/* UPTIME ROW */}
      {health && (
        <div className="p-4 bg-surface border border-border rounded flex justify-between items-center font-mono text-xs text-muted uppercase">
          <span>Host System Uptime</span>
          <span className="text-text font-bold">{formatUptime(health.uptime_seconds)}</span>
        </div>
      )}

      {/* SERVERS MANAGEMENT TABLE */}
      <section className="space-y-4">
        <h2 className="font-heading text-lg font-bold uppercase tracking-tight">Joined Servers List</h2>
        
        <div className="border border-border rounded overflow-hidden">
          <table className="w-full text-left border-collapse font-mono text-xs">
            <thead>
              <tr className="bg-surface border-b border-border text-muted uppercase text-[10px] tracking-wider select-none">
                <th className="p-4 font-semibold">Server Name</th>
                <th className="p-4 font-semibold">Guild ID</th>
                <th className="p-4 font-semibold">Users</th>
                <th className="p-4 font-semibold">Queue Size</th>
                <th className="p-4 font-semibold">Status</th>
                <th className="p-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border bg-surface/30">
              {servers.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-muted font-light uppercase select-none">
                    {isLoadingStats ? "Querying server cache..." : "No servers connected."}
                  </td>
                </tr>
              ) : (
                servers.map((s) => (
                  <tr key={s.id} className="hover:bg-surface/50 transition-colors">
                    <td className="p-4 font-bold text-text select-text">{s.name}</td>
                    <td className="p-4 text-muted select-text">{s.id}</td>
                    <td className="p-4 text-text">{s.member_count}</td>
                    <td className="p-4 text-text">{s.active_queue_count}</td>
                    <td className="p-4">
                      <div className="flex items-center gap-2 select-none">
                        <span className={`w-1.5 h-1.5 rounded-full ${s.is_playing ? "bg-accent animate-pulse" : "bg-muted"}`} />
                        <span className="uppercase text-[10px] text-muted">
                          {s.is_playing ? "Playing" : "Idle"}
                        </span>
                      </div>
                    </td>
                    <td className="p-4 text-right">
                      <div className="flex justify-end gap-3 select-none">
                        <button
                          onClick={() => handleLeaveServer(s.id)}
                          disabled={actionLoading === s.id}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-2 border border-border text-muted hover:text-accent-2 hover:border-accent-2 disabled:opacity-40 rounded transition-all cursor-pointer text-[10px] uppercase font-bold"
                          title="Force bot to leave server"
                        >
                          <Trash2 className="w-3.5 h-3.5 shrink-0" />
                          Leave
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

    </div>
  );
}
