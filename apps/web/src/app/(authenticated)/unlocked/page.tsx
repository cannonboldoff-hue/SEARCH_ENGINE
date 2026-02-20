"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowLeft, Briefcase, ExternalLink, LockOpen, MapPin } from "lucide-react";
import { api } from "@/lib/api";
import type { UnlockedCardsResponse } from "@/types";
import { PageError, PageLoading } from "@/components/feedback";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function formatUnlockedAt(value: string | null): string {
  if (!value) return "Unlocked recently";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unlocked recently";
  return `Unlocked ${new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date)}`;
}

export default function UnlockedCardsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["me", "unlocked-cards"],
    queryFn: () => api<UnlockedCardsResponse>("/me/unlocked-cards"),
  });

  const cards = data?.cards ?? [];
  const sortedCards = useMemo(
    () =>
      [...cards].sort((a, b) => {
        const aTime = a.unlocked_at ? new Date(a.unlocked_at).getTime() : 0;
        const bTime = b.unlocked_at ? new Date(b.unlocked_at).getTime() : 0;
        return bTime - aTime;
      }),
    [cards]
  );

  if (isLoading) {
    return <PageLoading message="Loading unlocked cards..." />;
  }

  if (error) {
    return (
      <PageError
        message={error instanceof Error ? error.message : "Failed to load unlocked cards."}
        backHref="/home"
        backLabel="Back to CONXA"
      />
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="max-w-4xl mx-auto space-y-6"
    >
      <div>
        <Link
          href="/home"
          className="text-sm text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-1.5 group mb-4"
        >
          <ArrowLeft className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5" />
          Back to Search
        </Link>
        <h1 className="text-xl font-semibold tracking-tight">Unlocked cards</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Every person card you have unlocked appears here.
        </p>
      </div>

      {sortedCards.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="py-12 text-center">
            <LockOpen className="h-8 w-8 text-muted-foreground/40 mx-auto mb-3" />
            <p className="text-sm text-muted-foreground">
              No unlocked cards yet. Unlock contact details from search results to see cards here.
            </p>
          </CardContent>
        </Card>
      ) : (
        <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {sortedCards.map((card, index) => (
            <motion.li
              key={card.person_id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.03, duration: 0.22 }}
            >
              <Link
                href={`/people/${card.person_id}`}
                className="block h-full"
              >
                <Card className="h-full transition-colors hover:bg-muted/40 hover:border-muted-foreground/20">
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <CardTitle className="text-base truncate">
                          {card.display_name || "Anonymous"}
                        </CardTitle>
                        <p className="text-xs text-muted-foreground mt-1">
                          {formatUnlockedAt(card.unlocked_at)}
                        </p>
                      </div>
                      <ExternalLink className="h-4 w-4 text-muted-foreground flex-shrink-0 mt-0.5" />
                    </div>
                    {card.current_location && (
                      <p className="text-sm text-muted-foreground flex items-center gap-1.5 mt-1">
                        <MapPin className="h-3.5 w-3.5 flex-shrink-0" />
                        <span className="truncate">{card.current_location}</span>
                      </p>
                    )}
                  </CardHeader>
                  <CardContent className="pt-0 space-y-2">
                    <div className="flex gap-2 flex-wrap">
                      {card.open_to_work && (
                        <span className="inline-flex items-center rounded-md bg-success/10 px-2 py-0.5 text-xs font-medium text-success ring-1 ring-inset ring-success/20">
                          Open to work
                        </span>
                      )}
                      {card.open_to_contact && (
                        <span className="inline-flex items-center rounded-md bg-info/10 px-2 py-0.5 text-xs font-medium text-info ring-1 ring-inset ring-info/20">
                          Open to contact
                        </span>
                      )}
                    </div>
                    {card.experience_summaries.length > 0 ? (
                      <ul className="space-y-1">
                        {card.experience_summaries.slice(0, 3).map((summary, i) => (
                          <li
                            key={`${card.person_id}-${i}`}
                            className="text-xs text-muted-foreground flex items-start gap-1.5"
                          >
                            <Briefcase className="h-3 w-3 flex-shrink-0 mt-0.5" />
                            <span className="line-clamp-2">{summary}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-xs text-muted-foreground">No experience summary available.</p>
                    )}
                  </CardContent>
                </Card>
              </Link>
            </motion.li>
          ))}
        </ul>
      )}
    </motion.div>
  );
}
