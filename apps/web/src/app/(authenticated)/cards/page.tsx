"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { PenLine, Plus, LayoutGrid, Hammer } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { BackLink } from "@/components/back-link";
import { PageLoading } from "@/components/feedback";
import { V1CardDetails } from "@/components/builder/v1-card-details";
import { useExperienceCardFamilies } from "@/hooks";
import type { ExperienceCard, ExperienceCardChild } from "@/types";

function getParentId(parent: ExperienceCard | Record<string, unknown>): string {
  const p = parent as Record<string, unknown>;
  return String(p.id ?? p.card_id ?? "").trim();
}

export default function YourCardsPage() {
  const { data: savedFamilies = [], isLoading } = useExperienceCardFamilies();

  if (isLoading) {
    return (
      <PageLoading
        message="Loading experience cards..."
        className="py-12 flex flex-col items-center justify-center gap-3"
      />
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="max-w-3xl mx-auto space-y-6"
    >
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3 min-w-0">
          <BackLink href="/profile" className="flex-shrink-0" />
          <div className="flex items-center gap-2 min-w-0">
            <div className="h-9 w-9 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
              <LayoutGrid className="h-4 w-4 text-primary" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-foreground tracking-tight">
                Your Cards
              </h1>
              <p className="text-sm text-muted-foreground">
                {savedFamilies.length === 0
                  ? "No cards yet"
                  : `${savedFamilies.length} experience${savedFamilies.length !== 1 ? "s" : ""}`}
              </p>
            </div>
          </div>
        </div>
        <Link href="/builder">
          <Button variant="outline" className="min-h-[2.75rem] touch-manipulation">
            <Hammer className="h-4 w-4 mr-2" />
            Builder
          </Button>
        </Link>
      </div>

      {savedFamilies.length === 0 ? (
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.35 }}
          className="flex flex-col items-center justify-center py-16 px-4 rounded-xl border border-dashed border-border bg-muted/30 text-center"
        >
          <div className="h-14 w-14 rounded-full border-2 border-dashed border-muted-foreground/40 flex items-center justify-center mb-4">
            <LayoutGrid className="h-7 w-7 text-muted-foreground" />
          </div>
          <h2 className="text-base font-medium text-foreground mb-1">
            No experience cards yet
          </h2>
          <p className="text-sm text-muted-foreground max-w-sm mb-6">
            Create experience cards from your work history, projects, and achievements. They help others discover you in search.
          </p>
          <Link href="/builder">
            <Button size="lg" className="min-h-[2.75rem]">
              <Plus className="h-4 w-4 mr-2" />
              Create in Builder
            </Button>
          </Link>
        </motion.div>
      ) : (
        <div className="space-y-4">
          {savedFamilies.map((family, i) => (
            <motion.div
              key={getParentId(family.parent) || `family-${i}`}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05, duration: 0.3 }}
            >
              <Card className="overflow-hidden border border-border/80">
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="font-semibold text-foreground truncate">
                      {family.parent.title || family.parent.company_name || "Untitled experience"}
                    </h3>
                    {family.children.length > 0 && (
                      <span className="text-xs text-muted-foreground flex-shrink-0 tabular-nums">
                        {family.children.length} detail{family.children.length !== 1 ? "s" : ""}
                      </span>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="pt-0">
                  <V1CardDetails
                    card={family.parent as unknown as Record<string, unknown>}
                    summaryFullWidth
                  />
                  {family.children.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-border/50">
                      <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wider">
                        Details
                      </p>
                      <ul className="space-y-2">
                        {family.children.map((child: ExperienceCardChild) => (
                          <li
                            key={child.id}
                            className="text-sm text-muted-foreground pl-3 border-l-2 border-border/50"
                          >
                            <span className="font-medium text-foreground">
                              {child.title || child.summary || "Detail"}
                            </span>
                            {(child.company || child.time_range) && (
                              <span className="text-muted-foreground">
                                {" "}
                                — {[child.company, child.time_range].filter(Boolean).join(" · ")}
                              </span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      )}
    </motion.div>
  );
}
