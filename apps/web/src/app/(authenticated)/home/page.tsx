"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { HeroBg } from "@/components/hero-bg";
import { SearchForm, SearchResults } from "@/components/search";
import type { PersonSearchResult, SearchResponse } from "@/types";

export default function HomePage() {
  const [query, setQuery] = useState("");
  const [openToWorkOnly, setOpenToWorkOnly] = useState(false);
  const [searchId, setSearchId] = useState<string | null>(null);
  const [people, setPeople] = useState<PersonSearchResult[]>([]);
  const [error, setError] = useState<string | null>(null);

  const handleSearchSuccess = (data: SearchResponse) => {
    setSearchId(data.search_id);
    setPeople(data.people);
    setError(null);
  };

  return (
    <div className="relative min-h-[calc(100vh-3.5rem)]">
      <div className="relative -mx-4 -mt-6 px-4 pt-8 pb-12 mb-8 overflow-hidden rounded-b-2xl perspective-1000">
        <HeroBg />
        <div className="relative z-10 max-w-3xl space-y-2" style={{ transformStyle: "preserve-3d" }}>
          <motion.div
            initial={{ opacity: 0, y: 12, rotateX: -6 }}
            animate={{ opacity: 1, y: 0, rotateX: 0 }}
            transition={{ duration: 0.45 }}
            className="flex items-center gap-2 text-primary mb-2"
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
            Describe who you&apos;re looking for in plain language. Each search costs 1 credit.
          </motion.p>
        </div>
      </div>

      <motion.div
        className="space-y-6"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.25, duration: 0.4 }}
      >
        <SearchForm
          query={query}
          setQuery={setQuery}
          openToWorkOnly={openToWorkOnly}
          setOpenToWorkOnly={setOpenToWorkOnly}
          error={error}
          onSuccess={handleSearchSuccess}
          onError={setError}
        />
        <SearchResults searchId={searchId} people={people} />
      </motion.div>
    </div>
  );
}
