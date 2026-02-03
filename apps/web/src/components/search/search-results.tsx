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
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ type: "spring", stiffness: 280, damping: 26 }}
          className="space-y-4"
        >
          <h2 className="text-lg font-semibold">Results</h2>
          {people.length === 0 ? (
            <motion.p
              className="text-muted-foreground py-8 text-center rounded-xl border border-dashed border-border/50"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.15 }}
            >
              No matches. Try a different query or clear &quot;Open to work only&quot;.
            </motion.p>
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
