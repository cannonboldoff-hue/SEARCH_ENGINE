"use client";

import { useMutation } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Search, Coins } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { apiWithIdempotency } from "@/lib/api";
import { useCredits } from "@/hooks";
import { ErrorMessage } from "@/components/feedback";
import type { SearchResponse } from "@/types";

type SearchFormProps = {
  query: string;
  setQuery: (q: string) => void;
  openToWorkOnly: boolean;
  setOpenToWorkOnly: (v: boolean) => void;
  error: string | null;
  onSuccess: (data: SearchResponse) => void;
  onError: (message: string) => void;
};

export function SearchForm({
  query,
  setQuery,
  openToWorkOnly,
  setOpenToWorkOnly,
  error,
  onSuccess,
  onError,
}: SearchFormProps) {
  const { data: credits } = useCredits();

  const searchMutation = useMutation({
    mutationFn: async (q: string) => {
      const idempotencyKey = `search-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      return apiWithIdempotency<SearchResponse>("/search", idempotencyKey, {
        method: "POST",
        body: { query: q, open_to_work_only: openToWorkOnly },
      });
    },
    onSuccess: (data) => {
      onSuccess(data);
    },
    onError: (e: Error) => {
      onError(e.message);
    },
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    searchMutation.mutate(query.trim());
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Search className="h-4 w-4 text-muted-foreground" />
            Search by intent
          </CardTitle>
          <CardDescription>
            {'e.g. "Someone with 3+ years quant research, persistent mindset, and production experience"'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSearch} className="space-y-3">
            <div>
              <Label htmlFor="query" className="sr-only">
                Search
              </Label>
              <input
                id="query"
                type="text"
                placeholder="Describe who you're looking for..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="flex h-11 min-h-[44px] w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/20 focus-visible:border-foreground/30 transition-colors"
              />
            </div>
            <label className="flex items-center gap-2 min-h-[44px] cursor-pointer text-muted-foreground touch-manipulation">
              <input
                type="checkbox"
                id="open_to_work"
                checked={openToWorkOnly}
                onChange={(e) => setOpenToWorkOnly(e.target.checked)}
                className="rounded border-border accent-foreground h-4 w-4 shrink-0"
              />
              <span className="text-sm">Open to work only</span>
            </label>
            {error && <ErrorMessage message={error} />}
            <div className="flex flex-wrap items-center gap-3">
              <Button
                type="submit"
                disabled={searchMutation.isPending || !query.trim()}
              >
                {searchMutation.isPending ? "Searching..." : "Search"}
              </Button>
              <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                <Coins className="h-3.5 w-3.5" />
                1 credit per card shown (e.g. "give me 2 cards" → 2 credits)
                <span className="text-foreground font-medium tabular-nums">
                  ({credits?.balance ?? "--"} remaining)
                </span>
              </span>
            </div>
          </form>
        </CardContent>
      </Card>
    </motion.div>
  );
}
