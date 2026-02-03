"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { TiltCard } from "@/components/tilt-card";
import type { PersonSearchResult } from "@/types";

type PersonResultCardProps = {
  person: PersonSearchResult;
  searchId: string;
  index?: number;
};

export function PersonResultCard({ person, searchId, index = 0 }: PersonResultCardProps) {
  return (
    <motion.li
      initial={{ opacity: 0, y: 16, rotateX: -10 }}
      animate={{ opacity: 1, y: 0, rotateX: 0 }}
      transition={{
        delay: index * 0.05,
        type: "spring",
        stiffness: 280,
        damping: 24,
      }}
      style={{ transformStyle: "preserve-3d", perspective: 800 }}
    >
      <TiltCard
        maxTilt={5}
        scale={1.015}
        className="h-full"
      >
      <Link
        href={`/people/${person.id}?search_id=${searchId}`}
        className={cn(
          "block rounded-xl border border-border/50 p-4 transition-all duration-300",
          "bg-card/80 hover:bg-accent/30 hover-lift glow-ring hover:border-primary/30 depth-shadow"
        )}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="font-semibold text-foreground">
            {person.display_name || "Anonymous"}
          </span>
          <div className="flex gap-2 text-xs">
            {person.open_to_work && (
              <span className="rounded-md bg-emerald-500/20 px-2 py-1 text-emerald-400">
                Open to work
              </span>
            )}
            {person.open_to_contact && (
              <span className="rounded-md bg-blue-500/20 px-2 py-1 text-blue-400">
                Open to contact
              </span>
            )}
          </div>
        </div>
        <p className="text-sm text-muted-foreground mt-1">View profile →</p>
      </Link>
      </TiltCard>
    </motion.li>
  );
}
