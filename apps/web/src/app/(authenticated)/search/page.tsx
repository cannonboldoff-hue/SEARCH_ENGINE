"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function SearchPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/home");
  }, [router]);
  return (
    <div className="min-h-[40vh] flex items-center justify-center">
      <div className="animate-pulse text-muted-foreground">Redirecting to Home…</div>
    </div>
  );
}
