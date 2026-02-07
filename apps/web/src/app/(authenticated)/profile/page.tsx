"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Pencil, Layers } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageLoading } from "@/components/page-loading";
import { PageError } from "@/components/page-error";
import { ExpandableExperienceCard } from "@/components/profile/expandable-experience-card";
import { useBio, useExperienceCardFamilies } from "@/hooks";

export default function ProfilePage() {
  const { data: bio, isLoading: loadingBio, isError: bioError } = useBio();
  const { data: cardFamilies = [], isLoading: loadingCards, isError: cardsError } = useExperienceCardFamilies();

  const isLoading = loadingBio || loadingCards;

  if (isLoading) {
    return <PageLoading message="Loading profile..." className="py-8 flex flex-col items-center justify-center gap-3" />;
  }

  if (bioError || cardsError) {
    return (
      <PageError
        message="Failed to load profile. Please try again."
        backHref="/home"
        backLabel="Go home"
        className="py-8"
      />
    );
  }

  const displayName = [bio?.first_name, bio?.last_name].filter(Boolean).join(" ") || "Anonymous";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="max-w-2xl mx-auto space-y-6"
    >
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 border-b border-border pb-4">
          <CardTitle className="text-lg">My profile</CardTitle>
          <div className="flex gap-2">
            <Link href="/onboarding/bio">
              <Button variant="outline" size="sm">
                <Pencil className="h-3.5 w-3.5 mr-1.5" />
                Edit Bio
              </Button>
            </Link>
            <Link href="/builder">
              <Button variant="outline" size="sm">
                <Layers className="h-3.5 w-3.5 mr-1.5" />
                Builder
              </Button>
            </Link>
          </div>
        </CardHeader>
        <CardContent className="pt-4">
          <section>
            <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">Bio</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2 text-sm">
              {(bio?.first_name || bio?.last_name) && (
                <div><span className="text-muted-foreground">Name:</span> <span className="text-foreground">{displayName}</span></div>
              )}
              {bio?.date_of_birth && (
                <div><span className="text-muted-foreground">DOB:</span> <span className="text-foreground">{bio.date_of_birth}</span></div>
              )}
              {bio?.current_city && (
                <div><span className="text-muted-foreground">City:</span> <span className="text-foreground">{bio.current_city}</span></div>
              )}
              {bio?.school && (
                <div><span className="text-muted-foreground">School:</span> <span className="text-foreground">{bio.school}</span></div>
              )}
              {bio?.college && (
                <div><span className="text-muted-foreground">College:</span> <span className="text-foreground">{bio.college}</span></div>
              )}
              {bio?.current_company && (
                <div><span className="text-muted-foreground">Company:</span> <span className="text-foreground">{bio.current_company}</span></div>
              )}
              {bio?.email && (
                <div><span className="text-muted-foreground">Email:</span> <span className="text-foreground">{bio.email}</span></div>
              )}
              {bio?.linkedin_url && (
                <div>
                  <span className="text-muted-foreground">LinkedIn:</span>{" "}
                  <a href={bio.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-foreground hover:underline">
                    View
                  </a>
                </div>
              )}
              {bio?.phone && (
                <div><span className="text-muted-foreground">Phone:</span> <span className="text-foreground">{bio.phone}</span></div>
              )}
            </div>
            {bio?.past_companies && bio.past_companies.length > 0 && (
              <div className="mt-4">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">Past companies</p>
                <ul className="text-sm space-y-1">
                  {bio.past_companies.map((p, i) => (
                    <li key={i} className="text-foreground">
                      {p.company_name}
                      {p.role && <span className="text-muted-foreground">{` - ${p.role}`}</span>}
                      {p.years && <span className="text-muted-foreground">{` (${p.years})`}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {!bio?.complete && (
              <p className="text-xs text-muted-foreground mt-3 border-t border-border pt-3">
                Complete your bio in Edit Bio to improve your Builder context.
              </p>
            )}
          </section>
        </CardContent>
      </Card>

      <section>
        <h2 className="text-sm font-medium text-muted-foreground mb-3">Experience cards</h2>
        {cardFamilies.length === 0 ? (
          <div className="text-center py-12 rounded-lg border border-dashed border-border">
            <p className="text-sm text-muted-foreground">
              No experience cards yet.{" "}
              <Link href="/builder" className="text-foreground font-medium hover:underline">
                Add experience in the builder
              </Link>
            </p>
          </div>
        ) : (
          <ul className="space-y-3 max-h-[60vh] overflow-y-auto">
            {cardFamilies.map((family, idx) => (
              <ExpandableExperienceCard key={family.parent.id} family={family} index={idx} />
            ))}
          </ul>
        )}
      </section>
    </motion.div>
  );
}
