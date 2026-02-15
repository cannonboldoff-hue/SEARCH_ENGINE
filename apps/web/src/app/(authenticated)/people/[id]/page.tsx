"use client";

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
  ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageLoading, PageError, ErrorMessage } from "@/components/feedback";
import { api, apiWithIdempotency } from "@/lib/api";
import type {
  PersonProfile,
  PersonPublicProfile,
  ContactDetails,
  ExperienceCard,
  ExperienceCardChild,
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

function ExperienceCardDetails({
  card,
  hideVisibilityField = false,
  hideConfidenceScore = false,
  hideTimestamps = false,
}: {
  card: ExperienceCard;
  hideVisibilityField?: boolean;
  hideConfidenceScore?: boolean;
  hideTimestamps?: boolean;
}) {
  const rows: DetailRow[] = [
    { label: "Title", value: card.title },
    { label: "Normalized role", value: card.normalized_role },
    { label: "Domain", value: card.domain },
    { label: "Sub domain", value: card.sub_domain },
    { label: "Company name", value: card.company_name },
    { label: "Company type", value: card.company_type },
    { label: "Employment type", value: card.employment_type },
    { label: "Location", value: card.location },
    { label: "Start date", value: card.start_date },
    { label: "End date", value: card.end_date },
    { label: "Current role", value: card.is_current },
    { label: "Summary", value: card.summary },
    { label: "Intent primary", value: card.intent_primary },
    {
      label: "Intent secondary",
      value:
        card.intent_secondary && card.intent_secondary.length > 0
          ? card.intent_secondary.join(", ")
          : null,
    },
    { label: "Seniority", value: card.seniority_level },
    ...(hideConfidenceScore ? [] : [{ label: "Confidence score", value: card.confidence_score }]),
    ...(hideVisibilityField
      ? []
      : [{ label: "Visible in search", value: card.experience_card_visibility }]),
    ...(hideTimestamps
      ? []
      : [
          { label: "Created at", value: card.created_at },
          { label: "Updated at", value: card.updated_at },
        ]),
  ];

  return <DetailGrid rows={rows} />;
}

function ExperienceCardChildDetails({
  child,
  hideTitleAndHeadline = false,
}: {
  child: ExperienceCardChild;
  hideTitleAndHeadline?: boolean;
}) {
  const topicLabels =
    child.topics && child.topics.length > 0
      ? child.topics
          .map((topic) => topic?.label)
          .filter((label): label is string => !!label && label.trim().length > 0)
      : [];

  const rows: DetailRow[] = [
    { label: "Relation type", value: child.relation_type },
    ...(hideTitleAndHeadline
      ? []
      : [
          { label: "Title", value: child.title },
          { label: "Headline", value: child.headline },
        ]),
    { label: "Summary", value: child.summary },
    { label: "Time range", value: child.time_range },
    { label: "Role title", value: child.role_title },
    { label: "Company", value: child.company },
    { label: "Location", value: child.location },
    { label: "Topics", value: topicLabels.length ? topicLabels.join(", ") : null },
  ];

  return <DetailGrid rows={rows} />;
}

function BioSection({ bio }: { bio: NonNullable<PersonPublicProfile["bio"]> }) {
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

function CardFamilyBlock({
  parent,
  children,
  index,
  isSearchResultView = false,
}: {
  parent: ExperienceCard;
  children: ExperienceCardChild[];
  index: number;
  isSearchResultView?: boolean;
}) {
  const title = parent.title || parent.company_name || parent.normalized_role || "Untitled";
  const meta = [parent.company_name, parent.normalized_role, parent.location]
    .filter(Boolean)
    .join(" / ");

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, duration: 0.25 }}
      className="space-y-2"
    >
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-1.5">
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
            {title}
          </CardTitle>
          {meta && <p className="text-xs text-muted-foreground pl-6">{meta}</p>}
        </CardHeader>
        <CardContent className="pt-0">
          <ExperienceCardDetails
            card={parent}
            hideVisibilityField={isSearchResultView}
            hideConfidenceScore={isSearchResultView}
            hideTimestamps={isSearchResultView}
          />
        </CardContent>
      </Card>
      {children.length > 0 && (
        <ul className="space-y-2 pl-4 border-l-2 border-border ml-2">
          {children.map((child) => (
            <li key={child.id}>
              <Card className="bg-muted/30">
                <CardHeader className="py-2 px-3">
                  <CardTitle className="text-xs font-medium">
                    {isSearchResultView
                      ? child.summary || child.relation_type || "Child card"
                      : child.title || child.headline || child.summary || "Child card"}
                  </CardTitle>
                </CardHeader>
                <CardContent className="px-3 pb-3 pt-0">
                  <ExperienceCardChildDetails
                    child={child}
                    hideTitleAndHeadline={isSearchResultView}
                  />
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </motion.div>
  );
}

export default function PersonProfilePage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const personId = params.id as string;
  const searchId = searchParams.get("search_id");
  const queryClient = useQueryClient();

  const fromSearch = !!searchId;

  const searchProfileQuery = useQuery({
    queryKey: ["person", personId, searchId],
    queryFn: () =>
      api<PersonProfile>(
        `/people/${personId}?search_id=${encodeURIComponent(searchId || "")}`
      ),
    enabled: !!personId && fromSearch,
  });

  const publicProfileQuery = useQuery({
    queryKey: ["person-public", personId],
    queryFn: () => api<PersonPublicProfile>(`/people/${personId}/profile`),
    enabled: !!personId && !fromSearch,
  });

  const unlockMutation = useMutation({
    mutationFn: () => {
      const key = `unlock-${personId}-${searchId}`;
      return apiWithIdempotency<{ unlocked: boolean; contact: ContactDetails }>(
        `/people/${personId}/unlock-contact`,
        key,
        { method: "POST", body: { search_id: searchId! } }
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["person", personId, searchId] });
    },
  });

  const isLoading = fromSearch
    ? searchProfileQuery.isLoading
    : publicProfileQuery.isLoading;
  const error = fromSearch ? searchProfileQuery.error : publicProfileQuery.error;

  if (isLoading) {
    return <PageLoading message="Loading profile..." />;
  }

  if (fromSearch) {
    const profile = searchProfileQuery.data;
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
                <CardFamilyBlock
                  key={family.parent.id}
                  parent={family.parent}
                  children={family.children}
                  index={idx}
                  isSearchResultView
                />
              ))}
            </div>
          ) : profile.experience_cards.length === 0 ? (
            <div className="text-center py-8 rounded-lg border border-dashed border-border">
              <Briefcase className="h-6 w-6 text-muted-foreground/40 mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">No experience cards shared.</p>
            </div>
          ) : (
            <ul className="space-y-2">
              {profile.experience_cards.map((card, idx) => (
                <motion.li key={card.id} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: idx * 0.04, duration: 0.25 }}>
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-medium">
                        {card.title || card.company_name || "Untitled"}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="pt-0">
                      <ExperienceCardDetails
                        card={card}
                        hideVisibilityField
                        hideConfidenceScore
                        hideTimestamps
                      />
                    </CardContent>
                  </Card>
                </motion.li>
              ))}
            </ul>
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

  const publicProfile = publicProfileQuery.data;
  if (error || !publicProfile) {
    return (
      <PageError
        message={error instanceof Error ? error.message : "Failed to load profile"}
        backHref="/home"
        backLabel="Back to CONXA"
      />
    );
  }

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
        Back to CONXA
      </Link>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg">
            {publicProfile.display_name || "Anonymous"}
          </CardTitle>
        </CardHeader>
      </Card>

      {publicProfile.bio && <BioSection bio={publicProfile.bio} />}

      <section>
        <h2 className="text-sm font-medium text-muted-foreground mb-3">Experience</h2>
        {publicProfile.card_families.length === 0 ? (
          <div className="text-center py-8 rounded-lg border border-dashed border-border">
            <Briefcase className="h-6 w-6 text-muted-foreground/40 mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">No experience cards shared.</p>
          </div>
        ) : (
          <div className="space-y-6">
            {publicProfile.card_families.map((family, idx) => (
              <CardFamilyBlock
                key={family.parent.id}
                parent={family.parent}
                children={family.children}
                index={idx}
              />
            ))}
          </div>
        )}
      </section>
    </motion.div>
  );
}
