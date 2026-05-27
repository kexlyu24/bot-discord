"use client";

import { useEffect } from "react";
import { Disc } from "lucide-react";

export default function LoginPage() {
  useEffect(() => {
    async function performRedirect() {
      try {
        const res = await fetch("/api/v1/auth/login");
        if (res.ok) {
          const json = await res.json();
          if (json.success && json.data?.url) {
            window.location.href = json.data.url;
            return;
          }
        }
      } catch (err) {
        console.error("Failed to perform Discord OAuth redirect:", err);
      }
    }
    performRedirect();
  }, []);

  return (
    <main className="min-h-screen bg-bg text-text flex flex-col justify-center items-center gap-4 select-none">
      <Disc className="w-10 h-10 text-accent animate-spin-slow" />
      <span className="font-mono text-xs uppercase tracking-widest text-muted">
        Establishing Discord Connection...
      </span>
    </main>
  );
}
