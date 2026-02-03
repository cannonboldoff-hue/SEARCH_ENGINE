"use client";

import { Coins } from "lucide-react";
import { useCredits } from "@/hooks";

export function CreditsBadge() {
  const { data: credits } = useCredits();
  return (
    <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-muted/80 border border-border/50">
      <Coins className="h-4 w-4 text-primary" />
      <span className="text-sm font-medium tabular-nums">
        {credits?.balance ?? "—"}
      </span>
      <span className="text-xs text-muted-foreground">credits</span>
    </div>
  );
}
