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
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="space-y-3"
        >
          <h2 className="text-sm font-medium text-muted-foreground">
            {people.length} {people.length === 1 ? "result" : "results"}
          </h2>
          {people.length === 0 ? (
            <p className="text-muted-foreground py-12 text-center text-sm rounded-lg border border-dashed border-border">
              {'No matches. Try a different query or clear "Open to work only".'}
            </p>
          ) : (
            <ul className="grid grid-cols-1 gap-3 md:grid-cols-3">
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
