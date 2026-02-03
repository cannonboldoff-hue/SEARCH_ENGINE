"use client";

import { motion, AnimatePresence } from "framer-motion";
import { PersonResultCard } from "./person-result-card";
import type { PersonSearchResult } from "@/types";

type SearchResultsProps = {
  searchId: string | null;
  people: PersonSearchResult[];
};

export function SearchResults({ searchId, people }: SearchResultsProps) {
  return (
    <AnimatePresence mode="wait">
      {searchId && (
        <motion.div
          key={searchId}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="space-y-4"
        >
          <h2 className="text-lg font-semibold">Results</h2>
          {people.length === 0 ? (
            <p className="text-muted-foreground py-8 text-center rounded-xl border border-dashed border-border/50">
              No matches. Try a different query or clear &quot;Open to work only&quot;.
            </p>
          ) : (
            <ul className="grid gap-3">
              {people.map((person, i) => (
                <PersonResultCard
                  key={person.id}
                  person={person}
                  searchId={searchId}
                  index={i}
                />
              ))}
            </ul>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
