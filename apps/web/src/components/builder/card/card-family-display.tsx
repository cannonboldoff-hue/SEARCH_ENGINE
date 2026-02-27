"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { V1CardDetails, isPlaceholderChildCard } from "./v1-card-details";
import { cn } from "@/lib/utils";
import { ChevronDown } from "lucide-react";
import type { ExperienceCard, ExperienceCardChild } from "@/types";

export interface CardFamilyDisplayProps {
  parent: ExperienceCard | Record<string, unknown>;
  children: ExperienceCardChild[];
  index?: number;
}

// Category colors and icons
const categoryConfig: Record<string, { bg: string; text: string; label: string }> = {
  RESPONSIBILITIES: { bg: "bg-slate-100 dark:bg-slate-900", text: "text-slate-700 dark:text-slate-300", label: "✓ Responsibilities" },
  COLLABORATIONS: { bg: "bg-blue-100 dark:bg-blue-900", text: "text-blue-700 dark:text-blue-300", label: "🤝 Collaborations" },
  METRICS: { bg: "bg-amber-100 dark:bg-amber-900", text: "text-amber-700 dark:text-amber-300", label: "📊 Metrics" },
  ACHIEVEMENTS: { bg: "bg-green-100 dark:bg-green-900", text: "text-green-700 dark:text-green-300", label: "🏆 Achievements" },
};

function getCategoryConfig(category: string) {
  const key = (category ?? "").toString().toUpperCase().trim();
  return categoryConfig[key] || { bg: "bg-muted", text: "text-muted-foreground", label: category };
}

function groupChildrenByCategory(children: ExperienceCardChild[]) {
  const grouped: Record<string, ExperienceCardChild[]> = {};
  children.forEach((child) => {
    const category = (child.relation_type ?? "").toString().trim().toUpperCase() || "OTHER";
    if (!grouped[category]) grouped[category] = [];
    grouped[category].push(child);
  });
  return grouped;
}

export function CardFamilyDisplay({
  parent,
  children,
  index = 0,
}: CardFamilyDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const parentObj = parent as Record<string, unknown>;
  const visibleChildren = children.filter((c) => !isPlaceholderChildCard(c as Record<string, unknown>));
  const groupedChildren = groupChildrenByCategory(visibleChildren);
  
  const title =
    (parentObj.title as string) ??
    (parentObj.company_name as string) ??
    "Untitled";

  const startDate = (parentObj.start_date as string) || null;
  const endDate = (parentObj.end_date as string) || null;
  const isCurrent = (parentObj.is_current as boolean) || false;
  const dateRange = startDate
    ? `${startDate} - ${endDate || (isCurrent ? "Ongoing" : "")}`
    : null;

  const company = (parentObj.company_name as string) || null;
  const location = (parentObj.location as string) || null;
  const summary = (parentObj.summary as string) || null;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        type: "spring",
        stiffness: 280,
        damping: 26,
        delay: index * 0.05,
      }}
      className="relative max-w-full min-w-0"
    >
      {/* Card container */}
      <div className="border border-border rounded-lg bg-card overflow-hidden hover:border-border/80 transition-colors">
        {/* Collapsed/header view */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full text-left p-4 sm:p-5 hover:bg-secondary/30 transition-colors focus:outline-none focus:ring-2 focus:ring-primary/20"
        >
          <div className="flex items-start justify-between gap-3 w-full min-w-0">
            {/* Left: Title and metadata */}
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-base text-foreground truncate">{title}</h3>
              
              {/* Company and location */}
              {(company || location) && (
                <p className="text-sm text-muted-foreground mt-1">
                  {[company, location].filter(Boolean).join(" • ")}
                </p>
              )}

              {/* Date range */}
              {dateRange && (
                <p className="text-xs text-muted-foreground mt-1 font-mono">{dateRange}</p>
              )}
            </div>

            {/* Right: Expand indicator and category counts */}
            <div className="flex flex-col items-end gap-2 flex-shrink-0">
              <ChevronDown
                className={cn(
                  "h-5 w-5 text-muted-foreground transition-transform duration-300",
                  isExpanded && "rotate-180"
                )}
              />
              {visibleChildren.length > 0 && (
                <div className="text-xs font-medium text-muted-foreground">
                  {visibleChildren.length} item{visibleChildren.length !== 1 ? "s" : ""}
                </div>
              )}
            </div>
          </div>
        </button>

        {/* Expanded details */}
        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.3 }}
              className="border-t border-border bg-secondary/20"
            >
              <div className="p-4 sm:p-5 space-y-5">
                {/* Summary section */}
                {summary && (
                  <div>
                    <p className="text-sm text-foreground leading-relaxed">{summary}</p>
                  </div>
                )}

                {/* Child items grouped by category */}
                {Object.entries(groupedChildren).map(([category, items]) => {
                  const config = getCategoryConfig(category);
                  return (
                    <div key={category} className="space-y-2">
                      <h4 className={cn("text-xs font-semibold uppercase tracking-wide px-2 py-1 rounded", config.bg, config.text)}>
                        {getCategoryConfig(category).label}
                      </h4>
                      <div className="space-y-2">
                        {items.map((child) => (
                          <div key={child.id} className="text-sm p-3 rounded bg-background/50 border border-border/40">
                            {child.title && (
                              <p className="font-medium text-foreground">{child.title}</p>
                            )}
                            {child.summary && (
                              <p className="text-muted-foreground mt-1 leading-relaxed">{child.summary}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
