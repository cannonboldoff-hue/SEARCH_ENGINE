"use client";

import Link from "next/link";
import { Coins } from "lucide-react";
import { useCredits } from "@/hooks";

export function CreditsBadge() {
  const { data: credits } = useCredits();
  return (
    <Link
      href="/credits"
      className="flex items-center gap-1.5 px-2 py-1 rounded-md text-muted-foreground hover:text-foreground transition-colors"
    >
      <Coins className="h-3.5 w-3.5" />
      <span className="text-xs font-medium tabular-nums">
        {credits?.balance ?? "--"}
      </span>
    </Link>
  );
}
