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
import { api, apiWithIdempotency } from "@/lib/api";
import type { PersonSearchResult, SearchResponse } from "@/types";

type SearchMoreResponse = { people: PersonSearchResult[] };

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
  performSearchWithQuery: (q: string) => void;
  loadMore: () => Promise<void>;
  isSearching: boolean;
  isLoadingMore: boolean;
  hasMore: boolean;
};

const SearchContext = createContext<SearchContextValue | null>(null);

const LOAD_MORE_LIMIT = 6;

export function SearchProvider({ children }: { children: ReactNode }) {
  const [query, setQuery] = useState("");
  const [openToWorkOnly, setOpenToWorkOnly] = useState(false);
  const [searchId, setSearchId] = useState<string | null>(null);
  const [people, setPeople] = useState<PersonSearchResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
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
      setHasMore(data.people.length >= LOAD_MORE_LIMIT);
      queryClient.invalidateQueries({ queryKey: ["credits"] });
      queryClient.invalidateQueries({ queryKey: ["me", "searches"] });
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

  const performSearchWithQuery = useCallback(
    (q: string) => {
      const trimmed = q.trim();
      if (!trimmed) return;
      setQuery(trimmed);
      searchMutation.mutate(trimmed);
    },
    [searchMutation]
  );

  const loadMore = useCallback(async () => {
    if (!searchId || isLoadingMore || !hasMore) return;
    setIsLoadingMore(true);
    setError(null);
    try {
      const data = await api<SearchMoreResponse>(
        `/search/${searchId}/more?offset=${people.length}&limit=${LOAD_MORE_LIMIT}`
      );
      setPeople((prev) => [...prev, ...data.people]);
      setHasMore(data.people.length >= LOAD_MORE_LIMIT);
      queryClient.invalidateQueries({ queryKey: ["credits"] });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load more profiles");
    } finally {
      setIsLoadingMore(false);
    }
  }, [searchId, people.length, isLoadingMore, hasMore, queryClient]);

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
      performSearchWithQuery,
      loadMore,
      isSearching: searchMutation.isPending,
      isLoadingMore,
      hasMore,
    }),
    [
      query,
      openToWorkOnly,
      searchId,
      people,
      error,
      performSearch,
      performSearchWithQuery,
      loadMore,
      searchMutation.isPending,
      isLoadingMore,
      hasMore,
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
      performSearchWithQuery: () => {},
      loadMore: async () => {},
      isSearching: false,
      isLoadingMore: false,
      hasMore: false,
    };
  }
  return ctx;
}
