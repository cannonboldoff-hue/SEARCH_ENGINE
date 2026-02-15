"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiWithIdempotency } from "@/lib/api";
import type { PersonSearchResult, SearchResponse } from "@/types";

type SearchContextValue = {
  query: string;
  setQuery: (q: string) => void;
  openToWorkOnly: boolean;
  setOpenToWorkOnly: (v: boolean) => void;
  searchId: string | null;
  people: PersonSearchResult[];
  error: string | null;
  setError: (m: string | null) => void;
  performSearch: () => void;
  isSearching: boolean;
};

const SearchContext = createContext<SearchContextValue | null>(null);

export function SearchProvider({ children }: { children: ReactNode }) {
  const [query, setQuery] = useState("");
  const [openToWorkOnly, setOpenToWorkOnly] = useState(false);
  const [searchId, setSearchId] = useState<string | null>(null);
  const [people, setPeople] = useState<PersonSearchResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const searchMutation = useMutation({
    mutationFn: async (q: string) => {
      const idempotencyKey = `search-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      return apiWithIdempotency<SearchResponse>("/search", idempotencyKey, {
        method: "POST",
        body: { query: q, open_to_work_only: openToWorkOnly },
      });
    },
    onMutate: () => {
      setError(null);
    },
    onSuccess: (data) => {
      setSearchId(data.search_id);
      setPeople(data.people);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["credits"] });
    },
    onError: (e: Error) => {
      setError(e.message);
    },
  });

  const performSearch = useCallback(() => {
    const q = query.trim();
    if (!q) return;
    searchMutation.mutate(q);
  }, [query, searchMutation]);

  const value = useMemo<SearchContextValue>(
    () => ({
      query,
      setQuery,
      openToWorkOnly,
      setOpenToWorkOnly,
      searchId,
      people,
      error,
      setError,
      performSearch,
      isSearching: searchMutation.isPending,
    }),
    [
      query,
      openToWorkOnly,
      searchId,
      people,
      error,
      performSearch,
      searchMutation.isPending,
    ]
  );

  return (
    <SearchContext.Provider value={value}>
      {children}
    </SearchContext.Provider>
  );
}

export function useSearch(): SearchContextValue {
  const ctx = useContext(SearchContext);
  if (!ctx) {
    return {
      query: "",
      setQuery: () => {},
      openToWorkOnly: false,
      setOpenToWorkOnly: () => {},
      searchId: null,
      people: [],
      error: null,
      setError: () => {},
      performSearch: () => {},
      isSearching: false,
    };
  }
  return ctx;
}
