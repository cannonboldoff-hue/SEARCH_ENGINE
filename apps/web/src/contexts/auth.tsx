"use client";

import React, { createContext, useContext, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

type User = { id: string; email: string; display_name: string | null };

const AuthContext = createContext<{
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => void;
  setToken: (t: string | null) => void;
  refetchUser: () => Promise<void>;
} | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() =>
    typeof window !== "undefined" ? localStorage.getItem("token") : null
  );
  const [user, setUser] = useState<User | null>(null);
  const router = useRouter();

  const setToken = useCallback((t: string | null) => {
    if (typeof window !== "undefined") {
      if (t) localStorage.setItem("token", t);
      else localStorage.removeItem("token");
    }
    setTokenState(t);
    setUser(null);
  }, []);

  const refetchUser = useCallback(async () => {
    if (!token) return;
    try {
      const me = await api<{ id: string; email: string; display_name: string | null }>("/me");
      setUser(me);
    } catch {
      setToken(null);
    }
  }, [token, setToken]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const t = localStorage.getItem("token");
    setTokenState(t);
    if (t) {
      api<{ id: string; email: string; display_name: string | null }>("/me")
        .then(setUser)
        .catch(() => setToken(null));
    }
  }, [setToken]);

  const login = useCallback(
    async (email: string, password: string) => {
      const { access_token } = await api<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: { email, password },
      });
      setTokenState(access_token);
      if (typeof window !== "undefined") localStorage.setItem("token", access_token);
      const me = await api<{ id: string; email: string; display_name: string | null }>("/me");
      setUser(me);
      router.replace("/builder");
    },
    [router]
  );

  const signup = useCallback(
    async (email: string, password: string, displayName?: string) => {
      const { access_token } = await api<{ access_token: string }>("/auth/signup", {
        method: "POST",
        body: { email, password, display_name: displayName || null },
      });
      setTokenState(access_token);
      if (typeof window !== "undefined") localStorage.setItem("token", access_token);
      const me = await api<{ id: string; email: string; display_name: string | null }>("/me");
      setUser(me);
      router.replace("/builder");
    },
    [router]
  );

  const logout = useCallback(() => {
    setToken(null);
    router.push("/login");
  }, [router, setToken]);

  return (
    <AuthContext.Provider
      value={{ user, token, login, signup, logout, setToken, refetchUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
