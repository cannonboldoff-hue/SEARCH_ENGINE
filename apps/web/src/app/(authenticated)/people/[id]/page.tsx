"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Briefcase,
  Lock,
  Mail,
  MapPin,
  Phone,
  ExternalLink,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageLoading, PageError, ErrorMessage } from "@/components/feedback";
import { CardFamilyDisplay } from "@/components/builder";
import { api, apiWithIdempotency } from "@/lib/api";
import type {
  PersonProfile,
  ContactDetails,
  ExperienceCard,
} from "@/types";

type DetailRow = {
  label: string;
  value: string | number | boolean | null | undefined;
};

function detailValueToText(value: DetailRow["value"]): string | null {
  if (value === null || value === undefined) return null;
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

function DetailGrid({ rows, columns = 2 }: { rows: DetailRow[]; columns?: 1 | 2 }) {
  const visibleRows = rows
    .map((row) => ({ ...row, text: detailValueToText(row.value) }))
    .filter((row) => row.text);

  if (visibleRows.length === 0) return null;

  return (
    <dl className={`grid gap-3 ${columns === 2 ? "sm:grid-cols-2" : ""}`}>
      {visibleRows.map((row) => (
        <div key={row.label} className="space-y-1">
          <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">{row.label}</dt>
          <dd className="text-sm text-foreground whitespace-pre-wrap break-words">{row.text}</dd>
        </div>
      ))}
    </dl>
  );
}

function BioSection({ bio }: { bio: NonNullable<PersonProfile["bio"]> }) {
  const pastCompanies = bio.past_companies?.length
    ? bio.past_companies
        .map((company) =>
          [
            company.company_name,
            company.role ? `Role: ${company.role}` : null,
            company.years ? `Years: ${company.years}` : null,
          ]
            .filter(Boolean)
            .join(" | ")
        )
        .join("\n")
    : null;

  const rows: DetailRow[] = [
    { label: "First name", value: bio.first_name },
    { label: "Last name", value: bio.last_name },
    { label: "Date of birth", value: bio.date_of_birth },
    { label: "Current city", value: bio.current_city },
    { label: "School", value: bio.school },
    { label: "College", value: bio.college },
    { label: "Current company", value: bio.current_company },
    { label: "Past companies", value: pastCompanies },
  ];

  const hasAnyValue = rows.some((row) => detailValueToText(row.value));
  if (!hasAnyValue) return null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Bio</CardTitle>
      </CardHeader>
      <CardContent>
        <DetailGrid rows={rows} />
      </CardContent>
    </Card>
  );
}

export default function PersonProfilePage() {
  return (
    <Suspense fallback={<PageLoading message="Loading profile..." />}>
      <PersonProfilePageContent />
    </Suspense>
  );
}

function PersonProfilePageContent() {
  const params = useParams();
  const searchParams = useSearchParams();
  const personId = params.id as string;
  const searchId = searchParams.get("search_id");
  const queryClient = useQueryClient();

  const profileQuery = useQuery({
    queryKey: ["person", personId, searchId],
    queryFn: () => {
      if (searchId) {
        return api<PersonProfile>(
          `/people/${personId}?search_id=${encodeURIComponent(searchId)}`
        );
      }
      return api<PersonProfile>(`/people/${personId}`);
    },
    enabled: !!personId,
  });

  const unlockMutation = useMutation({
    mutationFn: () => {
      const key = `unlock-${personId}-${searchId}`;
      return apiWithIdempotency<{ unlocked: boolean; contact: ContactDetails }>(
        `/people/${personId}/unlock-contact`,
        key,
        { method: "POST", body: searchId ? { search_id: searchId } : {} }
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["person", personId, searchId] });
    },
  });

  const isLoading = profileQuery.isLoading;
  const error = profileQuery.error;

  if (isLoading) {
    return <PageLoading message="Loading profile..." />;
  }

  const profile = profileQuery.data;
  if (error || !profile) {
    return (
      <PageError
        message={error instanceof Error ? error.message : "Failed to load profile"}
        backHref="/home"
        backLabel="Back to CONXA"
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
      <Link
        href="/home"
        className="text-sm text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-1.5 group"
      >
        <ArrowLeft className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5" />
        Back to Search
      </Link>
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-lg">{profile.display_name || "Anonymous"}</CardTitle>
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
            {profile.open_to_work && profile.work_preferred_locations?.length > 0 && (
              <p className="text-xs text-muted-foreground mt-2 flex items-center gap-1">
                <MapPin className="h-3 w-3" />
                {profile.work_preferred_locations.join(", ")}
              </p>
            )}
          </CardHeader>
        </Card>
        {profile.bio && <BioSection bio={profile.bio} />}
        <section>
          <h2 className="text-sm font-medium text-muted-foreground mb-3">Experience</h2>
          {profile.card_families && profile.card_families.length > 0 ? (
            <div className="space-y-6">
              {profile.card_families.map((family, idx) => (
                <CardFamilyDisplay
                  key={family.parent.id}
                  parent={family.parent}
                  children={family.children}
                  index={idx}
                />
              ))}
            </div>
          ) : profile.experience_cards.length === 0 ? (
            <div className="text-center py-8 rounded-lg border border-dashed border-border">
              <Briefcase className="h-6 w-6 text-muted-foreground/40 mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">No experience cards shared.</p>
            </div>
          ) : (
            <div className="space-y-6">
              {profile.experience_cards.map((card, idx) => (
                <CardFamilyDisplay
                  key={card.id}
                  parent={card}
                  children={[]}
                  index={idx}
                />
              ))}
            </div>
          )}
        </section>
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
                {(profile.contact?.email != null && profile.contact.email !== "") || profile.contact?.email_visible ? (
                  <div className="flex items-center gap-2 text-sm">
                    <Mail className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    <span className="text-foreground">
                      {profile.contact?.email || "Email visible to you"}
                    </span>
                  </div>
                ) : null}
                {profile.contact?.phone && (
                  <div className="flex items-center gap-2 text-sm">
                    <Phone className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    <span className="text-foreground">{profile.contact.phone}</span>
                  </div>
                )}
                {profile.contact?.linkedin_url && (
                  <div className="flex items-center gap-2 text-sm">
                    <ExternalLink className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    <a href={profile.contact.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-foreground hover:underline break-all">
                      {profile.contact.linkedin_url}
                    </a>
                  </div>
                )}
                {profile.contact?.other && (
                  <p className="text-sm text-muted-foreground mt-1">{profile.contact.other}</p>
                )}
              </div>
            ) : (profile.open_to_work || profile.open_to_contact) ? (
              <div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground mb-3">
                  <Lock className="h-3.5 w-3.5" />
                  <span>Unlock contact details for 1 credit.</span>
                </div>
                <Button size="sm" onClick={() => unlockMutation.mutate()} disabled={unlockMutation.isPending}>
                  {unlockMutation.isPending ? "Unlocking..." : "Unlock contact (1 credit)"}
                </Button>
                {unlockMutation.isError && (
                  <div className="mt-2">
                    <ErrorMessage
                      message={unlockMutation.error instanceof Error ? unlockMutation.error.message : "Failed"}
                    />
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">This person is not open to contact.</p>
            )}
          </CardContent>
        </Card>
      </motion.div>
  );
}
