"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { getPostAuthPath } from "@/lib/auth-flow";
import { LoadingScreen } from "@/components/feedback";

export default function RootPage() {
  const { isAuthenticated, isAuthLoading, onboardingStep } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isAuthLoading) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    router.replace(getPostAuthPath(onboardingStep));
  }, [isAuthenticated, isAuthLoading, onboardingStep, router]);

  return <LoadingScreen />;
}
