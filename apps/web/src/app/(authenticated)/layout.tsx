"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { SearchProvider } from "@/contexts/search-context";
import { AppNav } from "@/components/app-nav";

export default function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { token } = useAuth();
  const router = useRouter();
  const [hasToken, setHasToken] = useState<boolean | null>(null);

  useEffect(() => {
    const stored = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    const resolved = Boolean(token || stored);
    setHasToken(resolved);
    if (!resolved) router.replace("/login");
  }, [token, router]);

  if (hasToken !== true) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-background gap-3">
        <div className="h-5 w-5 rounded-full border-2 border-muted-foreground/30 border-t-foreground animate-spin" />
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <SearchProvider>
      <AppNav />
      <main className="container mx-auto px-4 py-6 min-h-[calc(100vh-3.5rem)]">
        {children}
      </main>
    </SearchProvider>
  );
}
