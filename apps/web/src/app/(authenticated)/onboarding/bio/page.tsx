"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FormField } from "@/components/ui/form-field";
import { BackLink } from "@/components/back-link";
import { PageLoading } from "@/components/page-loading";
import { PageError } from "@/components/page-error";
import { ErrorMessage } from "@/components/error-message";
import { VisibilitySection, type VisibilityMode } from "@/components/onboarding/visibility-section";
import { api, type ApiOptions } from "@/lib/api";
import { bioSchema, bioFormDefaultValues, type BioForm } from "@/lib/bio-schema";
import type { PatchVisibilityRequest, VisibilitySettingsResponse } from "@/types";
import { useBio, useVisibility, BIO_QUERY_KEY, VISIBILITY_QUERY_KEY } from "@/hooks";

type PutBioBody = {
  first_name?: string;
  last_name?: string;
  date_of_birth?: string;
  current_city?: string;
  profile_photo_url?: string;
  school?: string;
  college?: string;
  current_company?: string;
  past_companies?: { company_name: string; role?: string; years?: string }[];
  email?: string;
  linkedin_url?: string;
  phone?: string;
};

export default function OnboardingBioPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);
  const [visibilityMode, setVisibilityMode] = useState<VisibilityMode>("hide_contact");
  const [workPreferredLocations, setWorkPreferredLocations] = useState<string[]>([]);
  const [workSalaryMin, setWorkSalaryMin] = useState<string>("");

  const { data: bio, isLoading, isError: bioError } = useBio();
  const { data: visibility, isLoading: visibilityLoading } = useVisibility();

  useEffect(() => {
    if (!visibility) return;
    if (visibility.open_to_work) {
      setVisibilityMode("open_to_work");
      setWorkPreferredLocations(visibility.work_preferred_locations ?? []);
      setWorkSalaryMin(visibility.work_preferred_salary_min != null ? String(visibility.work_preferred_salary_min) : "");
    } else if (visibility.open_to_contact) {
      setVisibilityMode("open_to_contact");
      setWorkPreferredLocations([]);
      setWorkSalaryMin("");
    } else {
      setVisibilityMode("hide_contact");
      setWorkPreferredLocations([]);
      setWorkSalaryMin("");
    }
  }, [visibility]);

  const { register, control, handleSubmit, formState: { errors }, setValue } = useForm<BioForm>({
    resolver: zodResolver(bioSchema),
    defaultValues: bioFormDefaultValues,
  });

  const { fields, append, remove } = useFieldArray({ control, name: "past_companies" });

  useEffect(() => {
    if (!bio) return;
    setValue("first_name", bio.first_name ?? "");
    setValue("last_name", bio.last_name ?? "");
    setValue("date_of_birth", bio.date_of_birth ?? "");
    setValue("current_city", bio.current_city ?? "");
    setValue("profile_photo_url", bio.profile_photo_url ?? "");
    setValue("school", bio.school ?? "");
    setValue("college", bio.college ?? "");
    setValue("current_company", bio.current_company ?? "");
    setValue("email", bio.email ?? "");
    setValue("linkedin_url", bio.linkedin_url ?? "");
    setValue("phone", bio.phone ?? "");
    if (bio.past_companies?.length) {
      setValue(
        "past_companies",
        bio.past_companies.map((p) => ({
          company_name: p.company_name,
          role: p.role ?? "",
          years: p.years ?? "",
        }))
      );
    } else {
      setValue("past_companies", []);
    }
  }, [bio, setValue]);

  const putBio = useMutation({
    mutationFn: (body: PutBioBody) =>
      api("/me/bio", { method: "PUT", body } as ApiOptions),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: BIO_QUERY_KEY }),
    onError: (e: Error) => setServerError(e.message),
  });

  const patchVisibility = useMutation({
    mutationFn: (body: PatchVisibilityRequest) =>
      api<VisibilitySettingsResponse>("/me/visibility", { method: "PATCH", body } as ApiOptions),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: VISIBILITY_QUERY_KEY }),
    onError: (e: Error) => setServerError(e.message),
  });

  const buildVisibilityPayload = (): PatchVisibilityRequest => {
    if (visibilityMode === "open_to_work") {
      const minNum = workSalaryMin.trim() ? Number(workSalaryMin) : undefined;
      return {
        open_to_work: true,
        open_to_contact: false,
        work_preferred_locations: workPreferredLocations.length ? workPreferredLocations : undefined,
        work_preferred_salary_min: minNum != null && !Number.isNaN(minNum) ? minNum : null,
        work_preferred_salary_max: null,
        contact_preferred_salary_min: null,
        contact_preferred_salary_max: null,
      };
    }
    if (visibilityMode === "open_to_contact") {
      return {
        open_to_work: false,
        open_to_contact: true,
        work_preferred_locations: [],
        work_preferred_salary_min: null,
        work_preferred_salary_max: null,
        contact_preferred_salary_min: null,
        contact_preferred_salary_max: null,
      };
    }
    return {
      open_to_work: false,
      open_to_contact: false,
      work_preferred_locations: [],
      work_preferred_salary_min: null,
      work_preferred_salary_max: null,
      contact_preferred_salary_min: null,
      contact_preferred_salary_max: null,
    };
  };

  const onSubmit = async (data: BioForm) => {
    setServerError(null);
    try {
      await patchVisibility.mutateAsync(buildVisibilityPayload());
      putBio.mutate(
        {
          first_name: data.first_name,
          last_name: data.last_name,
          date_of_birth: data.date_of_birth,
          current_city: data.current_city,
          profile_photo_url: data.profile_photo_url || undefined,
          school: data.school,
          college: data.college || undefined,
          current_company: data.current_company || undefined,
          past_companies: data.past_companies?.filter((p) => p.company_name.trim()).length
            ? data.past_companies?.map((p) => ({
                company_name: p.company_name,
                role: p.role || undefined,
                years: p.years || undefined,
              }))
            : undefined,
          email: data.email,
          linkedin_url: data.linkedin_url?.trim() || undefined,
          phone: data.phone?.trim() || undefined,
        },
        {
          onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: VISIBILITY_QUERY_KEY });
            router.push("/home");
          },
        }
      );
    } catch {
      // Errors handled by mutation onError
    }
  };

  if (isLoading || visibilityLoading) {
    return <PageLoading message="Loading…" />;
  }

  if (bioError) {
    return (
      <PageError
        message="Failed to load your bio. You may need to sign in again."
        backHref="/profile"
        backLabel="← Back to profile"
      />
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-[720px] mx-auto py-8"
    >
      <div className="mb-6">
        <BackLink href="/profile" className="text-sm text-muted-foreground hover:text-foreground transition-colors" />
      </div>
      <Card className="glass border-border/50 shadow-xl glow-ring overflow-hidden">
        <CardHeader className="space-y-1 border-b border-border/50">
          <CardTitle className="text-xl">Create your bio</CardTitle>
          <CardDescription>
            This helps us contextualize your experience. You can edit everything later from your profile.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-8">
            {serverError && <ErrorMessage message={serverError} />}

            <section className="space-y-4">
              <h3 className="text-sm font-semibold text-foreground">Profile basics</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <FormField
                  id="first_name"
                  label="First name (required)"
                  placeholder="Jane"
                  error={errors.first_name?.message}
                  {...register("first_name")}
                />
                <FormField
                  id="last_name"
                  label="Last name (required)"
                  placeholder="Doe"
                  error={errors.last_name?.message}
                  {...register("last_name")}
                />
              </div>
              <FormField
                id="date_of_birth"
                label="Date of birth (required, YYYY-MM-DD)"
                type="text"
                placeholder="1990-01-15"
                error={errors.date_of_birth?.message}
                {...register("date_of_birth")}
              />
              <FormField
                id="current_city"
                label="Current city (required)"
                placeholder="San Francisco"
                error={errors.current_city?.message}
                {...register("current_city")}
              />
              <FormField
                id="profile_photo_url"
                label="Profile photo URL (optional)"
                placeholder="https://..."
                {...register("profile_photo_url")}
              />
            </section>

            <section className="space-y-4">
              <h3 className="text-sm font-semibold text-foreground">Education</h3>
              <FormField
                id="school"
                label="School (required)"
                placeholder="High school or equivalent"
                error={errors.school?.message}
                {...register("school")}
              />
              <FormField
                id="college"
                label="College (optional)"
                placeholder="University name"
                {...register("college")}
              />
            </section>

            <section className="space-y-4">
              <h3 className="text-sm font-semibold text-foreground">Work</h3>
              <FormField
                id="current_company"
                label="Current company (optional)"
                placeholder="Company name"
                {...register("current_company")}
              />
              <div className="space-y-2">
                <Label>Past companies (optional)</Label>
                {fields.map((field, i) => (
                  <div key={field.id} className="flex gap-2 items-end flex-wrap">
                    <Input
                      {...register(`past_companies.${i}.company_name`)}
                      placeholder="Company name"
                      className="flex-1 min-w-[140px]"
                    />
                    <Input
                      {...register(`past_companies.${i}.role`)}
                      placeholder="Role"
                      className="w-32"
                    />
                    <Input
                      {...register(`past_companies.${i}.years`)}
                      placeholder="Years"
                      className="w-24"
                    />
                    <Button type="button" variant="outline" size="sm" onClick={() => remove(i)}>
                      Remove
                    </Button>
                  </div>
                ))}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => append({ company_name: "", role: "", years: "" })}
                >
                  + Add past company
                </Button>
              </div>
            </section>

            <section className="space-y-4">
              <h3 className="text-sm font-semibold text-foreground">Contact</h3>
              <FormField
                id="email"
                label="Email (required)"
                type="email"
                placeholder="you@example.com"
                error={errors.email?.message}
                {...register("email")}
              />
              <FormField
                id="linkedin_url"
                label="LinkedIn URL (optional)"
                placeholder="https://linkedin.com/in/username"
                error={errors.linkedin_url?.message}
                {...register("linkedin_url")}
              />
              <FormField
                id="phone"
                label="Phone number (optional)"
                placeholder="+1 234 567 8900"
                {...register("phone")}
              />
            </section>

            <VisibilitySection
              visibilityMode={visibilityMode}
              onVisibilityModeChange={setVisibilityMode}
              workPreferredLocations={workPreferredLocations}
              onWorkPreferredLocationsChange={setWorkPreferredLocations}
              workSalaryMin={workSalaryMin}
              onWorkSalaryMinChange={setWorkSalaryMin}
            />

            <div className="pt-4 flex flex-col sm:flex-row gap-3">
              <Button
                type="submit"
                className="w-full sm:w-auto"
                size="lg"
                disabled={putBio.isPending || patchVisibility.isPending}
              >
                {putBio.isPending || patchVisibility.isPending ? "Saving…" : "Save & continue to Discover"}
              </Button>
              <p className="text-sm text-muted-foreground self-center sm:self-center">
                Next: add experience in the builder, or start searching.
              </p>
            </div>
          </form>
        </CardContent>
      </Card>
    </motion.div>
  );
}
