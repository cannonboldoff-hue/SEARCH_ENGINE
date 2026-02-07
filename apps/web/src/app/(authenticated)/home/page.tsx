"use client";

import { motion } from "framer-motion";
import { SearchResults } from "@/components/search";
import { ErrorMessage } from "@/components/error-message";
import { useSearch } from "@/contexts/search-context";

export default function HomePage() {
  const { searchId, people, error } = useSearch();

  return (
    <div className="relative min-h-[calc(100vh-3.5rem)]">
      {/* Hero section */}
      <div className="relative pt-12 pb-8 sm:pt-20 sm:pb-12">
        <div className="max-w-2xl mx-auto text-center">
          <motion.h1
            className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl text-balance"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
          >
            {"Discover people by what they've actually done"}
          </motion.h1>
          <motion.p
            className="text-muted-foreground mt-3 text-base leading-relaxed"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.08 }}
          >
            Use the search bar above. Each search costs 1 credit.
          </motion.p>
        </div>
      </div>

      <motion.div
        className="max-w-2xl mx-auto"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2, duration: 0.35 }}
      >
        {error && (
          <div className="mb-4">
            <ErrorMessage message={error} />
          </div>
        )}
        <SearchResults searchId={searchId} people={people} />
      </motion.div>
    </div>
  );
}
