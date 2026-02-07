"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Pencil, Layers, User, Briefcase, GraduationCap, Mail, MapPin } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageLoading } from "@/components/page-loading";
import { PageError } from "@/components/page-error";
import { ExpandableExperienceCard } from "@/components/profile/expandable-experience-card";
import { useBio, useExperienceCardFamilies } from "@/hooks";

function BioField({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-sm text-foreground font-medium">{value}</span>
    </div>
  );
}

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
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground tracking-tight">{displayName}</h1>
          {bio?.current_company && (
            <p className="text-sm text-muted-foreground mt-0.5">{bio.current_company}</p>
          )}
        </div>
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
      </div>

      {/* Bio card */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
              <User className="h-4 w-4 text-muted-foreground" />
            </div>
            <CardTitle className="text-base">Bio</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-3">
            {(bio?.first_name || bio?.last_name) && (
              <BioField label="Name" value={displayName} />
            )}
            {bio?.date_of_birth && <BioField label="Date of birth" value={bio.date_of_birth} />}
            {bio?.current_city && <BioField label="City" value={bio.current_city} />}
            {bio?.email && <BioField label="Email" value={bio.email} />}
            {bio?.phone && <BioField label="Phone" value={bio.phone} />}
            {bio?.linkedin_url && (
              <div className="flex flex-col">
                <span className="text-xs text-muted-foreground">LinkedIn</span>
                <a
                  href={bio.linkedin_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-foreground font-medium hover:underline"
                >
                  View profile
                </a>
              </div>
            )}
          </div>
          {!bio?.complete && (
            <p className="text-xs text-muted-foreground mt-4 pt-3 border-t border-border">
              Complete your bio in Edit Bio to improve your Builder context.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Education & Work */}
      {(bio?.school || bio?.college || bio?.current_company || (bio?.past_companies && bio.past_companies.length > 0)) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {(bio?.school || bio?.college) && (
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
                    <GraduationCap className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <CardTitle className="text-base">Education</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                {bio?.school && <BioField label="School" value={bio.school} />}
                {bio?.college && <BioField label="College" value={bio.college} />}
              </CardContent>
            </Card>
          )}
          {(bio?.current_company || (bio?.past_companies && bio.past_companies.length > 0)) && (
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
                    <Briefcase className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <CardTitle className="text-base">Work</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                {bio?.current_company && <BioField label="Current company" value={bio.current_company} />}
                {bio?.past_companies && bio.past_companies.length > 0 && (
                  <div className="flex flex-col">
                    <span className="text-xs text-muted-foreground mb-1">Past companies</span>
                    <ul className="space-y-1">
                      {bio.past_companies.map((p, i) => (
                        <li key={i} className="text-sm text-foreground">
                          <span className="font-medium">{p.company_name}</span>
                          {p.role && <span className="text-muted-foreground">{` - ${p.role}`}</span>}
                          {p.years && <span className="text-muted-foreground">{` (${p.years})`}</span>}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Experience cards */}
      <section>
        <h2 className="text-sm font-medium text-muted-foreground mb-3">Experience cards</h2>
        {cardFamilies.length === 0 ? (
          <div className="text-center py-12 rounded-lg border border-dashed border-border">
            <Layers className="h-8 w-8 text-muted-foreground/40 mx-auto mb-3" />
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
