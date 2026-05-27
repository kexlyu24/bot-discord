"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { Disc, ShieldAlert, LogOut, LayoutGrid } from "lucide-react";
import { useAuth } from "../../hooks/use-auth";
import { authFetch, clearAuthToken } from "../../lib/auth-fetch";

export interface SidebarGuild {
  id: string;
  name: string;
  icon: string | null;
  has_bot: boolean;
  is_playing: boolean;
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [guilds, setGuilds] = useState<SidebarGuild[]>([]);
  const [isLoadingGuilds, setIsLoadingGuilds] = useState(true);

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/");
    }
  }, [user, isLoading, router]);

  useEffect(() => {
    if (!user) return;
    async function fetchSidebarGuilds() {
      try {
        const res = await authFetch("/api/v1/guilds/");
        if (res.ok) {
          const json = await res.json();
          if (json.success && json.data) {
            setGuilds(json.data);
          }
        }
      } catch (err) {
        console.error("Failed to fetch sidebar guilds:", err);
      } finally {
        setIsLoadingGuilds(false);
      }
    }
    fetchSidebarGuilds();
  }, [user]);

  const handleLogout = async () => {
    try {
      await authFetch("/api/v1/auth/logout", { method: "POST" });
    } catch (err) {
      console.error("Logout failed:", err);
    } finally {
      clearAuthToken();
      window.location.href = "/";
    }
  };

  if (isLoading || !user) {
    return (
      <div className="min-h-screen bg-bg text-text flex items-center justify-center">
        <Disc className="w-8 h-8 text-accent animate-spin-slow" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg text-text flex">
      {/* LEFT SIDEBAR - 240px */}
      <aside className="w-[240px] border-r border-border bg-surface flex flex-col justify-between shrink-0 h-screen sticky top-0 overflow-y-auto z-20">
        <div className="flex flex-col">
          {/* Header Brand */}
          <div className="p-6 border-b border-border flex items-center gap-3">
            <Disc className="w-6 h-6 text-accent animate-spin-slow" />
            <span className="font-heading font-bold text-sm tracking-widest uppercase select-none">EQ_BOT</span>
          </div>

          {/* Navigation Links */}
          <nav className="p-4 space-y-1">
            <Link
              href="/dashboard"
              className={`flex items-center gap-3 px-3 py-2 text-xs uppercase tracking-wider font-semibold rounded hover:bg-surface-2 transition-all ${
                pathname === "/dashboard" ? "text-accent bg-surface-2 border-l-2 border-accent" : "text-muted hover:text-text"
              }`}
            >
              <LayoutGrid className="w-4 h-4" />
              Servers Overview
            </Link>

            {user.is_admin && (
              <Link
                href="/admin"
                className={`flex items-center gap-3 px-3 py-2 text-xs uppercase tracking-wider font-semibold rounded hover:bg-surface-2 transition-all ${
                  pathname?.startsWith("/admin") ? "text-[#FFA000] bg-surface-2 border-l-2 border-[#FFA000]" : "text-muted hover:text-text"
                }`}
              >
                <ShieldAlert className="w-4 h-4 text-[#FFA000]" />
                Admin Panel
              </Link>
            )}
          </nav>

          {/* Server List */}
          <div className="px-4 py-2">
            <div className="text-[10px] uppercase font-mono font-bold tracking-widest text-muted px-3 py-2 border-b border-border/40 select-none">
              Active Servers
            </div>
            
            <div className="mt-2 space-y-1">
              {isLoadingGuilds ? (
                <div className="py-4 text-center text-xs text-muted font-mono animate-pulse">
                  Loading...
                </div>
              ) : guilds.length === 0 ? (
                <div className="px-3 py-4 text-center text-[10px] text-muted font-mono leading-relaxed select-none">
                  No active servers
                </div>
              ) : (
                guilds.map((g) => {
                  const active = pathname === `/dashboard/${g.id}`;
                  return (
                    <Link
                      key={g.id}
                      href={`/dashboard/${g.id}`}
                      className={`group flex items-center justify-between px-3 py-2 rounded text-xs transition-all ${
                        active ? "bg-surface-2 text-accent font-semibold" : "text-text hover:bg-surface-2"
                      }`}
                    >
                      <div className="flex items-center gap-2.5 truncate">
                        {g.icon ? (
                          <img
                            src={`https://cdn.discordapp.com/icons/${g.id}/${g.icon}.png`}
                            alt={g.name}
                            className="w-5 h-5 rounded-full shrink-0"
                          />
                        ) : (
                          <div className="w-5 h-5 bg-border rounded-full flex items-center justify-center text-[8px] font-bold text-muted uppercase shrink-0">
                            {g.name.substring(0, 2)}
                          </div>
                        )}
                        <span className="truncate font-light">{g.name}</span>
                      </div>
                      
                      {g.is_playing && (
                        <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse shrink-0 ml-2" />
                      )}
                    </Link>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* Footer User Info & Logout */}
        <div className="p-4 border-t border-border bg-bg/40 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 truncate">
            {user.avatar ? (
              <img
                src={`https://cdn.discordapp.com/avatars/${user.id}/${user.avatar}.png`}
                alt={user.username}
                className="w-7 h-7 rounded-full shrink-0"
              />
            ) : (
              <div className="w-7 h-7 bg-border rounded-full flex items-center justify-center text-xs font-bold text-muted uppercase shrink-0">
                {user.username.substring(0, 2)}
              </div>
            )}
            <span className="text-xs truncate font-semibold text-text">{user.username}</span>
          </div>
          <button
            onClick={handleLogout}
            className="p-1.5 hover:bg-surface-2 border border-transparent hover:border-border text-muted hover:text-accent-2 rounded transition-all cursor-pointer"
            title="Log Out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </aside>

      {/* MAIN CONTENT AREA */}
      <main className="flex-1 overflow-y-auto h-screen relative">
        {children}
      </main>
    </div>
  );
}
