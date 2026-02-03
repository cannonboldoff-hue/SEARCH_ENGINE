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
      <div className="relative -mx-4 -mt-6 px-4 pt-8 pb-12 mb-8 overflow-hidden rounded-b-2xl">
        <HeroBg />
        <div className="relative z-10 max-w-3xl">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="flex items-center gap-2 text-primary mb-2"
          >
            <Sparkles className="h-5 w-5" />
            <span className="text-sm font-medium">Trust-weighted search</span>
          </motion.div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            Discover people by what they&apos;ve actually done
          </h1>
          <p className="text-muted-foreground mt-2 text-lg">
            Describe who you&apos;re looking for in plain language. Each search costs 1 credit.
          </p>
        </div>
      </div>

      <div className="space-y-6">
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
      </div>
    </div>
  );
}
