"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, apiWithIdempotency } from "@/lib/api";
import { ErrorMessage } from "@/components/error-message";
import type { PersonProfile, ContactDetails } from "@/types";

export default function PersonProfilePage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const personId = params.id as string;
  const searchId = searchParams.get("search_id");
  const queryClient = useQueryClient();

  const { data: profile, error, isLoading } = useQuery({
    queryKey: ["person", personId, searchId],
    queryFn: () =>
      api<PersonProfile>(
        `/people/${personId}?search_id=${encodeURIComponent(searchId || "")}`
      ),
    enabled: !!personId && !!searchId,
  });

  const unlockMutation = useMutation({
    mutationFn: () => {
      const key = `unlock-${personId}-${searchId}-${Date.now()}`;
      return apiWithIdempotency<{ unlocked: boolean; contact: ContactDetails }>(
        `/people/${personId}/unlock-contact?search_id=${encodeURIComponent(searchId!)}`,
        key,
        { method: "POST" }
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["person", personId, searchId] });
    },
  });

  if (!searchId) {
    return (
      <div className="py-12 text-center max-w-md mx-auto space-y-4">
        <p className="text-muted-foreground">
          This profile must be opened from a search result so we can track your credit usage.
        </p>
        <Link
          href="/home"
          className="inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          Back to Discover
        </Link>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="py-8 flex justify-center">
        <div className="animate-pulse text-muted-foreground">Loading profile…</div>
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="py-8 text-center text-destructive">
        {error instanceof Error ? error.message : "Failed to load profile"}
      </div>
    );
  }

  const contactUnlocked = !!profile.contact;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-3xl mx-auto space-y-6"
    >
      <div className="mb-4">
        <Link
          href="/home"
          className="text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          ← Back to Discover
        </Link>
      </div>
      <Card className="glass border-border/50 overflow-hidden">
        <CardHeader>
          <CardTitle className="text-xl">
            {profile.display_name || "Anonymous"}
          </CardTitle>
          <div className="flex gap-2 text-sm text-muted-foreground">
            {profile.open_to_work && (
              <span className="rounded bg-green-100 px-2 py-0.5 text-green-800 dark:bg-green-900/30 dark:text-green-400">
                Open to work
              </span>
            )}
            {profile.open_to_contact && (
              <span className="rounded bg-blue-100 px-2 py-0.5 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
                Open to contact
              </span>
            )}
          </div>
          {profile.open_to_work && (
            <p className="text-sm">
              Locations: {profile.work_preferred_locations?.length ? profile.work_preferred_locations.join(", ") : "—"}
              {profile.work_preferred_salary_min != null && (
                <> · Salary: {profile.work_preferred_salary_min}
                  {profile.work_preferred_salary_max != null ? `–${profile.work_preferred_salary_max}` : ""}
                </>
              )}
            </p>
          )}
        </CardHeader>
      </Card>

      <div>
        <h2 className="text-lg font-semibold mb-3">Experience cards</h2>
        <ul className="space-y-4">
          {profile.experience_cards.map((card) => (
            <Card key={card.id} className="glass border-border/50 hover-lift">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">
                  {card.title || card.company || "Untitled"}
                </CardTitle>
                <p className="text-sm text-muted-foreground">
                  {[card.company, card.team, card.role_title, card.time_range]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                {card.context && <p>{card.context}</p>}
                {card.constraints && <p><strong>Constraints:</strong> {card.constraints}</p>}
                {card.decisions && <p><strong>Decisions:</strong> {card.decisions}</p>}
                {card.outcome && <p><strong>Outcome:</strong> {card.outcome}</p>}
                {card.tags?.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {card.tags.map((t, i) => (
                      <span key={`${t}-${i}`} className="rounded bg-muted px-2 py-0.5 text-xs">
                        {t}
                      </span>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </ul>
      </div>

      <Card className="glass border-border/50 overflow-hidden">
        <CardHeader>
          <CardTitle className="text-base">Contact</CardTitle>
        </CardHeader>
        <CardContent>
          {contactUnlocked ? (
            <div className="space-y-2 text-sm">
              {profile.contact?.email_visible && <p>Email: (visible to you)</p>}
              {profile.contact?.phone && <p>Phone: {profile.contact.phone}</p>}
              {profile.contact?.linkedin_url && (
                <a
                  href={profile.contact.linkedin_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  LinkedIn
                </a>
              )}
              {profile.contact?.other && <p>{profile.contact.other}</p>}
            </div>
          ) : profile.open_to_contact ? (
            <div>
              <p className="text-muted-foreground text-sm mb-2">
                Unlock contact for 1 credit.
              </p>
              <Button
                onClick={() => unlockMutation.mutate()}
                disabled={unlockMutation.isPending}
              >
                {unlockMutation.isPending ? "Unlocking…" : "Unlock contact (1 credit)"}
              </Button>
              {unlockMutation.isError && (
                <div className="mt-2">
                  <ErrorMessage
                    message={
                      unlockMutation.error instanceof Error
                        ? unlockMutation.error.message
                        : "Failed"
                    }
                  />
                </div>
              )}
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">
              This person is not open to contact.
            </p>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}
