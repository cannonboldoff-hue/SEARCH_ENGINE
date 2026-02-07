import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { SavedCardFamily } from "@/types";

interface ExpandableExperienceCardProps {
  family: SavedCardFamily;
  index: number;
}

export function ExpandableExperienceCard({ family, index }: ExpandableExperienceCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const { parent, children } = family;
  const hasChildren = children.length > 0;

  return (
    <motion.div
      initial={{ opacity: 0, x: -12, rotateY: 8 }}
      animate={{ opacity: 1, x: 0, rotateY: 0 }}
      transition={{ delay: index * 0.04, type: "spring", stiffness: 280, damping: 24 }}
      style={{ transformStyle: "preserve-3d", perspective: 800 }}
      className="relative"
    >
      <Card
        className={cn(
          "glass border-border/50 depth-shadow perspective-1000 transform-3d transition-all",
          hasChildren && "cursor-pointer hover-lift"
        )}
        onClick={hasChildren ? () => setIsExpanded(!isExpanded) : undefined}
      >
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <CardTitle className="text-base flex items-center gap-2">
              {parent.title || parent.company_name || "Untitled"}
              {hasChildren && (
                <span className="text-xs text-muted-foreground font-normal">
                  ({children.length} detail{children.length !== 1 ? "s" : ""})
                </span>
              )}
            </CardTitle>
            {hasChildren && (
              <motion.div
                animate={{ rotate: isExpanded ? 180 : 0 }}
                transition={{ duration: 0.2 }}
                className="text-muted-foreground flex-shrink-0"
              >
                <ChevronDown className="h-5 w-5" />
              </motion.div>
            )}
          </div>
          <p className="text-sm text-muted-foreground">
            {[parent.company_name, parent.normalized_role, parent.location, parent.start_date, parent.end_date]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {parent.summary && <p>{parent.summary}</p>}
        </CardContent>
      </Card>

      {/* Connection thread */}
      <AnimatePresence>
        {isExpanded && hasChildren && (
          <>
            <motion.span
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 24, opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="pointer-events-none absolute left-1/2 -translate-x-1/2 -bottom-6 w-px bg-border/60 origin-top"
              aria-hidden
            />
            <motion.span
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0, opacity: 0 }}
              transition={{ duration: 0.2, delay: 0.1 }}
              className="pointer-events-none absolute left-1/2 -translate-x-1/2 -bottom-1 h-2 w-2 rounded-full bg-primary/50 border border-primary/30"
              aria-hidden
            />
          </>
        )}
      </AnimatePresence>

      {/* Children cards */}
      <AnimatePresence>
        {isExpanded && hasChildren && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
            className="relative mt-8 overflow-hidden"
          >
            {/* Vertical spine for children */}
            <span
              className="pointer-events-none absolute left-1/2 -translate-x-1/2 -top-8 h-8 w-px bg-border/60"
              aria-hidden
            />
            <span
              className="pointer-events-none absolute left-1/2 -translate-x-1/2 top-2 bottom-3 w-px bg-border/60"
              aria-hidden
            />

            <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide text-center mb-3">
              Details
            </p>

            <ul className="space-y-3">
              {children.map((child, childIdx) => (
                <motion.li
                  key={child.id}
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -12 }}
                  transition={{ delay: childIdx * 0.05, duration: 0.2 }}
                  className="relative"
                >
                  {/* Node on the spine */}
                  <span
                    className="pointer-events-none absolute left-1/2 -translate-x-1/2 top-4 h-2 w-2 rounded-full bg-muted-foreground/40 border border-border/60"
                    aria-hidden
                  />

                  <div className="rounded-lg border border-border/40 bg-muted/30 p-3 sm:p-4">
                    <div className="min-w-0">
                      <p className="font-medium text-sm mb-1">
                        {child.title || child.headline || child.summary || "Detail"}
                      </p>
                      {child.summary && child.title && (
                        <p className="text-xs text-muted-foreground mb-2">{child.summary}</p>
                      )}
                      <div className="flex flex-wrap gap-x-3 text-xs text-muted-foreground">
                        {child.company && <span>{child.company}</span>}
                        {child.time_range && <span>{child.time_range}</span>}
                        {child.location && <span>{child.location}</span>}
                      </div>
                      {child.tags && child.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {child.tags.map((tag, tagIdx) => (
                            <span
                              key={tagIdx}
                              className="rounded-md bg-muted/80 px-2 py-0.5 text-xs text-muted-foreground"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </motion.li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
