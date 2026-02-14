"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { MapPin, Briefcase } from "lucide-react";
import { api } from "@/lib/api";
import { useSearch } from "@/contexts/search-context";
import { SearchResults } from "@/components/search";
import { ErrorMessage } from "@/components/feedback";
import type { PersonListItem } from "@/types";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

function PersonCard({ person }: { person: PersonListItem }) {
  const name = person.display_name || "Anonymous";
  const location = person.current_location || null;
  const summaries = person.experience_summaries?.slice(0, 5) ?? [];

  return (
    <Link href={`/people/${person.id}`} className="block h-full">
      <Card className="h-full transition-colors hover:bg-muted/50 hover:border-muted-foreground/20">
        <CardHeader className="pb-2">
          <h3 className="font-semibold text-foreground truncate" title={name}>
            {name}
          </h3>
          {location && (
            <p className="text-sm text-muted-foreground flex items-center gap-1.5 truncate">
              <MapPin className="h-3.5 w-3.5 flex-shrink-0" />
              {location}
            </p>
          )}
        </CardHeader>
        <CardContent className="pt-0">
          {summaries.length > 0 ? (
            <ul className="space-y-1">
              {summaries.map((summary, i) => (
                <li
                  key={i}
                  className="text-xs text-muted-foreground flex items-start gap-1.5"
                >
                  <Briefcase className="h-3 w-3 flex-shrink-0 mt-0.5" />
                  <span className="line-clamp-2">{summary}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-muted-foreground">No experience listed.</p>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}

export default function HomePage() {
  const { searchId, people: searchPeople, error: searchError } = useSearch();
  const { data, error, isLoading } = useQuery({
    queryKey: ["people"],
    queryFn: () => api<{ people: PersonListItem[] }>("/people"),
  });

  if (isLoading) {
    return (
      <div className="relative min-h-[calc(100vh-3.5rem)]">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 py-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Card key={i} className="h-full animate-pulse">
              <CardHeader className="pb-2">
                <div className="h-5 w-32 rounded bg-muted" />
                <div className="h-4 w-24 rounded bg-muted mt-2" />
              </CardHeader>
              <CardContent className="pt-0 space-y-2">
                <div className="h-3 w-full rounded bg-muted" />
                <div className="h-3 w-11/12 rounded bg-muted" />
                <div className="h-3 w-2/3 rounded bg-muted" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-8 text-center">
        <p className="text-sm text-destructive">
          {error instanceof Error ? error.message : "Failed to load people."}
        </p>
      </div>
    );
  }

  const people = data?.people ?? [];

  return (
    <div className="relative min-h-[calc(100vh-3.5rem)]">
      {searchId && (
        <div className="mb-6">
          {searchError && (
            <div className="mb-4">
              <ErrorMessage message={searchError} />
            </div>
          )}
          <SearchResults searchId={searchId} people={searchPeople} />
        </div>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 py-4">
        {people.length === 0 ? (
          <div className="col-span-full text-center py-16 text-muted-foreground text-sm">
            No people to show yet.
          </div>
        ) : (
          people.map((person) => (
            <PersonCard key={person.id} person={person} />
          ))
        )}
      </div>
    </div>
  );
}
