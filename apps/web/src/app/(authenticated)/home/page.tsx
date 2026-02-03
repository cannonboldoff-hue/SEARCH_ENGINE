"use client";

import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { SearchHero } from "@/components/search-hero";
import { SearchResults } from "@/components/search";
import { ErrorMessage } from "@/components/error-message";
import { useSearch } from "@/contexts/search-context";

export default function HomePage() {
  const { searchId, people, error } = useSearch();

  return (
    <div className="relative min-h-[calc(100vh-3.5rem)]">
      {/* Huge 3D hero — alluding to discover people by experience */}
      <div className="relative mb-10">
        <SearchHero />
        <div
          className="relative z-10 max-w-3xl mx-auto -mt-32 sm:-mt-40 px-4 text-center space-y-2"
          style={{ transformStyle: "preserve-3d" }}
        >
          <motion.div
            initial={{ opacity: 0, y: 12, rotateX: -6 }}
            animate={{ opacity: 1, y: 0, rotateX: 0 }}
            transition={{ duration: 0.45 }}
            className="flex items-center justify-center gap-2 text-primary mb-2"
          >
            <motion.span
              animate={{ rotate: [0, 10, -10, 0], y: [0, -2, 0] }}
              transition={{ duration: 2.5, repeat: Infinity, repeatDelay: 2.5 }}
            >
              <Sparkles className="h-5 w-5" />
            </motion.span>
            <span className="text-sm font-medium">Trust-weighted search</span>
          </motion.div>
          <motion.h1
            className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl"
            initial={{ opacity: 0, y: 16, rotateX: -4 }}
            animate={{ opacity: 1, y: 0, rotateX: 0 }}
            transition={{ duration: 0.45, delay: 0.06 }}
          >
            Discover people by what they&apos;ve actually done
          </motion.h1>
          <motion.p
            className="text-muted-foreground mt-2 text-lg"
            initial={{ opacity: 0, y: 10, rotateX: -2 }}
            animate={{ opacity: 1, y: 0, rotateX: 0 }}
            transition={{ duration: 0.45, delay: 0.12 }}
          >
            Use the search bar above. Each search costs 1 credit.
          </motion.p>
        </div>
      </div>

      <motion.div
        className="space-y-6"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.25, duration: 0.4 }}
      >
        {error && <ErrorMessage message={error} />}
        <SearchResults searchId={searchId} people={people} />
      </motion.div>
    </div>
  );
}
