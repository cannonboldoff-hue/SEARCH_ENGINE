"use client";

import { Suspense, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { getPostAuthPath, isPathAllowedForStep } from "@/lib/auth-flow";
import { SearchProvider } from "@/contexts/search-context";
import { AppNav } from "@/components/app-nav";
import { SidebarWidthProvider, useSidebarWidth } from "@/contexts/sidebar-width-context";

import type { ReactNode } from "react";

export default function AuthenticatedLayout({
  children,
}: {
  children: ReactNode;
}) {
  const { isAuthenticated, onboardingStep, isAuthLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const requiredPath = getPostAuthPath(onboardingStep);
  const routeAllowed = isPathAllowedForStep(pathname, onboardingStep);

  useEffect(() => {
    if (isAuthLoading) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    if (onboardingStep != null && !routeAllowed) {
      router.replace(requiredPath);
    }
  }, [isAuthLoading, isAuthenticated, onboardingStep, requiredPath, routeAllowed, router]);

  if (isAuthLoading || !isAuthenticated || !routeAllowed) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-background gap-3">
        <div className="h-5 w-5 rounded-full border-2 border-muted-foreground/30 border-t-foreground animate-spin" />
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <SearchProvider>
      <SidebarWidthProvider>
        <AuthenticatedLayoutBody>{children}</AuthenticatedLayoutBody>
      </SidebarWidthProvider>
    </SearchProvider>
  );
}

function AuthenticatedLayoutBody({ children }: { children: ReactNode }) {
  const { sidebarWidth } = useSidebarWidth();

  return (
    <div className="overflow-x-hidden">
      <Suspense fallback={null}>
        <AppNav />
      </Suspense>
      <div style={{ paddingLeft: sidebarWidth }} className="min-w-0 overflow-x-hidden">
        <main className="container mx-auto px-4 py-6 min-h-[calc(100vh-3.5rem)] max-w-full overflow-x-hidden">
          {children}
        </main>
      </div>
    </div>
  );
}
