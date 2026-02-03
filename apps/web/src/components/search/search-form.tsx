"use client";

import { useMutation } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Search, Coins } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { apiWithIdempotency } from "@/lib/api";
import { useCredits } from "@/hooks";
import { ErrorMessage } from "@/components/error-message";
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
      initial={{ opacity: 0, y: 20, rotateX: -8 }}
      animate={{ opacity: 1, y: 0, rotateX: 0 }}
      transition={{ type: "spring", stiffness: 260, damping: 24 }}
      style={{ transformStyle: "preserve-3d", perspective: 1000 }}
    >
    <Card className="glass border-border/50 overflow-hidden glow-ring depth-shadow perspective-1000 transform-3d">
      <CardHeader className="pb-4">
        <CardTitle className="text-lg flex items-center gap-2">
          <motion.span
            animate={{ scale: [1, 1.1, 1] }}
            transition={{ duration: 1.5, repeat: Infinity, repeatDelay: 2 }}
          >
            <Search className="h-5 w-5 text-primary" />
          </motion.span>
          Search by intent
        </CardTitle>
        <CardDescription>
          e.g. &quot;Someone with 3+ years quant research, persistent mindset, and production experience&quot;
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSearch} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="query" className="sr-only">
              Search
            </Label>
            <Input
              id="query"
              placeholder="Describe who you're looking for..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="text-base bg-background/50 border-border/70 h-12"
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="open_to_work"
              checked={openToWorkOnly}
              onChange={(e) => setOpenToWorkOnly(e.target.checked)}
              className="rounded border-input bg-input accent-primary"
            />
            <Label htmlFor="open_to_work" className="text-sm cursor-pointer">
              Open to work only
            </Label>
          </div>
          {error && <ErrorMessage message={error} />}
          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="submit"
              size="lg"
              disabled={searchMutation.isPending || !query.trim()}
            >
              {searchMutation.isPending ? "Searching…" : "Search"}
            </Button>
            <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
              <Coins className="h-4 w-4 text-primary" />
              1 credit · You have{" "}
              <span className="font-semibold text-foreground tabular-nums">
                {credits?.balance ?? "—"}
              </span>{" "}
              credits
            </span>
          </div>
        </form>
      </CardContent>
    </Card>
    </motion.div>
  );
}
