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
      <h3 className="text-sm font-semibold text-foreground tracking-tight">Visibility</h3>
      <p className="text-sm text-muted-foreground leading-relaxed">
        Choose how you want to appear in search. If you select Hide Contact, you will not appear in search results at all.
      </p>
      <div className="flex flex-col gap-1.5">
        {([
          { value: "open_to_work" as const, label: "Open to Work", desc: "Show work preferences and allow contact" },
          { value: "open_to_contact" as const, label: "Open to Contact", desc: "Allow searchers to unlock your contact info" },
          { value: "hide_contact" as const, label: "Hide Contact", desc: "Do not appear in search results" },
        ] as const).map((opt) => (
          <label
            key={opt.value}
            className={cn(
              "flex items-start gap-3 cursor-pointer rounded-lg border p-3 transition-colors",
              visibilityMode === opt.value
                ? "border-primary/50 bg-accent"
                : "border-border hover:bg-accent/50"
            )}
          >
            <input
              type="radio"
              name="visibility_mode"
              checked={visibilityMode === opt.value}
              onChange={() => onVisibilityModeChange(opt.value)}
              className="h-4 w-4 border-border mt-0.5"
            />
            <div>
              <span className="text-sm font-medium text-foreground">{opt.label}</span>
              <p className="text-xs text-muted-foreground mt-0.5">{opt.desc}</p>
            </div>
          </label>
        ))}
      </div>

      {visibilityMode === "open_to_work" && (
        <div className="mt-4 space-y-4 pl-5 border-l-2 border-primary/20">
          <div className="space-y-2">
            <Label>Preferred locations (cities in India)</Label>
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={""}
                onChange={(e) => {
                  const city = e.target.value;
                  if (city && !workPreferredLocations.includes(city)) {
                    onWorkPreferredLocationsChange([...workPreferredLocations, city]);
                  }
                }}
                className={cn(
                  "rounded-lg border border-input bg-background px-3 py-2 text-sm min-w-[160px]",
                  "focus:outline-none focus:ring-1 focus:ring-ring/30 transition-colors"
                )}
              >
                <option value="">Add a city...</option>
                {INDIA_CITIES.filter((c) => !workPreferredLocations.includes(c)).map((city) => (
                  <option key={city} value={city}>
                    {city}
                  </option>
                ))}
              </select>
              {workPreferredLocations.length > 0 && (
                <span className="text-xs text-muted-foreground">
                  {workPreferredLocations.length} selected
                </span>
              )}
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
                      onClick={() =>
                        onWorkPreferredLocationsChange(workPreferredLocations.filter((c) => c !== city))
                      }
                      className="text-muted-foreground hover:text-foreground ml-0.5"
                      aria-label={`Remove ${city}`}
                    >
                      {"x"}
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="work_salary_min">{"Minimum package (Rs./year, optional)"}</Label>
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
