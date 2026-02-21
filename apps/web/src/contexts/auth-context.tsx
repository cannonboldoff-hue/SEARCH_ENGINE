"use client";

import { createContext, useContext, useCallback, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import {
  AUTH_TOKEN_KEY,
  getPostAuthPath,
  ONBOARDING_STEP_KEY,
  PENDING_ONBOARDING_STEP_KEY,
  readPendingOnboardingStep,
  setPendingOnboardingStep,
  type OnboardingStep,
} from "@/lib/auth-flow";

type User = { id: string; email: string; display_name: string | null };
const AuthContext = createContext<{
  user: User | null;
  onboardingStep: OnboardingStep | null;
  isAuthLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (payload: { email: string; password: string; displayName?: string }) => Promise<{ emailVerificationRequired: boolean }>;
  logout: () => void;
  setOnboardingStep: (step: OnboardingStep | null) => void;
} | null>(null);

function readToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

function readOnboardingStep(): OnboardingStep | null {
  if (typeof window === "undefined") return null;
  const step = localStorage.getItem(ONBOARDING_STEP_KEY);
  return step === "bio" || step === "builder" ? step : null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => readToken());
  const [user, setUser] = useState<User | null>(null);
  const [onboardingStep, setOnboardingStepState] = useState<OnboardingStep | null>(() =>
    readOnboardingStep()
  );
  const [isAuthLoading, setIsAuthLoading] = useState<boolean>(() => !!readToken());
  const router = useRouter();

  const clearSession = useCallback(() => {
    if (typeof window !== "undefined") {
      localStorage.removeItem(AUTH_TOKEN_KEY);
      localStorage.removeItem(ONBOARDING_STEP_KEY);
      localStorage.removeItem(PENDING_ONBOARDING_STEP_KEY);
    }
    setToken(null);
    setUser(null);
    setOnboardingStepState(null);
    setIsAuthLoading(false);
  }, []);

  const startSession = useCallback((nextToken: string, step: OnboardingStep | null) => {
    if (typeof window !== "undefined") {
      localStorage.setItem(AUTH_TOKEN_KEY, nextToken);
      if (step) localStorage.setItem(ONBOARDING_STEP_KEY, step);
      else localStorage.removeItem(ONBOARDING_STEP_KEY);
    }
    setToken(nextToken);
    setUser(null);
    setOnboardingStepState(step);
    setIsAuthLoading(true);
  }, []);

  const setOnboardingStep = useCallback((step: OnboardingStep | null) => {
    if (typeof window !== "undefined") {
      if (step) localStorage.setItem(ONBOARDING_STEP_KEY, step);
      else localStorage.removeItem(ONBOARDING_STEP_KEY);
    }
    setOnboardingStepState(step);
  }, []);

  useEffect(() => {
    if (!token) {
      setUser(null);
      setIsAuthLoading(false);
      return;
    }
    let isMounted = true;
    setIsAuthLoading(true);
    api<{ id: string; email: string; display_name: string | null }>("/me")
      .then((me) => {
        if (!isMounted) return;
        setUser(me);
      })
      .catch(() => {
        if (!isMounted) return;
        clearSession();
      })
      .finally(() => {
        if (!isMounted) return;
        setIsAuthLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, [token, clearSession]);

  const login = useCallback(
    async (email: string, password: string) => {
      const { access_token } = await api<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: { email, password },
      });
      const pendingStep = readPendingOnboardingStep();
      startSession(access_token, pendingStep ?? null);
      setPendingOnboardingStep(null);
      router.replace("/home");
    },
    [router, startSession]
  );

  const signup = useCallback(
    async (payload: { email: string; password: string; displayName?: string }) => {
      const res = await api<{ access_token?: string | null; email_verification_required: boolean }>("/auth/signup", {
        method: "POST",
        body: {
          email: payload.email,
          password: payload.password,
          display_name: payload.displayName ?? null,
        },
      });
      if (res?.access_token) {
        const pendingStep = readPendingOnboardingStep();
        startSession(res.access_token, pendingStep ?? "bio");
        setPendingOnboardingStep(null);
        router.replace(getPostAuthPath(pendingStep ?? "bio"));
        return { emailVerificationRequired: false };
      }
      setPendingOnboardingStep("bio");
      return { emailVerificationRequired: res?.email_verification_required ?? true };
    },
    [router, startSession]
  );

  const logout = useCallback(() => {
    clearSession();
    router.push("/login");
  }, [router, clearSession]);

  return (
    <AuthContext.Provider
      value={{
        user,
        onboardingStep,
        isAuthLoading,
        isAuthenticated: Boolean(user),
        login,
        signup,
        logout,
        setOnboardingStep,
      }}
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
