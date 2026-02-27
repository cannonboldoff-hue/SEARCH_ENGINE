"use client";

import { createContext, useContext, useCallback, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import type { OnboardingStep } from "@/lib/auth-flow";

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

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>({ id: "demo", email: "demo@example.com", display_name: "Demo User" });
  const [onboardingStep, setOnboardingStepState] = useState<OnboardingStep | null>(null);
  const router = useRouter();

  const setOnboardingStep = useCallback((step: OnboardingStep | null) => {
    setOnboardingStepState(step);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      setUser({ id: "demo", email, display_name: "Demo User" });
      router.replace("/home");
    },
    [router]
  );

  const signup = useCallback(
    async (payload: { email: string; password: string; displayName?: string }) => {
      setUser({ id: "demo", email: payload.email, display_name: payload.displayName ?? "Demo User" });
      router.replace("/home");
      return { emailVerificationRequired: false };
    },
    [router]
  );

  const logout = useCallback(() => {
    setUser(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider
      value={{
        user,
        onboardingStep,
        isAuthLoading: false,
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
