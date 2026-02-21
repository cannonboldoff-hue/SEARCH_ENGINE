"use client";

import { motion } from "framer-motion";
import { TiltCard } from "@/components/tilt-card";
import { V1CardDetails } from "./v1-card-details";
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
  const title =
    (parentObj.title as string) ??
    (parentObj.company_name as string) ??
    "Untitled";

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 16, rotateX: -12, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, rotateX: 0, scale: 1 }}
      transition={{
        type: "spring",
        stiffness: 280,
        damping: 26,
        delay: index * 0.05,
      }}
      style={{ transformStyle: "preserve-3d", perspective: 800 }}
      className="relative max-w-full min-w-0"
    >
      <TiltCard
        disabled
        maxTilt={6}
        scale={1.01}
        className={cn(
          "rounded-xl border border-border/50 glass overflow-hidden max-w-full min-w-0",
          "border-l-4 border-l-primary depth-shadow"
        )}
      >
        <div className="p-4 sm:p-5 min-w-0">
          <div className="flex items-start justify-between gap-2 w-full min-w-0">
            <span className="flex items-center gap-2 min-w-0 flex-1 truncate">
              <span className="font-semibold text-sm truncate text-foreground">
                {title}
              </span>
              {children.length > 0 && (
                <span className="text-xs text-muted-foreground flex-shrink-0 tabular-nums">
                  {children.length} thread{children.length !== 1 ? "s" : ""}
                </span>
              )}
            </span>
          </div>
          <V1CardDetails
            card={parent as Record<string, unknown>}
            summaryFullWidth
            hideInternalFields
          />
        </div>
      </TiltCard>

      {children.length > 0 && (
        <div className="relative pl-7 pt-0 mt-0">
          <span
            className="thread-line top-0 bottom-3"
            aria-hidden
          />
          <ul className="relative space-y-0">
            {children.map((child, childIdx) => {
              const relationType = (child.relation_type ?? "")
                .toString()
                .trim();
              const relationDisplay = relationType
                ? relationType.replace(/_/g, " ").toUpperCase()
                : "";

              return (
                <motion.li
                  key={child.id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: childIdx * 0.06, duration: 0.2 }}
                  className="relative py-2 first:pt-3"
                >
                  <span
                    className={cn(
                      "thread-node thread-node-sm",
                      "top-1/2 -translate-y-1/2"
                    )}
                    aria-hidden
                  />
                  <div className="ml-5 rounded-lg border border-border/40 bg-accent/30 px-3 py-2.5">
                    <div className="min-w-0 flex-1">
                      {relationDisplay && (
                        <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-0.5">
                          {relationDisplay}
                        </p>
                      )}
                      <p className="font-medium text-sm text-foreground">
                        {child.title || child.summary || "Detail"}
                      </p>
                    </div>
                    {(child.summary || child.company || child.time_range) && (
                      <div className="mt-1.5 pt-1.5 border-t border-border/30 text-xs text-muted-foreground space-y-0.5">
                        {child.summary && (
                          <p className="line-clamp-2">{child.summary}</p>
                        )}
                        <div className="flex flex-wrap gap-x-3">
                          {child.company && <span>{child.company}</span>}
                          {child.time_range && (
                            <span>{child.time_range}</span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </motion.li>
              );
            })}
          </ul>
        </div>
      )}
    </motion.div>
  );
}
