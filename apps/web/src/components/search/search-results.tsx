"use client";

import { useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { LockOpen } from "lucide-react";
import { PersonResultCard } from "./person-result-card";
import { useSearch } from "@/contexts/search-context";
import { Button } from "@/components/ui/button";
import type { PersonSearchResult } from "@/types";

type SearchResultsProps = {
  searchId: string | null;
  people: PersonSearchResult[];
};

export function SearchResults({ searchId, people }: SearchResultsProps) {
  const { loadMore, isLoadingMore, hasMore } = useSearch();

  const sortedPeople = useMemo(() => {
    return people
      .map((person, index) => ({ person, index }))
      .sort((a, b) => {
        const aSimilarity =
          typeof a.person.similarity_percent === "number" ? a.person.similarity_percent : -1;
        const bSimilarity =
          typeof b.person.similarity_percent === "number" ? b.person.similarity_percent : -1;
        if (bSimilarity !== aSimilarity) return bSimilarity - aSimilarity;
        return a.index - b.index;
      })
      .map(({ person }) => person);
  }, [people]);

  return (
    <AnimatePresence mode="wait">
      {searchId && (
        <motion.div
          key={searchId}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="space-y-4"
        >
          <h2 className="text-sm font-medium text-muted-foreground">
            {people.length} {people.length === 1 ? "result" : "results"}
          </h2>
          {people.length === 0 ? (
            <p className="text-muted-foreground py-12 text-center text-sm rounded-lg border border-dashed border-border">
              {'No matches. Try a different query or clear "Open to work only".'}
            </p>
          ) : (
            <>
              <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {sortedPeople.map((person, i) => (
                  <PersonResultCard
                    key={person.id}
                    person={person}
                    searchId={searchId}
                    index={i}
                  />
                ))}
              </ul>
              {hasMore && (
                <div className="flex justify-center pt-4 pb-2">
                  <Button
                    variant="outline"
                    onClick={() => loadMore()}
                    disabled={isLoadingMore}
                    className="gap-2"
                  >
                    {isLoadingMore ? (
                      <span className="h-4 w-4 rounded-full border-2 border-current border-t-transparent animate-spin" />
                    ) : (
                      <LockOpen className="h-4 w-4" />
                    )}
                    Unlock more profiles
                  </Button>
                </div>
              )}
            </>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
