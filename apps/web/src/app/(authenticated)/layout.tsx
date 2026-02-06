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
    const storedToken = localStorage.getItem("token");
    setHasToken(Boolean(token || storedToken));
  }, [token]);

  useEffect(() => {
    if (hasToken === false) router.replace("/login");
  }, [hasToken, router]);

  if (hasToken !== true) {
    return (
      <div className="min-h-screen flex items-center justify-center mesh-bg">
        <div className="animate-pulse text-muted-foreground">Loading…</div>
      </div>
    );
  }

  return (
    <SearchProvider>
      <AppNav />
      <main className="container mx-auto px-4 py-6 min-h-[calc(100vh-3.5rem)] mesh-bg">
        {children}
      </main>
    </SearchProvider>
  );
}
