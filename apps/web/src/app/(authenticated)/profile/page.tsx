"use client";

import Link from "next/link";
import { motion } from "framer-motion";
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
    return <PageLoading message="Loading profile…" className="py-8 flex justify-center" />;
  }

  if (bioError || cardsError) {
    return (
      <PageError
        message="Failed to load profile. Please try again."
        backHref="/home"
        backLabel="← Go home"
        className="py-8"
      />
    );
  }

  const displayName = [bio?.first_name, bio?.last_name].filter(Boolean).join(" ") || "Anonymous";

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 200, damping: 24 }}
      style={{ transformStyle: "preserve-3d", perspective: 1000 }}
      className="max-w-3xl mx-auto space-y-6"
    >
      <motion.div
        initial={{ opacity: 0, y: 12, rotateX: -6 }}
        animate={{ opacity: 1, y: 0, rotateX: 0 }}
        transition={{ delay: 0.06, type: "spring", stiffness: 260, damping: 24 }}
        style={{ transformStyle: "preserve-3d" }}
      >
      <Card className="glass border-border/50 overflow-hidden depth-shadow perspective-1000 transform-3d">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 border-b border-border/50">
          <CardTitle className="text-xl">My profile</CardTitle>
          <div className="flex gap-2">
            <Link href="/onboarding/bio">
              <Button variant="outline" size="sm">
                Edit Bio
              </Button>
            </Link>
            <Link href="/builder">
              <Button variant="outline" size="sm">
                Experience builder
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
      </motion.div>

      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
      >
        <h2 className="text-lg font-semibold mb-3">Experience cards</h2>
        {cardFamilies.length === 0 ? (
          <p className="text-muted-foreground text-sm py-6 rounded-xl border border-dashed border-border/50 text-center">
            No experience cards yet.{" "}
            <Link href="/builder" className="text-primary font-medium hover:underline">
              Add experience in the builder
            </Link>
            .
          </p>
        ) : (
          <ul className="space-y-6 max-h-[60vh] overflow-y-auto pr-2">
            {cardFamilies.map((family, idx) => (
              <ExpandableExperienceCard key={family.parent.id} family={family} index={idx} />
            ))}
          </ul>
        )}
      </motion.section>
    </motion.div>
  );
}
