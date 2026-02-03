"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function SettingsPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/builder");
  }, [router]);

  return (
    <div className="py-8 flex justify-center">
      <div className="animate-pulse text-muted-foreground">Redirecting to Builder…</div>
    </div>
  );
}
