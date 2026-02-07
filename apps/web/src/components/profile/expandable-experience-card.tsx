import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown } from "lucide-react";
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
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, duration: 0.25 }}
      className="relative"
    >
      <Card
        className={cn(
          "transition-colors",
          hasChildren && "cursor-pointer hover:bg-accent"
        )}
        onClick={hasChildren ? () => setIsExpanded(!isExpanded) : undefined}
      >
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
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
                <ChevronDown className="h-4 w-4" />
              </motion.div>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            {[parent.company_name, parent.normalized_role, parent.location, parent.start_date, parent.end_date]
              .filter(Boolean)
              .join(" / ")}
          </p>
        </CardHeader>
        <CardContent className="text-sm">
          {parent.summary && <p className="text-muted-foreground">{parent.summary}</p>}
        </CardContent>
      </Card>

      {/* Children cards */}
      <AnimatePresence>
        {isExpanded && hasChildren && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25 }}
            className="mt-2 ml-4 border-l border-border pl-4 overflow-hidden"
          >
            <ul className="space-y-2">
              {children.map((child, childIdx) => (
                <motion.li
                  key={child.id}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ delay: childIdx * 0.04, duration: 0.2 }}
                >
                  <div className="rounded-lg border border-border p-3">
                    <p className="text-sm font-medium text-foreground mb-1">
                      {child.title || child.headline || child.summary || "Detail"}
                    </p>
                    {child.summary && child.title && (
                      <p className="text-xs text-muted-foreground mb-1.5">{child.summary}</p>
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
                            className="rounded-md bg-muted px-1.5 py-0.5 text-xs text-muted-foreground"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
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
