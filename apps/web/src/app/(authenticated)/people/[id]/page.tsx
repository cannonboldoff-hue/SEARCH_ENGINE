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
      <div className="py-16 text-center max-w-sm mx-auto space-y-4">
        <p className="text-sm text-muted-foreground">
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
      <div className="py-12 flex flex-col items-center justify-center gap-3">
        <div className="h-5 w-5 rounded-full border-2 border-muted-foreground/30 border-t-foreground animate-spin" />
        <p className="text-sm text-muted-foreground">Loading profile...</p>
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="py-12 text-center text-sm text-destructive">
        {error instanceof Error ? error.message : "Failed to load profile"}
      </div>
    );
  }

  const contactUnlocked = !!profile.contact;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="max-w-2xl mx-auto space-y-6"
    >
      <div className="mb-2">
        <Link
          href="/home"
          className="text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          {"<-"} Back to Discover
        </Link>
      </div>

      <Card>
        <CardHeader className="pb-4">
          <CardTitle className="text-lg">
            {profile.display_name || "Anonymous"}
          </CardTitle>
          <div className="flex gap-2 mt-1">
            {profile.open_to_work && (
              <span className="text-xs text-success font-medium">Open to work</span>
            )}
            {profile.open_to_contact && (
              <span className="text-xs text-info font-medium">Open to contact</span>
            )}
          </div>
          {profile.open_to_work && (
            <p className="text-xs text-muted-foreground mt-1">
              Locations: {profile.work_preferred_locations?.length ? profile.work_preferred_locations.join(", ") : "--"}
              {profile.work_preferred_salary_min != null && (
                <>{" / Salary: "}{profile.work_preferred_salary_min}
                  {profile.work_preferred_salary_max != null ? `- ${profile.work_preferred_salary_max}` : ""}
                </>
              )}
            </p>
          )}
        </CardHeader>
      </Card>

      <section>
        <h2 className="text-sm font-medium text-muted-foreground mb-3">Experience</h2>
        <ul className="space-y-2">
          {profile.experience_cards.map((card) => (
            <Card key={card.id}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">
                  {card.title || card.company_name || "Untitled"}
                </CardTitle>
                <p className="text-xs text-muted-foreground">
                  {[card.company_name, card.normalized_role, card.location, card.start_date, card.end_date]
                    .filter(Boolean)
                    .join(" / ")}
                </p>
              </CardHeader>
              <CardContent className="text-sm">
                {card.summary && <p className="text-muted-foreground">{card.summary}</p>}
              </CardContent>
            </Card>
          ))}
        </ul>
      </section>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium">Contact</CardTitle>
        </CardHeader>
        <CardContent>
          {contactUnlocked ? (
            <div className="space-y-1.5 text-sm">
              {profile.contact?.email_visible && <p className="text-foreground">Email: (visible to you)</p>}
              {profile.contact?.phone && <p className="text-foreground">Phone: {profile.contact.phone}</p>}
              {profile.contact?.linkedin_url && (
                <a
                  href={profile.contact.linkedin_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-foreground hover:underline"
                >
                  LinkedIn
                </a>
              )}
              {profile.contact?.other && <p className="text-muted-foreground">{profile.contact.other}</p>}
            </div>
          ) : profile.open_to_contact ? (
            <div>
              <p className="text-sm text-muted-foreground mb-3">
                Unlock contact details for 1 credit.
              </p>
              <Button
                size="sm"
                onClick={() => unlockMutation.mutate()}
                disabled={unlockMutation.isPending}
              >
                {unlockMutation.isPending ? "Unlocking..." : "Unlock contact (1 credit)"}
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
            <p className="text-sm text-muted-foreground">
              This person is not open to contact.
            </p>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}
