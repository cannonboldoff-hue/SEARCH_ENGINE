"use client";

import Link from "next/link";
import { Coins } from "lucide-react";
import { useCredits } from "@/hooks";

export function CreditsBadge() {
  const { data: credits } = useCredits();
  return (
    <Link
      href="/credits"
      className="flex items-center gap-1.5 px-3 py-2 min-h-[44px] min-w-[44px] rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-colors"
    >
      <Coins className="h-3.5 w-3.5" />
      <span className="text-xs font-medium tabular-nums">
        {credits?.balance ?? "--"}
      </span>
      <span className="hidden text-xs sm:inline">credits</span>
    </Link>
  );
}
