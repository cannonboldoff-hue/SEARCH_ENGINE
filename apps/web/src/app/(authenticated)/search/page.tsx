"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Search, Coins } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { apiWithIdempotency } from "@/lib/api";
import { useCredits } from "@/hooks";
import { SearchResults } from "@/components/search";
import { ErrorMessage } from "@/components/feedback";
import { INDIA_CITIES } from "@/lib/india-cities";
import type { PersonSearchResult, SearchResponse } from "@/types";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [openToWorkOnly, setOpenToWorkOnly] = useState(false);
  const [preferredLocations, setPreferredLocations] = useState<string[]>([]);
  const [salaryMin, setSalaryMin] = useState<string>("");
  const [salaryMax, setSalaryMax] = useState<string>("");
  const [searchId, setSearchId] = useState<string | null>(null);
  const [people, setPeople] = useState<PersonSearchResult[]>([]);
  const [error, setError] = useState<string | null>(null);

  const queryClient = useQueryClient();
  const { data: credits } = useCredits();

  const searchMutation = useMutation({
    mutationFn: async () => {
      const idempotencyKey = `search-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      const body: {
        query: string;
        open_to_work_only: boolean;
        preferred_locations?: string[];
        salary_min?: number;
        salary_max?: number;
      } = {
        query: query.trim(),
        open_to_work_only: openToWorkOnly,
      };
      if (openToWorkOnly) {
        if (preferredLocations.length) body.preferred_locations = preferredLocations;
        const min = salaryMin.trim() ? Number(salaryMin) : undefined;
        const max = salaryMax.trim() ? Number(salaryMax) : undefined;
        if (min != null && !Number.isNaN(min)) body.salary_min = min;
        if (max != null && !Number.isNaN(max)) body.salary_max = max;
      }
      return apiWithIdempotency<SearchResponse>("/search", idempotencyKey, {
        method: "POST",
        body,
      });
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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    searchMutation.mutate();
  };

  const addLocation = (loc: string) => {
    if (loc && !preferredLocations.includes(loc)) {
      setPreferredLocations((prev) => [...prev, loc]);
    }
  };

  const removeLocation = (loc: string) => {
    setPreferredLocations((prev) => prev.filter((l) => l !== loc));
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="max-w-2xl mx-auto space-y-6"
    >
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Search className="h-4 w-4 text-muted-foreground" />
            Search by intent
          </CardTitle>
          <CardDescription>
            e.g. &quot;Backend engineer with Go, 3+ years, open to work in Bangalore&quot;
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label htmlFor="query" className="sr-only">
                Search
              </Label>
              <Input
                id="query"
                type="text"
                placeholder="Describe who you're looking for..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full"
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="open_to_work"
                checked={openToWorkOnly}
                onChange={(e) => setOpenToWorkOnly(e.target.checked)}
                className="rounded border-border accent-foreground h-3.5 w-3.5"
              />
              <Label htmlFor="open_to_work" className="text-sm cursor-pointer text-muted-foreground">
                Open to work only
              </Label>
            </div>
            {openToWorkOnly && (
              <>
                <div>
                  <Label className="text-sm text-muted-foreground">Preferred locations (any)</Label>
                  <div className="flex flex-wrap gap-2 mt-1">
                    <select
                      className="rounded-md border border-border bg-background px-2 py-1.5 text-sm"
                      value=""
                      onChange={(e) => {
                        const v = e.target.value;
                        if (v) addLocation(v);
                      }}
                    >
                      <option value="">Add location...</option>
                      {INDIA_CITIES.map((c) => (
                        <option key={c} value={c} disabled={preferredLocations.includes(c)}>
                          {c}
                        </option>
                      ))}
                    </select>
                    {preferredLocations.map((loc) => (
                      <span
                        key={loc}
                        className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-0.5 text-xs"
                      >
                        {loc}
                        <button
                          type="button"
                          onClick={() => removeLocation(loc)}
                          className="text-muted-foreground hover:text-foreground"
                          aria-label={`Remove ${loc}`}
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label htmlFor="salary_min" className="text-sm text-muted-foreground">
                      Salary min (₹/year)
                    </Label>
                    <Input
                      id="salary_min"
                      type="number"
                      min={0}
                      placeholder="e.g. 800000"
                      value={salaryMin}
                      onChange={(e) => setSalaryMin(e.target.value)}
                      className="mt-0.5"
                    />
                  </div>
                  <div>
                    <Label htmlFor="salary_max" className="text-sm text-muted-foreground">
                      Salary max (₹/year)
                    </Label>
                    <Input
                      id="salary_max"
                      type="number"
                      min={0}
                      placeholder="e.g. 1500000"
                      value={salaryMax}
                      onChange={(e) => setSalaryMax(e.target.value)}
                      className="mt-0.5"
                    />
                  </div>
                </div>
              </>
            )}
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
                1 credit per search
                <span className="text-foreground font-medium tabular-nums">
                  ({credits?.balance ?? "--"} remaining)
                </span>
              </span>
            </div>
          </form>
        </CardContent>
      </Card>
      {searchId && (
        <SearchResults searchId={searchId} people={people} />
      )}
    </motion.div>
  );
}
