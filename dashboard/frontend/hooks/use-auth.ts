import { useEffect, useState } from "react";
import { authFetch, getAuthToken, clearAuthToken } from "../lib/auth-fetch";

export interface User {
  id: string;
  username: string;
  avatar: string;
  is_admin: boolean;
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    async function fetchUser() {
      const token = getAuthToken();
      if (!token) {
        setUser(null);
        setIsAdmin(false);
        setIsLoading(false);
        return;
      }

      try {
        const res = await authFetch("/api/v1/auth/me");
        if (res.ok) {
          const json = await res.json();
          if (json.success && json.data) {
            setUser(json.data);
            setIsAdmin(json.data.is_admin || false);
          } else {
            setUser(null);
            setIsAdmin(false);
          }
        } else {
          // Token is invalid or expired — clear it
          if (res.status === 401) {
            clearAuthToken();
          }
          setUser(null);
          setIsAdmin(false);
        }
      } catch (err) {
        console.error("Error fetching authenticated user info:", err);
        setUser(null);
        setIsAdmin(false);
      } finally {
        setIsLoading(false);
      }
    }
    fetchUser();
  }, []);

  return { user, isLoading, isAdmin };
}
