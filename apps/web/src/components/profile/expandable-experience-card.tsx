"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { isPlaceholderChildCard, getChildDisplayTitle, getChildDisplaySummary } from "@/components/builder/card/card-details";
import type { SavedCardFamily } from "@/types";

interface ExpandableExperienceCardProps {
  family: SavedCardFamily;
  index: number;
}

export function ExpandableExperienceCard({ family, index }: ExpandableExperienceCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const { parent, children } = family;
  const visibleChildren = children.filter((c) => !isPlaceholderChildCard(c as Record<string, unknown>));
  const hasChildren = visibleChildren.length > 0;

  return (
    <motion.li
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, duration: 0.25 }}
      className="relative list-none"
    >
      {/* ── Parent card ── */}
      <div
        className={cn(
          "relative rounded-xl border border-border bg-card p-4 transition-colors",
          hasChildren && "cursor-pointer hover:bg-accent/50"
        )}
        onClick={hasChildren ? () => setIsExpanded((v) => !v) : undefined}
        role={hasChildren ? "button" : undefined}
        tabIndex={hasChildren ? 0 : undefined}
        onKeyDown={
          hasChildren
            ? (e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setIsExpanded((v) => !v);
                }
              }
            : undefined
        }
        aria-expanded={hasChildren ? isExpanded : undefined}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-foreground truncate">
              {parent.title || parent.company_name || "Untitled"}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {[parent.company_name, parent.normalized_role, parent.location]
                .filter(Boolean)
                .join(" / ")}
            </p>
            {parent.summary && (
              <p className="text-sm text-muted-foreground mt-2 line-clamp-2">{parent.summary}</p>
            )}
            {[parent.start_date, parent.end_date].filter(Boolean).length > 0 && (
              <p className="text-xs text-muted-foreground/70 mt-1.5">
                {[parent.start_date, parent.end_date].filter(Boolean).join(" - ")}
              </p>
            )}
          </div>
          {hasChildren && (
            <div className="flex items-center gap-1.5 flex-shrink-0 mt-0.5">
              <span className="text-xs text-muted-foreground tabular-nums">
                {children.length}
              </span>
              <motion.div
                animate={{ rotate: isExpanded ? 180 : 0 }}
                transition={{ duration: 0.2 }}
                className="text-muted-foreground"
              >
                <ChevronDown className="h-4 w-4" />
              </motion.div>
            </div>
          )}
        </div>
      </div>

      {/* ── Thread children ── */}
      <AnimatePresence>
        {isExpanded && hasChildren && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className="relative pl-7 pt-0">
              {/* Vertical thread line */}
              <span
                className="thread-line thread-line-animated top-0 bottom-4"
                aria-hidden
              />

              <ul className="relative space-y-0">
                {visibleChildren.map((child, childIdx) => (
                  <motion.li
                    key={child.id}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{
                      delay: childIdx * 0.06,
                      duration: 0.2,
                    }}
                    className="relative py-2.5 first:pt-3"
                  >
                    {/* Thread node */}
                    <span
                      className={cn(
                        "thread-node thread-node-sm thread-node-animated",
                        "top-1/2 -translate-y-1/2"
                      )}
                      style={{ animationDelay: `${childIdx * 60 + 100}ms` }}
                      aria-hidden
                    />

                    {/* Child block */}
                    <div className="ml-5 rounded-lg border border-border/60 bg-accent/30 px-3 py-2.5 transition-colors hover:bg-accent/60">
                      <p className="text-sm font-medium text-foreground">
                        {getChildDisplayTitle(child) || "Detail"}
                      </p>
                      {getChildDisplaySummary(child) && (
                        <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                          {getChildDisplaySummary(child)}
                        </p>
                      )}
                      {(() => {
                        const items = child.items;
                        if (Array.isArray(items) && items.length > 0) {
                          return (
                            <div className="space-y-1 mt-2">
                              {items.map((it, i) => (
                                <div key={i} className="text-xs text-muted-foreground">
                                  <span className="font-medium text-foreground">
                                    {String((it as Record<string, unknown>).subtitle ?? (it as Record<string, unknown>).title ?? "")}
                                  </span>
                                  {((it as Record<string, unknown>).sub_summary ?? (it as Record<string, unknown>).description) ? (
                                    <span className="ml-1.5">— {String((it as Record<string, unknown>).sub_summary ?? (it as Record<string, unknown>).description ?? "")}</span>
                                  ) : null}
                                </div>
                              ))}
                            </div>
                          );
                        }
                        const tagsFromItems = (child.items ?? []).map((it) => String((it as Record<string, unknown>).subtitle ?? (it as Record<string, unknown>).title ?? "")).filter(Boolean);
                        if (tagsFromItems.length > 0) {
                          return (
                            <div className="flex flex-wrap gap-1 mt-2">
                              {tagsFromItems.map((tag, tagIdx) => (
                                <span
                                  key={tagIdx}
                                  className="rounded-md bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground"
                                >
                                  {tag}
                                </span>
                              ))}
                            </div>
                          );
                        }
                        return null;
                      })()}
                    </div>
                  </motion.li>
                ))}
              </ul>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.li>
  );
}
