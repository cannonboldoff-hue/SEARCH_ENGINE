"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import type { PersonSearchResult } from "@/types";

type PersonResultCardProps = {
  person: PersonSearchResult;
  searchId: string;
  index?: number;
};

export function PersonResultCard({ person, searchId, index = 0 }: PersonResultCardProps) {
  return (
    <motion.li
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, duration: 0.25 }}
    >
      <Link
        href={`/people/${person.id}?search_id=${searchId}`}
        className="flex items-center justify-between gap-3 rounded-lg border border-border p-4 transition-colors hover:bg-accent group"
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center flex-shrink-0">
            <span className="text-xs font-medium text-muted-foreground">
              {(person.display_name || "A").charAt(0).toUpperCase()}
            </span>
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-foreground truncate">
              {person.display_name || "Anonymous"}
            </p>
            <div className="flex gap-2 mt-0.5">
              {person.open_to_work && (
                <span className="text-xs text-success">Open to work</span>
              )}
              {person.open_to_contact && (
                <span className="text-xs text-info">Open to contact</span>
              )}
            </div>
          </div>
        </div>
        <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-foreground transition-colors flex-shrink-0" />
      </Link>
    </motion.li>
  );
}
