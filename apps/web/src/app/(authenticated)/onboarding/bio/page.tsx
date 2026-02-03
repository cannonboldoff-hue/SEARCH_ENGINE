"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type ApiOptions } from "@/lib/api";
import { INDIA_CITIES } from "@/lib/india-cities";
import type { BioResponse, VisibilitySettingsResponse, PatchVisibilityRequest } from "@/types";
import { cn } from "@/lib/utils";

const LINKEDIN_URL_REGEX = /^(https?:\/\/)?(www\.)?linkedin\.com\/in\/[\w-]+\/?$/i;
const DOB_REGEX = /^\d{4}-\d{2}-\d{2}$/;

const bioSchema = z.object({
  first_name: z.string().min(1, "First name is required"),
  last_name: z.string().min(1, "Last name is required"),
  date_of_birth: z.string().min(1, "Date of birth is required").refine(
    (val) => DOB_REGEX.test(val),
    "Use YYYY-MM-DD format"
  ),
  current_city: z.string().min(1, "Current city is required"),
  profile_photo_url: z.string().optional(),
  school: z.string().min(1, "School is required"),
  college: z.string().optional(),
  current_company: z.string().optional(),
  past_companies: z.array(
    z.object({
      company_name: z.string(),
      role: z.string().optional(),
      years: z.string().optional(),
    })
  ).optional(),
  email: z.string().email("Valid email is required"),
  linkedin_url: z
    .string()
    .optional()
    .refine((val) => !val || val.trim() === "" || LINKEDIN_URL_REGEX.test(val), {
      message: "Enter a valid LinkedIn profile URL (e.g. https://linkedin.com/in/username)",
    }),
  phone: z.string().optional(),
});

type BioForm = z.infer<typeof bioSchema>;

type VisibilityMode = "open_to_work" | "open_to_contact" | "hide_contact";

const defaultVisibility: VisibilitySettingsResponse = {
  open_to_work: false,
  open_to_contact: false,
  work_preferred_locations: [],
  work_preferred_salary_min: null,
  work_preferred_salary_max: null,
  contact_preferred_salary_min: null,
  contact_preferred_salary_max: null,
};

