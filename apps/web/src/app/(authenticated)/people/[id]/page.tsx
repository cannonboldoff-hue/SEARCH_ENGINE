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

function BioSection({ bio }: { bio: NonNullable<PersonPublicProfile["bio"]> }) {
  const parts: string[] = [];
  if (bio.first_name || bio.last_name) {
    parts.push([bio.first_name, bio.last_name].filter(Boolean).join(" "));
  }
  if (bio.current_city) parts.push(bio.current_city);
  if (bio.school) parts.push(`School: ${bio.school}`);
  if (bio.college) parts.push(`College: ${bio.college}`);
  if (bio.current_company) parts.push(`Current: ${bio.current_company}`);
  if (bio.past_companies?.length) {
    parts.push(
      "Past: " +
        bio.past_companies.map((p) => p.company_name + (p.role ? ` (${p.role})` : "")).join(", ")
    );
  }
  const text = parts.join(" · ");
  if (!text.trim()) return null;
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Bio</CardTitle>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground whitespace-pre-wrap">
        {text}
      </CardContent>
    </Card>
  );
}

function CardFamilyBlock({
  parent,
  children,
  index,
}: {
  parent: ExperienceCard;
  children: ExperienceCardChild[];
  index: number;
}) {
  const title = parent.title || parent.company_name || parent.normalized_role || "Untitled";
  const meta = [parent.company_name, parent.normalized_role, parent.location, parent.start_date, parent.end_date]
    .filter(Boolean)
    .join(" / ");

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, duration: 0.25 }}
      className="space-y-2"
    >
      {/* Parent card */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-1.5">
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
            {title}
          </CardTitle>
          {meta && (
            <p className="text-xs text-muted-foreground pl-6">{meta}</p>
          )}
        </CardHeader>
        {parent.summary && (
          <CardContent className="pt-0 text-sm text-muted-foreground">
            {parent.summary}
          </CardContent>
        )}
      </Card>
      {/* Child cards (indented hierarchy) */}
      {children.length > 0 && (
        <ul className="space-y-2 pl-4 border-l-2 border-border ml-2">
          {children.map((child) => (
            <li key={child.id}>
              <Card className="bg-muted/30">
                <CardHeader className="py-2 px-3">
                  <CardTitle className="text-xs font-medium">
                    {child.title || child.headline || "—"}
                  </CardTitle>
                  {(child.summary || child.context) && (
                    <p className="text-xs text-muted-foreground mt-1">
                      {child.summary || child.context}
                    </p>
                  )}
                  {(child.time_range || child.company || child.location) && (
                    <p className="text-xs text-muted-foreground/80 mt-0.5">
                      {[child.time_range, child.company, child.location]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                  )}
                </CardHeader>
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
          backLabel="Back to Cipher"
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
          Back to Cipher
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
                <motion.li key={card.id} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: idx * 0.04, duration: 0.25 }}>
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
                    <a href={profile.contact.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-foreground hover:underline">
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
        backLabel="Back to Cipher"
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
        Back to Cipher
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
