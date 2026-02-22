"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { Search } from "lucide-react";
import { api } from "@/lib/api";
import type { SavedSearchesResponse, PersonSearchResult } from "@/types";
import { PageError, PageLoading } from "@/components/feedback";
import { PersonResultCard } from "@/components/search/person-result-card";

/** Max results stored per search; fetch all at once when viewing history (no extra credits). */
const MAX_STORED_RESULTS = 24;

export default function SearchesPage() {
  return (
    <Suspense fallback={<PageLoading message="Loading search history..." />}>
      <SearchesPageContent />
    </Suspense>
  );
}

function SearchesPageContent() {
  const searchParams = useSearchParams();
  const selectedSearchId = searchParams.get("id");

  const { data: searchesData, isLoading: isLoadingSearches, error } = useQuery({
    queryKey: ["me", "searches"],
    queryFn: () => api<SavedSearchesResponse>("/me/searches?limit=200"),
  });

  const selectedSearch = searchesData?.searches?.find((s) => s.id === selectedSearchId);

  const { data: peopleData, isLoading: isLoadingResults } = useQuery({
    queryKey: ["search", selectedSearchId, "history"],
    queryFn: async () => {
      if (!selectedSearchId || !selectedSearch) return { people: [] };
      if (selectedSearch.result_count <= 0) return { people: [] };
      const limit = Math.min(MAX_STORED_RESULTS, selectedSearch.result_count);
      return api<{ people: PersonSearchResult[] }>(
        `/search/${selectedSearchId}/more?offset=0&limit=${limit}&history=true`
      );
    },
    enabled: !!selectedSearchId && !!selectedSearch && !selectedSearch.expired,
  });

  const people = peopleData?.people ?? [];

  if (isLoadingSearches) {
    return <PageLoading message="Loading search history..." />;
  }

  if (error) {
    return (
      <PageError
        message={error instanceof Error ? error.message : "Failed to load search history."}
        backHref="/home"
        backLabel="Back to Search"
      />
    );
  }

  return (
    <main className="min-w-0">
      <AnimatePresence mode="wait">
        {!selectedSearchId ? (
          <motion.div
            key="empty"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex flex-col items-center justify-center min-h-[50vh] px-6 text-center"
          >
            <Search className="h-14 w-14 text-muted-foreground/30 mb-4" />
            <p className="text-muted-foreground text-sm">
              Select a search from the sidebar to view its result profiles.
            </p>
            <Link
              href="/home"
              className="mt-4 text-sm font-medium text-primary hover:underline"
            >
              Go to Home
            </Link>
          </motion.div>
        ) : (
          <motion.div
            key={selectedSearchId}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="container max-w-6xl mx-auto px-4 py-6"
          >
            <div className="mb-4">
              <h3 className="text-sm font-medium text-foreground">
                {selectedSearch?.query_text ?? "Search results"}
              </h3>
              <p className="text-sm text-muted-foreground mt-0.5">
                {people.length} of {selectedSearch?.result_count ?? 0} profiles
              </p>
            </div>
            {isLoadingResults ? (
              <div className="flex items-center justify-center py-16">
                <span className="h-6 w-6 rounded-full border-2 border-muted-foreground/30 border-t-foreground animate-spin" />
              </div>
            ) : people.length === 0 ? (
              <p className="text-muted-foreground py-12 text-center text-sm rounded-lg border border-dashed border-border">
                {selectedSearch?.expired
                  ? "This search has expired."
                  : "No profiles in this search."}
              </p>
            ) : (
              <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {people.map((person, i) => (
                  <PersonResultCard
                    key={person.id}
                    person={person}
                    searchId={selectedSearchId}
                    index={i}
                  />
                ))}
              </ul>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}
