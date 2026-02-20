"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Pencil, User, GraduationCap, Briefcase, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageLoading, PageError } from "@/components/feedback";
import { useBio } from "@/hooks";

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

  if (loadingBio) {
    return <PageLoading message="Loading profile..." className="py-8 flex flex-col items-center justify-center gap-3" />;
  }

  if (bioError) {
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
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-4 min-w-0">
          {bio?.profile_photo_url ? (
            <div className="relative h-14 w-14 shrink-0 rounded-full overflow-hidden bg-muted">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={bio.profile_photo_url}
                alt={displayName}
                className="h-full w-full object-cover"
              />
            </div>
          ) : (
            <div className="h-14 w-14 shrink-0 rounded-full bg-muted flex items-center justify-center">
              <User className="h-7 w-7 text-muted-foreground" />
            </div>
          )}
          <div className="min-w-0">
            <h1 className="text-xl font-semibold text-foreground tracking-tight truncate">{displayName}</h1>
            {bio?.current_company && <p className="text-sm text-muted-foreground mt-0.5 truncate">{bio.current_company}</p>}
          </div>
        </div>
        <Link href="/onboarding/bio">
          <Button variant="outline" size="sm">
            <Pencil className="h-3.5 w-3.5 mr-1.5" />
            Edit Bio
          </Button>
        </Link>
      </div>

      {/* Profile basics */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
              <User className="h-4 w-4 text-muted-foreground" />
            </div>
            <CardTitle className="text-base">Profile basics</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-3">
            {(bio?.first_name || bio?.last_name) && <BioField label="Name" value={displayName} />}
            {bio?.date_of_birth && <BioField label="Date of birth" value={bio.date_of_birth} />}
            {bio?.current_city && <BioField label="Current city" value={bio.current_city} />}
            {bio?.profile_photo_url && (
              <div className="flex flex-col">
                <span className="text-xs text-muted-foreground">Profile photo</span>
                <a
                  href={bio.profile_photo_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-foreground font-medium hover:underline truncate"
                >
                  View photo
                </a>
              </div>
            )}
          </div>
          {!bio?.complete && (
            <p className="text-xs text-muted-foreground mt-4 pt-3 border-t border-border">
              Complete your bio in Edit Bio.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Education */}
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
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-3">
              {bio?.school && <BioField label="School" value={bio.school} />}
              {bio?.college && <BioField label="College" value={bio.college} />}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Work */}
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

      {/* Contact */}
      {(bio?.email || bio?.phone || bio?.linkedin_url) && (
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
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-3">
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
          </CardContent>
        </Card>
      )}
    </motion.div>
  );
}
