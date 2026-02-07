"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LogOut, User, Coins, Shield, Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/contexts/auth-context";
import { useCredits, useVisibility, VISIBILITY_QUERY_KEY } from "@/hooks";
import { api } from "@/lib/api";
import { INDIA_CITIES } from "@/lib/india-cities";
import { cn } from "@/lib/utils";
import type { PatchVisibilityRequest, VisibilitySettingsResponse } from "@/types";

type VisibilityMode = "open_to_work" | "open_to_contact" | "no_contact";

const VISIBILITY_OPTIONS: Record<VisibilityMode, { label: string; desc: string }> = {
  open_to_work: {
    label: "Open to work",
    desc: "Location, minimum salary needed, and contact details can be shared.",
  },
  open_to_contact: {
    label: "Open to Contact",
    desc: "Only contact details can be shared. No location or salary.",
  },
  no_contact: {
    label: "No Contact",
    desc: "Nothing shared: no contact, no location, no salary.",
  },
};

function visibilityFromSettings(v: VisibilitySettingsResponse | undefined): VisibilityMode {
  if (!v) return "no_contact";
  if (v.open_to_work) return "open_to_work";
  if (v.open_to_contact) return "open_to_contact";
  return "no_contact";
}

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const { data: credits } = useCredits();
  const { data: visibility, isLoading: visibilityLoading } = useVisibility();
  const queryClient = useQueryClient();
  const [isEditingVisibility, setIsEditingVisibility] = useState(false);
  const [mode, setMode] = useState<VisibilityMode>("no_contact");
  const [workPreferredLocations, setWorkPreferredLocations] = useState<string[]>([]);
  const [workSalaryMin, setWorkSalaryMin] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (!visibility) return;
    setMode(visibilityFromSettings(visibility));
    setWorkPreferredLocations(visibility.work_preferred_locations ?? []);
    setWorkSalaryMin(visibility.work_preferred_salary_min != null ? String(visibility.work_preferred_salary_min) : "");
  }, [visibility]);

  const patchVisibility = useMutation({
    mutationFn: (body: PatchVisibilityRequest) =>
      api<VisibilitySettingsResponse>("/me/visibility", { method: "PATCH", body }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: VISIBILITY_QUERY_KEY });
      setIsEditingVisibility(false);
      setSaveError(null);
    },
    onError: (e: Error) => setSaveError(e.message),
  });

  const buildPayload = (): PatchVisibilityRequest => {
    if (mode === "open_to_work") {
      const minNum = workSalaryMin.trim() ? Number(workSalaryMin) : undefined;
      return {
        open_to_work: true,
        open_to_contact: false,
        work_preferred_locations: workPreferredLocations.length ? workPreferredLocations : undefined,
        work_preferred_salary_min: minNum != null && !Number.isNaN(minNum) ? minNum : null,
      };
    }
    if (mode === "open_to_contact") {
      return {
        open_to_work: false,
        open_to_contact: true,
        work_preferred_locations: [],
        work_preferred_salary_min: null,
      };
    }
    return {
      open_to_work: false,
      open_to_contact: false,
      work_preferred_locations: [],
      work_preferred_salary_min: null,
    };
  };

  const handleSaveVisibility = () => {
    setSaveError(null);
    patchVisibility.mutate(buildPayload());
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="max-w-xl mx-auto space-y-6"
    >
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage your account and preferences.
        </p>
      </div>

      {/* Account */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-muted flex items-center justify-center">
              <User className="h-4 w-4 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-base">Account</CardTitle>
              <CardDescription>
                Your sign-in identity.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="flex flex-col">
              <span className="text-xs text-muted-foreground">Email</span>
              <span className="text-sm text-foreground font-medium">{user?.email ?? "--"}</span>
            </div>
            {user?.display_name && (
              <div className="flex flex-col">
                <span className="text-xs text-muted-foreground">Display name</span>
                <span className="text-sm text-foreground font-medium">{user.display_name}</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Credits quick view */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-muted flex items-center justify-center">
              <Coins className="h-4 w-4 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-base">Credits</CardTitle>
              <CardDescription>Your current balance and purchase options.</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-semibold tabular-nums text-foreground">
                {credits?.balance ?? "--"}
              </span>
              <span className="text-sm text-muted-foreground">credits remaining</span>
            </div>
            <Link href="/credits">
              <Button variant="outline" size="sm">
                Buy credits
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>

      {/* Visibility */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-lg bg-muted flex items-center justify-center">
                <Eye className="h-4 w-4 text-muted-foreground" />
              </div>
              <div>
                <CardTitle className="text-base">Visibility</CardTitle>
                <CardDescription>
                  Open to work: location, minimum salary needed, and contact details are shared.
                </CardDescription>
                <CardDescription>
                  Open to contact: only contact details.
                </CardDescription>
                <CardDescription>
                  No contact: nothing shared.
                </CardDescription>
              </div>
            </div>
            {!visibilityLoading && !isEditingVisibility && (
              <Button variant="outline" size="sm" onClick={() => setIsEditingVisibility(true)}>
                Edit
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {visibilityLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : isEditingVisibility ? (
            <>
              <div className="flex flex-col gap-1.5">
                <Label className="text-xs text-muted-foreground">Choose one</Label>
                {(["open_to_work", "open_to_contact", "no_contact"] as const).map((opt) => (
                  <label
                    key={opt}
                    className={cn(
                      "flex items-start gap-3 cursor-pointer rounded-lg border p-3 transition-colors",
                      mode === opt ? "border-primary/50 bg-accent" : "border-border hover:bg-accent/50"
                    )}
                  >
                    <input
                      type="radio"
                      name="visibility_mode"
                      checked={mode === opt}
                      onChange={() => setMode(opt)}
                      className="h-4 w-4 border-border mt-0.5"
                    />
                    <div>
                      <span className="text-sm font-medium text-foreground">{VISIBILITY_OPTIONS[opt].label}</span>
                      <p className="text-xs text-muted-foreground mt-0.5">{VISIBILITY_OPTIONS[opt].desc}</p>
                    </div>
                  </label>
                ))}
              </div>
              {mode === "open_to_work" && (
                <div className="space-y-4 pl-5 border-l-2 border-primary/20">
                  <div className="space-y-2">
                    <Label className="text-xs">Preferred locations (cities in India)</Label>
                    <div className="flex flex-wrap items-center gap-2">
                      <select
                        value=""
                        onChange={(e) => {
                          const city = e.target.value;
                          if (city && !workPreferredLocations.includes(city)) {
                            setWorkPreferredLocations([...workPreferredLocations, city]);
                          }
                        }}
                        className={cn(
                          "rounded-lg border border-input bg-background px-3 py-2 text-sm min-w-[160px]",
                          "focus:outline-none focus:ring-1 focus:ring-ring/30 transition-colors"
                        )}
                      >
                        <option value="">Add a city…</option>
                        {INDIA_CITIES.filter((c) => !workPreferredLocations.includes(c)).map((city) => (
                          <option key={city} value={city}>
                            {city}
                          </option>
                        ))}
                      </select>
                    </div>
                    {workPreferredLocations.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {workPreferredLocations.map((city) => (
                          <span
                            key={city}
                            className="inline-flex items-center gap-1 rounded-md bg-accent border border-border px-2 py-1 text-xs text-foreground"
                          >
                            {city}
                            <button
                              type="button"
                              onClick={() => setWorkPreferredLocations(workPreferredLocations.filter((c) => c !== city))}
                              className="text-muted-foreground hover:text-foreground ml-0.5"
                              aria-label={`Remove ${city}`}
                            >
                              ×
                            </button>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="work_salary_min">Minimum salary needed (₹/year)</Label>
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
              {saveError && (
                <p className="text-sm text-destructive">{saveError}</p>
              )}
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  onClick={handleSaveVisibility}
                  disabled={patchVisibility.isPending}
                >
                  Save
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setIsEditingVisibility(false);
                    setSaveError(null);
                    if (visibility) {
                      setMode(visibilityFromSettings(visibility));
                      setWorkPreferredLocations(visibility.work_preferred_locations ?? []);
                      setWorkSalaryMin(visibility.work_preferred_salary_min != null ? String(visibility.work_preferred_salary_min) : "");
                    }
                  }}
                >
                  Cancel
                </Button>
              </div>
            </>
          ) : (
            <div className="flex items-center justify-between">
              <p className="text-sm text-foreground font-medium">
                {VISIBILITY_OPTIONS[visibilityFromSettings(visibility)].label}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Sign out */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-muted flex items-center justify-center">
              <Shield className="h-4 w-4 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-base">Session</CardTitle>
              <CardDescription>
                Sign out of this device. You can sign back in with the same email.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Button
            variant="outline"
            size="sm"
            className="text-muted-foreground hover:text-destructive hover:border-destructive/50"
            onClick={() => logout()}
          >
            <LogOut className="h-3.5 w-3.5 mr-1.5" />
            Log out
          </Button>
        </CardContent>
      </Card>
    </motion.div>
  );
}
