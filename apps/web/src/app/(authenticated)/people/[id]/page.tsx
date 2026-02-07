"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowLeft, Briefcase, Lock, Mail, MapPin, Phone, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageLoading } from "@/components/page-loading";
import { PageError } from "@/components/page-error";
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
        <Link href="/home">
          <Button>Back to Discover</Button>
        </Link>
      </div>
    );
  }

  if (isLoading) {
    return <PageLoading message="Loading profile..." />;
  }

  if (error || !profile) {
    return (
      <PageError
        message={error instanceof Error ? error.message : "Failed to load profile"}
        backHref="/home"
        backLabel="Back to Discover"
      />
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
      {/* Back link */}
      <Link
        href="/home"
        className="text-sm text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-1.5 group"
      >
        <ArrowLeft className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5" />
        Back to Discover
      </Link>

      {/* Profile header */}
      <Card>
        <CardHeader className="pb-4">
          <div className="flex items-start justify-between">
            <div>
              <CardTitle className="text-lg">
                {profile.display_name || "Anonymous"}
              </CardTitle>
              <div className="flex flex-wrap gap-2 mt-2">
                {profile.open_to_work && (
                  <span className="inline-flex items-center rounded-md bg-success/10 px-2 py-0.5 text-xs font-medium text-success ring-1 ring-inset ring-success/20">
                    Open to work
                  </span>
                )}
                {profile.open_to_contact && (
                  <span className="inline-flex items-center rounded-md bg-info/10 px-2 py-0.5 text-xs font-medium text-info ring-1 ring-inset ring-info/20">
                    Open to contact
                  </span>
                )}
              </div>
            </div>
          </div>
          {profile.open_to_work && (
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3 text-xs text-muted-foreground">
              {profile.work_preferred_locations?.length > 0 && (
                <span className="flex items-center gap-1">
                  <MapPin className="h-3 w-3" />
                  {profile.work_preferred_locations.join(", ")}
                </span>
              )}
              {profile.work_preferred_salary_min != null && (
                <span>
                  {"Salary: "}{profile.work_preferred_salary_min.toLocaleString()}
                  {profile.work_preferred_salary_max != null ? ` - ${profile.work_preferred_salary_max.toLocaleString()}` : "+"}
                </span>
              )}
            </div>
          )}
        </CardHeader>
      </Card>

      {/* Experience */}
      <section>
        <h2 className="text-sm font-medium text-muted-foreground mb-3">Experience</h2>
        {profile.experience_cards.length === 0 ? (
          <div className="text-center py-8 rounded-lg border border-dashed border-border">
            <Briefcase className="h-6 w-6 text-muted-foreground/40 mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">No experience cards shared.</p>
          </div>
        ) : (
          <ul className="space-y-2">
            {profile.experience_cards.map((card, idx) => (
              <motion.li
                key={card.id}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.04, duration: 0.25 }}
              >
                <Card>
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
              </motion.li>
            ))}
          </ul>
        )}
      </section>

      {/* Contact */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
              <Mail className="h-4 w-4 text-muted-foreground" />
            </div>
            <CardTitle className="text-base">Contact</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          {contactUnlocked ? (
            <div className="space-y-2">
              {profile.contact?.email_visible && (
                <div className="flex items-center gap-2 text-sm">
                  <Mail className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-foreground">Email visible to you</span>
                </div>
              )}
              {profile.contact?.phone && (
                <div className="flex items-center gap-2 text-sm">
                  <Phone className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-foreground">{profile.contact.phone}</span>
                </div>
              )}
              {profile.contact?.linkedin_url && (
                <div className="flex items-center gap-2 text-sm">
                  <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
                  <a
                    href={profile.contact.linkedin_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-foreground hover:underline"
                  >
                    LinkedIn
                  </a>
                </div>
              )}
              {profile.contact?.other && (
                <p className="text-sm text-muted-foreground mt-1">{profile.contact.other}</p>
              )}
            </div>
          ) : profile.open_to_contact ? (
            <div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground mb-3">
                <Lock className="h-3.5 w-3.5" />
                <span>Unlock contact details for 1 credit.</span>
              </div>
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
