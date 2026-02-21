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
    .slice(0, 3);
  const whyFromMatchedCards = person.matched_cards
    .map((card) => card.title?.trim() || card.summary?.trim() || "")
    .filter(Boolean)
    .slice(0, 3);
  const whyShown =
    whyFromApi.length > 0
      ? whyFromApi
      : whyFromMatchedCards.length > 0
        ? whyFromMatchedCards
        : ["Matched your search intent and profile signals."];

  return (
    <motion.li
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, duration: 0.25 }}
      className="h-full"
    >
      <Link
        href={`/people/${person.id}?search_id=${searchId}`}
        className="flex h-full min-h-[44px] items-start justify-between gap-4 rounded-xl border border-border p-4 sm:p-6 transition-colors hover:bg-accent group active:bg-accent/80"
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-3 min-w-0">
            <div className="h-10 w-10 rounded-full bg-muted flex items-center justify-center flex-shrink-0">
              <span className="text-sm font-medium text-muted-foreground">
                {(person.name || "A").charAt(0).toUpperCase()}
              </span>
            </div>
            <div className="min-w-0">
              <p className="text-base font-semibold text-foreground truncate">
                {person.name || "Anonymous"}
              </p>
              {person.headline && (
                <p className="text-sm text-muted-foreground truncate mt-0.5">{person.headline}</p>
              )}
              <div className="flex gap-2 mt-0.5 flex-wrap">
                {person.open_to_contact && (
                  <span className="text-xs text-info">Open to contact</span>
                )}
              </div>
            </div>
          </div>
          <div className="mt-3 border-t border-border/60 pt-3 space-y-1">
            <p className="text-xs text-muted-foreground">
              <span className="font-medium text-foreground/90">Matched percentage:</span>{" "}
              {similarityPercent != null ? `${similarityPercent}%` : "N/A"}
            </p>
            <div className="text-xs text-muted-foreground">
              <p className="font-medium text-foreground/90">Why this card was shown:</p>
              <ul className="mt-1 list-disc pl-4 space-y-0.5">
                {whyShown.map((reason, idx) => (
                  <li key={`${person.id}-why-${idx}`} className="leading-snug">
                    {reason}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
        <ArrowRight className="h-5 w-5 text-muted-foreground group-hover:text-foreground transition-colors flex-shrink-0 mt-1" />
      </Link>
    </motion.li>
  );
}
