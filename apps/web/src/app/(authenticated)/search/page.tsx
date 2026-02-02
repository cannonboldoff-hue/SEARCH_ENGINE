"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { api, apiWithIdempotency } from "@/lib/api";
import { cn } from "@/lib/utils";

type PersonSearchResult = {
  id: string;
  display_name: string | null;
  open_to_work: boolean;
  open_to_contact: boolean;
};

type SearchResponse = {
  search_id: string;
  people: PersonSearchResult[];
};

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [openToWorkOnly, setOpenToWorkOnly] = useState(false);
  const [searchId, setSearchId] = useState<string | null>(null);
  const [people, setPeople] = useState<PersonSearchResult[]>([]);
  const [error, setError] = useState<string | null>(null);

  const { data: credits } = useQuery({
    queryKey: ["credits"],
    queryFn: () => api<{ balance: number }>("/me/credits"),
  });

  const searchMutation = useMutation({
    mutationFn: async (q: string) => {
      const idempotencyKey = `search-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      return apiWithIdempotency<SearchResponse>("/search", idempotencyKey, {
        method: "POST",
        body: { query: q, open_to_work_only: openToWorkOnly },
      });
    },
    onSuccess: (data) => {
      setSearchId(data.search_id);
      setPeople(data.people);
      setError(null);
    },
    onError: (e: Error) => {
      setError(e.message);
    },
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    searchMutation.mutate(query.trim());
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Search</h1>
      <p className="text-muted-foreground">
        Find people by what they&apos;ve done. Each search costs 1 credit. You have{" "}
        <span className="font-medium text-foreground">{credits?.balance ?? "—"} credits</span>.
      </p>

      <Card>
        <CardHeader>
          <CardTitle>Query</CardTitle>
          <CardDescription>
            e.g. &quot;someone who worked in Razorpay in backend team and now wants a job&quot;
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSearch} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="query">Search</Label>
              <Input
                id="query"
                placeholder="Describe who you're looking for..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="open_to_work"
                checked={openToWorkOnly}
                onChange={(e) => setOpenToWorkOnly(e.target.checked)}
                className="rounded border-input"
              />
              <Label htmlFor="open_to_work">Open to work only</Label>
            </div>
            {error && (
              <div className="text-sm text-destructive bg-destructive/10 rounded-md p-3">
                {error}
              </div>
            )}
            <Button type="submit" disabled={searchMutation.isPending || !query.trim()}>
              {searchMutation.isPending ? "Searching…" : "Search (1 credit)"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {searchId && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-4"
        >
          <h2 className="text-lg font-medium">Top 20 people</h2>
          {people.length === 0 ? (
            <p className="text-muted-foreground">No matches.</p>
          ) : (
            <ul className="grid gap-3">
              {people.map((person, i) => (
                <li key={person.id}>
                  <Link
                    href={`/people/${person.id}?search_id=${searchId}`}
                    className={cn(
                      "block rounded-lg border p-4 transition-colors hover:bg-accent/50"
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium">
                        {person.display_name || "Anonymous"}
                      </span>
                      <div className="flex gap-2 text-xs text-muted-foreground">
                        {person.open_to_work && (
                          <span className="rounded bg-green-100 px-2 py-0.5 text-green-800 dark:bg-green-900/30 dark:text-green-400">
                            Open to work
                          </span>
                        )}
                        {person.open_to_contact && (
                          <span className="rounded bg-blue-100 px-2 py-0.5 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
                            Open to contact
                          </span>
                        )}
                      </div>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </motion.div>
      )}
    </div>
  );
}