export default function OnboardingBioPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);
  const [visibilityMode, setVisibilityMode] = useState<VisibilityMode>("hide_contact");
  const [workPreferredLocations, setWorkPreferredLocations] = useState<string[]>([]);
  const [workSalaryMin, setWorkSalaryMin] = useState<string>("");

  const { data: bio, isLoading, isError: bioError } = useQuery({
    queryKey: ["bio"],
    queryFn: () => api<BioResponse>("/me/bio"),
  });

  const { data: visibility, isLoading: visibilityLoading } = useQuery({
    queryKey: ["visibility"],
    queryFn: async () => {
      try {
        return await api<VisibilitySettingsResponse>("/me/visibility");
      } catch {
        return defaultVisibility;
      }
    },
  });

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
    defaultValues: {
      first_name: "",
      last_name: "",
      date_of_birth: "",
      current_city: "",
      profile_photo_url: "",
      school: "",
      college: "",
      current_company: "",
      past_companies: [],
      email: "",
      linkedin_url: "",
      phone: "",
    },
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
    mutationFn: (body: {
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
    }) =>
      api("/me/bio", {
        method: "PUT",
        body,
      } as ApiOptions),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["bio"] }),
    onError: (e: Error) => setServerError(e.message),
  });

  const patchVisibility = useMutation({
    mutationFn: (body: PatchVisibilityRequest) =>
      api<VisibilitySettingsResponse>("/me/visibility", { method: "PATCH", body } as ApiOptions),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["visibility"] }),
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
            queryClient.invalidateQueries({ queryKey: ["visibility"] });
            router.push("/home");
          },
        }
      );
    } catch {
      // Errors handled by mutation onError
    }
  };

  if (isLoading || visibilityLoading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="animate-pulse text-muted-foreground">Loading…</div>
      </div>
    );
  }

  if (bioError) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="text-center space-y-4 max-w-md">
          <p className="text-destructive">Failed to load your bio. You may need to sign in again.</p>
          <Link
            href="/profile"
            className="text-sm text-primary font-medium hover:underline"
          >
            ← Back to profile
          </Link>
        </div>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-[720px] mx-auto py-8"
    >
      <div className="mb-6">
        <Link
          href="/profile"
          className="text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          ← Back to profile
        </Link>
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
            {serverError && (
              <div className="text-sm text-destructive bg-destructive/10 rounded-md p-3">
                {serverError}
              </div>
            )}

            <section className="space-y-4">
              <h3 className="text-sm font-semibold text-foreground">Profile basics</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="first_name">First name (required)</Label>
                  <Input id="first_name" {...register("first_name")} placeholder="Jane" />
                  {errors.first_name && (
                    <p className="text-xs text-destructive">{errors.first_name.message}</p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="last_name">Last name (required)</Label>
                  <Input id="last_name" {...register("last_name")} placeholder="Doe" />
                  {errors.last_name && (
                    <p className="text-xs text-destructive">{errors.last_name.message}</p>
                  )}
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="date_of_birth">Date of birth (required, YYYY-MM-DD)</Label>
                <Input id="date_of_birth" type="text" {...register("date_of_birth")} placeholder="1990-01-15" />
                {errors.date_of_birth && (
                  <p className="text-xs text-destructive">{errors.date_of_birth.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="current_city">Current city (required)</Label>
                <Input id="current_city" {...register("current_city")} placeholder="San Francisco" />
                {errors.current_city && (
                  <p className="text-xs text-destructive">{errors.current_city.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="profile_photo_url">Profile photo URL (optional)</Label>
                <Input id="profile_photo_url" {...register("profile_photo_url")} placeholder="https://..." />
              </div>
            </section>

            <section className="space-y-4">
              <h3 className="text-sm font-semibold text-foreground">Education</h3>
              <div className="space-y-2">
                <Label htmlFor="school">School (required)</Label>
                <Input id="school" {...register("school")} placeholder="High school or equivalent" />
                {errors.school && (
                  <p className="text-xs text-destructive">{errors.school.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="college">College (optional)</Label>
                <Input id="college" {...register("college")} placeholder="University name" />
              </div>
            </section>

            <section className="space-y-4">
              <h3 className="text-sm font-semibold text-foreground">Work</h3>
              <div className="space-y-2">
                <Label htmlFor="current_company">Current company (optional)</Label>
                <Input id="current_company" {...register("current_company")} placeholder="Company name" />
              </div>
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
              <div className="space-y-2">
                <Label htmlFor="email">Email (required)</Label>
                <Input id="email" type="email" {...register("email")} placeholder="you@example.com" />
                {errors.email && (
                  <p className="text-xs text-destructive">{errors.email.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="linkedin_url">LinkedIn URL (optional)</Label>
                <Input
                  id="linkedin_url"
                  {...register("linkedin_url")}
                  placeholder="https://linkedin.com/in/username"
                />
                {errors.linkedin_url && (
                  <p className="text-xs text-destructive">{errors.linkedin_url.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="phone">Phone number (optional)</Label>
                <Input id="phone" {...register("phone")} placeholder="+1 234 567 8900" />
              </div>
            </section>

            <section className="space-y-4">
              <h3 className="text-sm font-semibold text-foreground">Visibility</h3>
              <p className="text-sm text-muted-foreground">
                Choose how you want to appear in search: Open to Work, Open to Contact, or Hide Contact. If you select Hide Contact, you will not appear in search results at all.
              </p>
              <div className="flex flex-col gap-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="visibility_mode"
                    checked={visibilityMode === "open_to_work"}
                    onChange={() => setVisibilityMode("open_to_work")}
                    className="h-4 w-4 border-border"
                  />
                  <span className="text-sm font-medium">Open to Work</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="visibility_mode"
                    checked={visibilityMode === "open_to_contact"}
                    onChange={() => setVisibilityMode("open_to_contact")}
                    className="h-4 w-4 border-border"
                  />
                  <span className="text-sm font-medium">Open to Contact</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="visibility_mode"
                    checked={visibilityMode === "hide_contact"}
                    onChange={() => setVisibilityMode("hide_contact")}
                    className="h-4 w-4 border-border"
                  />
                  <span className="text-sm font-medium">Hide Contact</span>
                </label>
              </div>

              {visibilityMode === "open_to_work" && (
                <div className="mt-4 space-y-4 pl-6 border-l-2 border-border/50">
                  <div className="space-y-2">
                    <Label>Preferred locations (cities in India)</Label>
                    <select
                      multiple
                      value={workPreferredLocations}
                      onChange={(e) => {
                        const selected = Array.from(e.target.selectedOptions, (o) => o.value);
                        setWorkPreferredLocations(selected);
                      }}
                      className={cn(
                        "w-full min-h-[120px] rounded-md border border-input bg-background px-3 py-2 text-sm",
                        "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                      )}
                    >
                      {INDIA_CITIES.map((city) => (
                        <option key={city} value={city}>
                          {city}
                        </option>
                      ))}
                    </select>
                    <p className="text-xs text-muted-foreground">
                      Hold Ctrl (Windows) or Cmd (Mac) to select multiple cities.
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="work_salary_min">Minimum package (₹/year, optional)</Label>
                    <Input
                      id="work_salary_min"
                      type="number"
                      min={0}
                      placeholder="e.g. 800000"
                      value={workSalaryMin}
                      onChange={(e) => setWorkSalaryMin(e.target.value)}
                      className="bg-background"
                    />
                  </div>
                </div>
              )}
            </section>

            <div className="pt-4 flex flex-col sm:flex-row gap-3">
              <Button type="submit" className="w-full sm:w-auto" size="lg" disabled={putBio.isPending || patchVisibility.isPending}>
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
