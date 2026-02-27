"use client";

import { Suspense } from "react";
import { SearchProvider } from "@/contexts/search-context";
import { AppNav } from "@/components/app-nav";
import { SidebarWidthProvider, useSidebarWidth } from "@/contexts/sidebar-width-context";

import type { ReactNode } from "react";

export default function AuthenticatedLayout({
  children,
}: {
  children: ReactNode;
}) {
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
        <main className="container mx-auto px-3 sm:px-4 py-4 sm:py-6 min-h-[calc(100vh-3.5rem)] max-w-full overflow-x-hidden">
          {children}
        </main>
      </div>
    </div>
  );
}
