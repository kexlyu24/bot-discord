"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Disc, Zap, Shield, ArrowUpRight, Music } from "lucide-react";

export default function LandingPage() {
  const router = useRouter();
  const [loginUrl, setLoginUrl] = useState<string | null>(null);

  useEffect(() => {
    async function fetchLoginUrl() {
      try {
        const res = await fetch("/api/v1/auth/login");
        if (res.ok) {
          const json = await res.json();
          if (json.success && json.data?.url) {
            setLoginUrl(json.data.url);
          }
        }
      } catch (err) {
        console.error("Failed to load login URL:", err);
      }
    }
    fetchLoginUrl();
  }, []);

  const handleLogin = () => {
    if (loginUrl) {
      window.location.href = loginUrl;
    } else {
      router.push("/login");
    }
  };

  return (
    <main className="min-h-screen bg-bg text-text selection:bg-accent selection:text-bg overflow-hidden relative flex flex-col justify-between p-8 md:p-16">
      {/* Background Decorative Element */}
      <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-accent/5 rounded-full blur-[150px] -z-10 pointer-events-none" />
      
      {/* Top Header */}
      <header className="flex justify-between items-center z-10">
        <div className="flex items-center gap-3">
          <Disc className="w-8 h-8 text-accent animate-spin-slow" />
          <span className="font-heading text-xl font-bold tracking-tight select-none">EQ_MUSIC</span>
        </div>
        <button
          onClick={handleLogin}
          className="group flex items-center gap-1.5 px-5 py-2.5 bg-surface border border-border text-xs uppercase tracking-wider font-semibold rounded hover:bg-surface-2 hover:border-accent transition-all duration-300"
        >
          Enter Dashboard
          <ArrowUpRight className="w-4 h-4 text-muted group-hover:text-accent group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-all" />
        </button>
      </header>

      {/* Hero Content Section - Asymmetric Grid Layout */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center my-auto py-12 md:py-24">
        {/* Left Column: Huge Diagonal Typography & Description */}
        <div className="lg:col-span-8 space-y-8 select-none">
          <h1 className="font-heading text-5xl sm:text-7xl md:text-8xl font-bold tracking-tighter leading-[0.9] flex flex-col skew-x-[-4deg]">
            <span className="text-muted uppercase text-xs sm:text-sm tracking-[0.2em] skew-x-[4deg] mb-4 font-mono font-normal">Premium Playback Orchestrator</span>
            <span>CONTROL YOUR</span>
            <span className="text-accent underline decoration-border decoration-[6px] underline-offset-[10px]">MUSIC</span>
            <span>IN REALTIME.</span>
          </h1>
          <p className="max-w-md font-mono text-sm text-muted leading-relaxed font-light">
            A premium, brutalist-inspired control dashboard for servers, channels, queues, and settings. Synchronized directly over lightning-fast websocket connections.
          </p>
        </div>

        {/* Right Column: Call to Action Panel */}
        <div className="lg:col-span-4 lg:pl-8 flex flex-col justify-center items-start">
          <div className="p-8 bg-surface border border-border rounded w-full space-y-6 relative hover:border-accent/40 transition-colors duration-300">
            <h3 className="font-heading text-lg font-semibold tracking-tight uppercase">Get Started</h3>
            <p className="font-mono text-xs text-muted font-light leading-relaxed">
              Authenticate securely with your Discord client to instantly sync with your active guilds. No configuration files required.
            </p>
            <button
              onClick={handleLogin}
              className="w-full py-4 bg-accent text-bg hover:bg-[#b0d52b] font-heading font-bold uppercase text-sm tracking-wider rounded transition-all duration-300 hover:shadow-[0_0_20px_rgba(200,241,53,0.3)]"
            >
              Connect Discord Account
            </button>
            <span className="block text-[10px] text-muted text-center font-mono font-light uppercase tracking-wider">
              Protected by Discord OAuth2 Secure Tunneling
            </span>
          </div>
        </div>
      </section>

      {/* Bottom Features Row - Minimal Editorial Grid */}
      <footer className="grid grid-cols-1 md:grid-cols-3 gap-8 pt-8 border-t border-border z-10">
        <div className="flex gap-4 items-start">
          <div className="p-2.5 bg-surface border border-border rounded text-accent">
            <Zap className="w-5 h-5" />
          </div>
          <div>
            <h4 className="font-heading text-sm uppercase font-bold tracking-wide">WebSockets Realtime</h4>
            <p className="font-mono text-xs text-muted font-light leading-relaxed mt-1">
              Zero-latency synchronization between Discord voice, track playback updates, and browser controls.
            </p>
          </div>
        </div>
        <div className="flex gap-4 items-start">
          <div className="p-2.5 bg-surface border border-border rounded text-accent">
            <Music className="w-5 h-5" />
          </div>
          <div>
            <h4 className="font-heading text-sm uppercase font-bold tracking-wide">Multi-Platform Integration</h4>
            <p className="font-mono text-xs text-muted font-light leading-relaxed mt-1">
              Instantly resolve Spotify links, YouTube queries, and SoundCloud tracks into unified play streams.
            </p>
          </div>
        </div>
        <div className="flex gap-4 items-start">
          <div className="p-2.5 bg-surface border border-border rounded text-accent">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <h4 className="font-heading text-sm uppercase font-bold tracking-wide">Strict Admin Controls</h4>
            <p className="font-mono text-xs text-muted font-light leading-relaxed mt-1">
              Enforce server DJ roles and blacklist query keyword rules directly from the web config panels.
            </p>
          </div>
        </div>
      </footer>
    </main>
  );
}
