"use client";

import { motion } from "framer-motion";
import { CardDetails, getChildDisplaySummary, getChildDisplayTitle, isPlaceholderChildCard } from "./card-details";
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
    String(parentObj.title ?? parentObj.company_name ?? "").trim() || "Untitled";

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
        "group rounded-xl border border-border bg-card overflow-hidden transition-colors",
        "hover:bg-accent/30",
      )}>
        <div className="p-4 sm:p-5">
          <div className="flex items-start justify-between gap-2">
            <h3 className="font-semibold text-[16px] text-foreground leading-snug">
              {title}
            </h3>
            {visibleChildren.length > 0 && (
              <span className="text-xs text-muted-foreground/60 flex-shrink-0 tabular-nums mt-0.5">
                {visibleChildren.length} detail{visibleChildren.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>
          <CardDetails
            card={parent as Record<string, unknown>}
            summaryFullWidth
            hideInternalFields
          />
        </div>

        {visibleChildren.length > 0 && (
          <div className="border-t border-border/30 bg-muted/20 px-4 sm:px-5 py-3">
            <div className="space-y-1.5">
              {visibleChildren.map((child, childIdx) => {
                const relationType = (child.child_type ?? "").toString().trim();
                const relationDisplay = relationType
                  ? relationType.replace(/_/g, " ")
                  : "";
                const title = getChildDisplayTitle(child);
                const summary = getChildDisplaySummary(child);
                const tags = (child.items ?? []).map((it) => String((it as Record<string, unknown>).subtitle ?? (it as Record<string, unknown>).title ?? "")).filter(Boolean);

                return (
                  <motion.div
                    key={child.id ?? `child-${childIdx}`}
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
                        {title || summary || "Detail"}
                      </p>
                      {summary && (
                        <p className="text-xs text-muted-foreground/70 mt-0.5 line-clamp-1">
                          {summary}
                        </p>
                      )}
                      {tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {tags.map((tag, i) => (
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
