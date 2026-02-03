"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth";

export default function HomePage() {
  const { token } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (token) router.replace("/home");
    else router.replace("/login");
  }, [token, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="animate-pulse text-muted-foreground">Loading…</div>
    </div>
  );
}
