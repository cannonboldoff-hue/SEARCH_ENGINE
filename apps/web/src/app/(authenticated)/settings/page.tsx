"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type ApiOptions } from "@/lib/api";
import { useEffect } from "react";

const visibilitySchema = z.object({
  open_to_work: z.boolean(),
  work_preferred_locations: z.string().optional(),
  work_preferred_salary_min: z.string().optional(),
  work_preferred_salary_max: z.string().optional(),
  open_to_contact: z.boolean(),
  contact_preferred_salary_min: z.string().optional(),
  contact_preferred_salary_max: z.string().optional(),
});

const contactSchema = z.object({
  email_visible: z.boolean(),
  phone: z.string().optional(),
  linkedin_url: z.string().optional(),
  other: z.string().optional(),
});

type VisibilityForm = z.infer<typeof visibilitySchema>;
type ContactForm = z.infer<typeof contactSchema>;

export default function SettingsPage() {
  const queryClient = useQueryClient();

  const { data: visibility } = useQuery({
    queryKey: ["visibility"],
    queryFn: () =>
      api<{
        open_to_work: boolean;
        work_preferred_locations: string[];
        work_preferred_salary_min: number | null;
        work_preferred_salary_max: number | null;
        open_to_contact: boolean;
        contact_preferred_salary_min: number | null;
        contact_preferred_salary_max: number | null;
      }>("/me/visibility"),
  });

  const { data: contact } = useQuery({
    queryKey: ["contact"],
    queryFn: () =>
      api<{ email_visible: boolean; phone: string | null; linkedin_url: string | null; other: string | null }>(
        "/me/contact"
      ),
  });

  const visibilityForm = useForm<VisibilityForm>({
    resolver: zodResolver(visibilitySchema),
    defaultValues: {
      open_to_work: false,
      work_preferred_locations: "",
      work_preferred_salary_min: "",
      work_preferred_salary_max: "",
      open_to_contact: false,
      contact_preferred_salary_min: "",
      contact_preferred_salary_max: "",
    },
  });

  const contactForm = useForm<ContactForm>({
    resolver: zodResolver(contactSchema),
    defaultValues: {
      email_visible: true,
      phone: "",
      linkedin_url: "",
      other: "",
    },
  });

  useEffect(() => {
    if (visibility) {
      visibilityForm.reset({
        open_to_work: visibility.open_to_work,
        work_preferred_locations: visibility.work_preferred_locations?.join(", ") ?? "",
        work_preferred_salary_min: visibility.work_preferred_salary_min?.toString() ?? "",
        work_preferred_salary_max: visibility.work_preferred_salary_max?.toString() ?? "",
        open_to_contact: visibility.open_to_contact,
        contact_preferred_salary_min: visibility.contact_preferred_salary_min?.toString() ?? "",
        contact_preferred_salary_max: visibility.contact_preferred_salary_max?.toString() ?? "",
      });
    }
  }, [visibility]);

  useEffect(() => {
    if (contact) {
      contactForm.reset({
        email_visible: contact.email_visible,
        phone: contact.phone ?? "",
        linkedin_url: contact.linkedin_url ?? "",
        other: contact.other ?? "",
      });
    }
  }, [contact]);

  const patchVisibility = useMutation({
    mutationFn: (body: VisibilityForm) =>
      api("/me/visibility", {
        method: "PATCH",
        body: {
          open_to_work: body.open_to_work,
          work_preferred_locations: body.work_preferred_locations
            ? body.work_preferred_locations.split(",").map((s) => s.trim()).filter(Boolean)
            : undefined,
          work_preferred_salary_min: body.work_preferred_salary_min
            ? Number(body.work_preferred_salary_min)
            : undefined,
          work_preferred_salary_max: body.work_preferred_salary_max
            ? Number(body.work_preferred_salary_max)
            : undefined,
          open_to_contact: body.open_to_contact,
          contact_preferred_salary_min: body.contact_preferred_salary_min
            ? Number(body.contact_preferred_salary_min)
            : undefined,
          contact_preferred_salary_max: body.contact_preferred_salary_max
            ? Number(body.contact_preferred_salary_max)
            : undefined,
        },
      } as ApiOptions),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["visibility"] }),
  });

  const patchContact = useMutation({
    mutationFn: (body: ContactForm) =>
      api("/me/contact", {
        method: "PATCH",
        body: {
          email_visible: body.email_visible,
          phone: body.phone || undefined,
          linkedin_url: body.linkedin_url || undefined,
          other: body.other || undefined,
        },
      } as ApiOptions),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["contact"] }),
  });

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-semibold">Settings</h1>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <Card>
          <CardHeader>
            <CardTitle>Visibility</CardTitle>
            <CardDescription>
              Open to Work (locations + salary) and Open to Contact (salary only).
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={visibilityForm.handleSubmit((data) => patchVisibility.mutate(data))}
              className="space-y-4"
            >
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="open_to_work"
                  checked={visibilityForm.watch("open_to_work")}
                  {...visibilityForm.register("open_to_work")}
                  className="rounded border-input"
                />
                <Label htmlFor="open_to_work">Open to work</Label>
              </div>
              {visibilityForm.watch("open_to_work") && (
                <>
                  <div className="space-y-2">
                    <Label>Preferred locations (comma-separated)</Label>
                    <Input
                      placeholder="Bangalore, Remote"
                      {...visibilityForm.register("work_preferred_locations")}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Salary min (yearly)</Label>
                      <Input
                        type="number"
                        placeholder="0"
                        {...visibilityForm.register("work_preferred_salary_min")}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Salary max (yearly)</Label>
                      <Input
                        type="number"
                        placeholder="0"
                        {...visibilityForm.register("work_preferred_salary_max")}
                      />
                    </div>
                  </div>
                </>
              )}
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="open_to_contact"
                  checked={visibilityForm.watch("open_to_contact")}
                  {...visibilityForm.register("open_to_contact")}
                  className="rounded border-input"
                />
                <Label htmlFor="open_to_contact">Open to contact</Label>
              </div>
              {visibilityForm.watch("open_to_contact") && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Contact salary min (yearly)</Label>
                    <Input
                      type="number"
                      placeholder="0"
                      {...visibilityForm.register("contact_preferred_salary_min")}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Contact salary max (yearly)</Label>
                    <Input
                      type="number"
                      placeholder="0"
                      {...visibilityForm.register("contact_preferred_salary_max")}
                    />
                  </div>
                </div>
              )}
              <Button type="submit" disabled={patchVisibility.isPending}>
                Save visibility
              </Button>
            </form>
          </CardContent>
        </Card>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.1 }}
      >
        <Card>
          <CardHeader>
            <CardTitle>Contact details</CardTitle>
            <CardDescription>Shown when someone unlocks your contact.</CardDescription>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={contactForm.handleSubmit((data) => patchContact.mutate(data))}
              className="space-y-4"
            >
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="email_visible"
                  checked={contactForm.watch("email_visible")}
                  {...contactForm.register("email_visible")}
                  className="rounded border-input"
                />
                <Label htmlFor="email_visible">Show email</Label>
              </div>
              <div className="space-y-2">
                <Label>Phone</Label>
                <Input placeholder="+1..." {...contactForm.register("phone")} />
              </div>
              <div className="space-y-2">
                <Label>LinkedIn URL</Label>
                <Input placeholder="https://linkedin.com/in/..." {...contactForm.register("linkedin_url")} />
              </div>
              <div className="space-y-2">
                <Label>Other</Label>
                <Input placeholder="Other contact info" {...contactForm.register("other")} />
              </div>
              <Button type="submit" disabled={patchContact.isPending}>
                Save contact
              </Button>
            </form>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
