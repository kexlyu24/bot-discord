"use client";

import { useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Disc } from "lucide-react";
import { setAuthToken } from "../../../lib/auth-fetch";

export default function AuthCallbackPage() {
  const searchParams = useSearchParams();
  const router = useRouter();

  useEffect(() => {
    const token = searchParams.get("token");
    const error = searchParams.get("error");

    if (error) {
      console.error("[Auth] OAuth callback error:", error);
      router.replace(`/login?error=${error}`);
      return;
    }

    if (token) {
      setAuthToken(token);
      router.replace("/dashboard");
    } else {
      console.error("[Auth] No token in callback URL");
      router.replace("/login?error=no_token");
    }
  }, [searchParams, router]);

  return (
    <main className="min-h-screen bg-bg text-text flex flex-col justify-center items-center gap-4 select-none">
      <Disc className="w-10 h-10 text-accent animate-spin-slow" />
      <span className="font-mono text-xs uppercase tracking-widest text-muted">
        Authenticating...
      </span>
    </main>
  );
}
