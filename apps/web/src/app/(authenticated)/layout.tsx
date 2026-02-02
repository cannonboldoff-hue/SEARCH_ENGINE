"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth";
import { AppNav } from "@/components/app-nav";

export default function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { token } = useAuth();
  const router = useRouter();

  const hasToken = token !== null || (typeof window !== "undefined" && !!localStorage.getItem("token"));

  useEffect(() => {
    if (!hasToken) router.replace("/login");
  }, [hasToken, router]);

  if (!hasToken) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-muted-foreground">Loading…</div>
      </div>
    );
  }

  return (
    <>
      <AppNav />
      <main className="container mx-auto px-4 py-6">{children}</main>
    </>
  );
}
