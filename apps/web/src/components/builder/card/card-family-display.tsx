"use client";

import { motion } from "framer-motion";
import { V1CardDetails, isPlaceholderChildCard } from "./v1-card-details";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ExperienceCard, ExperienceCardChild } from "@/types";

export interface CardFamilyDisplayProps {
  parent: ExperienceCard | Record<string, unknown>;
  children: ExperienceCardChild[];
  index?: number;
}

export function CardFamilyDisplay({
  parent,
  children,
  index = 0,
}: CardFamilyDisplayProps) {
  const parentObj = parent as Record<string, unknown>;
  const visibleChildren = children.filter((c) => !isPlaceholderChildCard(c as Record<string, unknown>));
  const title =
    (parentObj.title as string) ??
    (parentObj.company_name as string) ??
    "Untitled";

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        type: "spring",
        stiffness: 300,
        damping: 28,
        delay: index * 0.05,
      }}
      className="relative"
    >
      <div className={cn(
        "rounded-2xl border border-border/40 bg-card overflow-hidden",
        "transition-all duration-200",
        "hover:border-border/70 hover:shadow-md",
      )}>
        <div className="p-4 sm:p-5">
          <div className="flex items-start justify-between gap-2">
            <h3 className="font-semibold text-[15px] text-foreground leading-snug">
              {title}
            </h3>
            {visibleChildren.length > 0 && (
              <span className="text-xs text-muted-foreground/60 flex-shrink-0 tabular-nums mt-0.5">
                {visibleChildren.length} detail{visibleChildren.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>
          <V1CardDetails
            card={parent as Record<string, unknown>}
            summaryFullWidth
            hideInternalFields
          />
        </div>

        {visibleChildren.length > 0 && (
          <div className="border-t border-border/30 bg-muted/20 px-4 sm:px-5 py-3">
            <div className="space-y-1.5">
              {visibleChildren.map((child, childIdx) => {
                const relationType = (child.relation_type ?? "")
                  .toString()
                  .trim();
                const relationDisplay = relationType
                  ? relationType.replace(/_/g, " ")
                  : "";

                return (
                  <motion.div
                    key={child.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: childIdx * 0.04, duration: 0.15 }}
                    className="flex items-start gap-2.5 rounded-lg px-2.5 py-2 -mx-1 transition-colors hover:bg-muted/40"
                  >
                    <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/40 mt-0.5 flex-shrink-0" />
                    <div className="min-w-0 flex-1">
                      {relationDisplay && (
                        <span className="inline-block text-[10px] uppercase tracking-wider text-primary/60 font-medium mb-0.5">
                          {relationDisplay}
                        </span>
                      )}
                      <p className="text-sm font-medium text-foreground leading-snug">
                        {child.title || child.summary || "Detail"}
                      </p>
                      {child.summary && (
                        <p className="text-xs text-muted-foreground/70 mt-0.5 line-clamp-1">
                          {child.summary}
                        </p>
                      )}
                      {child.time_range && (
                        <p className="text-[11px] text-muted-foreground/50 mt-0.5">{child.time_range}</p>
                      )}
                      {Array.isArray(child.tags) && child.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {child.tags.map((tag, i) => (
                            <span
                              key={`${tag}-${i}`}
                              className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary/80"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}
