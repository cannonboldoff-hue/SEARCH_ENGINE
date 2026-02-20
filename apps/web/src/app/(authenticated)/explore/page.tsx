"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Briefcase, ExternalLink, MapPin } from "lucide-react";
import { api } from "@/lib/api";
import { PageError, PageLoading } from "@/components/feedback";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { PersonListResponse } from "@/types";

export default function ExplorePage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["people", "explore"],
    queryFn: () => api<PersonListResponse>("/people"),
  });

  const people = data?.people ?? [];

  if (isLoading) {
    return <PageLoading message="Loading profiles..." />;
  }

  if (error) {
    return (
      <PageError
        message={error instanceof Error ? error.message : "Failed to load profiles."}
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
      className="max-w-6xl mx-auto space-y-6"
    >
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Explore</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Browse profiles that have visible experience cards.
        </p>
      </div>

      {people.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="py-12 text-center">
            <p className="text-sm text-muted-foreground">No profiles available yet.</p>
          </CardContent>
        </Card>
      ) : (
        <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {people.map((person, index) => (
            <motion.li
              key={person.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.02, duration: 0.22 }}
            >
              <Link href={`/people/${person.id}`} className="block h-full">
                <Card className="h-full transition-colors hover:bg-muted/40 hover:border-muted-foreground/20">
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <CardTitle className="text-base truncate">
                          {person.display_name || "Anonymous"}
                        </CardTitle>
                        {person.current_location && (
                          <p className="text-sm text-muted-foreground flex items-center gap-1.5 mt-1">
                            <MapPin className="h-3.5 w-3.5 flex-shrink-0" />
                            <span className="truncate">{person.current_location}</span>
                          </p>
                        )}
                      </div>
                      <ExternalLink className="h-4 w-4 text-muted-foreground flex-shrink-0 mt-0.5" />
                    </div>
                  </CardHeader>
                  <CardContent className="pt-0">
                    {person.experience_summaries.length > 0 ? (
                      <ul className="space-y-1">
                        {person.experience_summaries.slice(0, 4).map((summary, i) => (
                          <li
                            key={`${person.id}-${i}`}
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

