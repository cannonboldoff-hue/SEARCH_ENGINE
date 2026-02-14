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
  const similarityPercent =
    typeof person.similarity_percent === "number"
      ? Math.max(0, Math.min(100, Math.round(person.similarity_percent)))
      : null;

  const whyFromApi = (person.why_matched ?? [])
    .map((item) => item?.trim() || "")
    .filter(Boolean)
    .slice(0, 2);
  const whyFromMatchedCards = person.matched_cards
    .map((card) => card.title?.trim() || card.summary?.trim() || "")
    .filter(Boolean)
    .slice(0, 2);
  const whyShown =
    whyFromApi.length > 0
      ? whyFromApi.join(" | ")
      : whyFromMatchedCards.length > 0
        ? whyFromMatchedCards.join(" | ")
        : "Matched your search intent and profile signals.";

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
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-3 min-w-0">
            <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center flex-shrink-0">
              <span className="text-xs font-medium text-muted-foreground">
                {(person.name || "A").charAt(0).toUpperCase()}
              </span>
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium text-foreground truncate">
                {person.name || "Anonymous"}
              </p>
              {person.headline && (
                <p className="text-xs text-muted-foreground truncate mt-0.5">{person.headline}</p>
              )}
              <div className="flex gap-2 mt-0.5 flex-wrap">
                {person.open_to_work && (
                  <span className="text-xs text-success">Open to work</span>
                )}
                {person.open_to_contact && (
                  <span className="text-xs text-info">Open to contact</span>
                )}
              </div>
            </div>
          </div>
          <div className="mt-2 border-t border-border/60 pt-2 space-y-0.5">
            <p className="text-[11px] text-muted-foreground">
              <span className="font-medium text-foreground/90">Search/Profile similarity:</span>{" "}
              {similarityPercent != null ? `${similarityPercent}%` : "N/A"}
            </p>
            <p className="text-[11px] text-muted-foreground line-clamp-3">
              <span className="font-medium text-foreground/90">Why this card was shown:</span> {whyShown}
            </p>
          </div>
        </div>
        <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-foreground transition-colors flex-shrink-0 self-start mt-1" />
      </Link>
    </motion.li>
  );
}
