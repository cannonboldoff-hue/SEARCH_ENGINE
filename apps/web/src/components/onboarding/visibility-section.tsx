"use client";

import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { INDIA_CITIES } from "@/lib/india-cities";
import { cn } from "@/lib/utils";

export type VisibilityMode = "open_to_work" | "open_to_contact" | "hide_contact";

type VisibilitySectionProps = {
  visibilityMode: VisibilityMode;
  onVisibilityModeChange: (mode: VisibilityMode) => void;
  workPreferredLocations: string[];
  onWorkPreferredLocationsChange: (locations: string[]) => void;
  workSalaryMin: string;
  onWorkSalaryMinChange: (value: string) => void;
};

export function VisibilitySection({
  visibilityMode,
  onVisibilityModeChange,
  workPreferredLocations,
  onWorkPreferredLocationsChange,
  workSalaryMin,
  onWorkSalaryMinChange,
}: VisibilitySectionProps) {
  return (
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
            onChange={() => onVisibilityModeChange("open_to_work")}
            className="h-4 w-4 border-border"
          />
          <span className="text-sm font-medium">Open to Work</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="radio"
            name="visibility_mode"
            checked={visibilityMode === "open_to_contact"}
            onChange={() => onVisibilityModeChange("open_to_contact")}
            className="h-4 w-4 border-border"
          />
          <span className="text-sm font-medium">Open to Contact</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="radio"
            name="visibility_mode"
            checked={visibilityMode === "hide_contact"}
            onChange={() => onVisibilityModeChange("hide_contact")}
            className="h-4 w-4 border-border"
          />
          <span className="text-sm font-medium">Hide Contact</span>
        </label>
      </div>

      {visibilityMode === "open_to_work" && (
        <div className="mt-4 space-y-4 pl-6 border-l-2 border-border/50">
          <div className="space-y-2">
            <Label>Preferred locations (cities in India)</Label>
            <div className="flex flex-wrap gap-2">
              <select
                value={""}
                onChange={(e) => {
                  const city = e.target.value;
                  if (city && !workPreferredLocations.includes(city)) {
                    onWorkPreferredLocationsChange([...workPreferredLocations, city]);
                  }
                }}
                className={cn(
                  "rounded-md border border-input bg-background px-3 py-2 text-sm min-w-[160px]",
                  "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                )}
              >
                <option value="">Add a city…</option>
                {INDIA_CITIES.filter((c) => !workPreferredLocations.includes(c)).map((city) => (
                  <option key={city} value={city}>
                    {city}
                  </option>
                ))}
              </select>
              {workPreferredLocations.length > 0 && (
                <span className="text-xs text-muted-foreground self-center">
                  {workPreferredLocations.length} selected
                </span>
              )}
            </div>
            {workPreferredLocations.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {workPreferredLocations.map((city) => (
                  <span
                    key={city}
                    className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-1 text-sm"
                  >
                    {city}
                    <button
                      type="button"
                      onClick={() =>
                        onWorkPreferredLocationsChange(workPreferredLocations.filter((c) => c !== city))
                      }
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
            <Label htmlFor="work_salary_min">Minimum package (₹/year, optional)</Label>
            <Input
              id="work_salary_min"
              type="number"
              min={0}
              placeholder="e.g. 800000"
              value={workSalaryMin}
              onChange={(e) => onWorkSalaryMinChange(e.target.value)}
              className="bg-background"
            />
          </div>
        </div>
      )}
    </section>
  );
}
