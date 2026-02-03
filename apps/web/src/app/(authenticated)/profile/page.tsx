"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

type ExperienceCard = {
  id: string;
  status: string;
  human_edited?: boolean;
  locked?: boolean;
  title: string | null;
  context: string | null;
  constraints: string | null;
  decisions: string | null;
  outcome: string | null;
  tags: string[];
  company: string | null;
  team: string | null;
  role_title: string | null;
  time_range: string | null;
};

type BioResponse = {
  first_name: string | null;
  last_name: string | null;
  date_of_birth: string | null;
  current_city: string | null;
  profile_photo_url: string | null;
  school: string | null;
  college: string | null;
  current_company: string | null;
  past_companies: { company_name: string; role?: string; years?: string }[] | null;
  email: string | null;
  linkedin_url: string | null;
  phone: string | null;
  complete: boolean;
};

export default function ProfilePage() {
  const { data: bio, isLoading: loadingBio, isError: bioError } = useQuery({
    queryKey: ["bio"],
    queryFn: () => api<BioResponse>("/me/bio"),
  });

  const { data: experienceCards = [], isLoading: loadingCards, isError: cardsError } = useQuery({
    queryKey: ["experience-cards"],
    queryFn: () => api<ExperienceCard[]>("/me/experience-cards"),
  });

  const isLoading = loadingBio || loadingCards;

  if (isLoading) {
    return (
      <div className="py-8 flex justify-center">
        <div className="animate-pulse text-muted-foreground">Loading profile…</div>
      </div>
    );
  }

  if (bioError || cardsError) {
    return (
      <div className="py-8 text-center text-destructive">
        Failed to load profile. Please try again.
      </div>
    );
  }

  const displayName = [bio?.first_name, bio?.last_name].filter(Boolean).join(" ") || "Anonymous";

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="max-w-3xl mx-auto space-y-6"
    >
      <Card className="border-border/50 bg-card">
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-xl">Profile</CardTitle>
          <div className="flex gap-2">
            <Link href="/onboarding/bio">
              <Button variant="outline" size="sm">
                Edit Bio
              </Button>
            </Link>
            <Link href="/builder">
              <Button variant="outline" size="sm">
                Builder
              </Button>
            </Link>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <section>
            <h3 className="text-sm font-semibold text-muted-foreground mb-2">Bio</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 text-sm">
              {(bio?.first_name || bio?.last_name) && (
                <p><span className="text-muted-foreground">Name:</span> {displayName}</p>
              )}
              {bio?.date_of_birth && (
                <p><span className="text-muted-foreground">DOB:</span> {bio.date_of_birth}</p>
              )}
              {bio?.current_city && (
                <p><span className="text-muted-foreground">City:</span> {bio.current_city}</p>
              )}
              {bio?.school && (
                <p><span className="text-muted-foreground">School:</span> {bio.school}</p>
              )}
              {bio?.college && (
                <p><span className="text-muted-foreground">College:</span> {bio.college}</p>
              )}
              {bio?.current_company && (
                <p><span className="text-muted-foreground">Current company:</span> {bio.current_company}</p>
              )}
              {bio?.email && (
                <p><span className="text-muted-foreground">Email:</span> {bio.email}</p>
              )}
              {bio?.linkedin_url && (
                <p>
                  <span className="text-muted-foreground">LinkedIn:</span>{" "}
                  <a href={bio.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                    {bio.linkedin_url}
                  </a>
                </p>
              )}
              {bio?.phone && (
                <p><span className="text-muted-foreground">Phone:</span> {bio.phone}</p>
              )}
            </div>
            {bio?.past_companies && bio.past_companies.length > 0 && (
              <div className="mt-2">
                <p className="text-muted-foreground text-sm mb-1">Past companies</p>
                <ul className="text-sm list-disc list-inside space-y-0.5">
                  {bio.past_companies.map((p, i) => (
                    <li key={i}>
                      {p.company_name}
                      {p.role && ` — ${p.role}`}
                      {p.years && ` (${p.years})`}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {!bio?.complete && (
              <p className="text-sm text-muted-foreground mt-2">
                Complete your bio in Edit Bio to improve your Builder context.
              </p>
            )}
          </section>
        </CardContent>
      </Card>

      <section>
        <h2 className="text-lg font-semibold mb-3">Experience cards</h2>
        {experienceCards.length === 0 ? (
          <p className="text-muted-foreground text-sm py-4">
            No experience cards yet.{" "}
            <Link href="/builder" className="text-primary hover:underline">
              Add experience in the Builder
            </Link>
            .
          </p>
        ) : (
          <ul className="space-y-4 max-h-[60vh] overflow-y-auto pr-2">
            {experienceCards.map((card) => (
              <Card key={card.id} className="border-border/50 bg-card">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <CardTitle className="text-base">
                      {card.title || card.company || "Untitled"}
                    </CardTitle>
                    <div className="flex items-center gap-2">
                      {card.human_edited && (
                        <span className="rounded bg-violet-900/40 px-2 py-0.5 text-xs text-violet-400">
                          Edited
                        </span>
                      )}
                      {card.locked && (
                        <span className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                          Locked
                        </span>
                      )}
                      <span
                        className={
                          card.status === "APPROVED"
                            ? "rounded bg-green-900/40 px-2 py-0.5 text-xs text-green-400"
                            : card.status === "DRAFT"
                              ? "rounded bg-amber-900/40 px-2 py-0.5 text-xs text-amber-400"
                              : "rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground"
                        }
                      >
                        {card.status}
                      </span>
                    </div>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {[card.company, card.team, card.role_title, card.time_range]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  {card.context && <p>{card.context}</p>}
                  {card.constraints && (
                    <p><strong>Constraints:</strong> {card.constraints}</p>
                  )}
                  {card.decisions && (
                    <p><strong>Decisions:</strong> {card.decisions}</p>
                  )}
                  {card.outcome && (
                    <p><strong>Outcome:</strong> {card.outcome}</p>
                  )}
                  {card.tags?.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {card.tags.map((t, i) => (
                        <span
                          key={`${t}-${i}`}
                          className="rounded bg-muted px-2 py-0.5 text-xs"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </ul>
        )}
      </section>
    </motion.div>
  );
}
