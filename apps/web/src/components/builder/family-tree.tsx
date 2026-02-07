"use client";

import {
  useRef,
  useEffect,
  useState,
  useCallback,
} from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

/* ────────────────────────────────────────────── */
/*  Public types                                  */
/* ────────────────────────────────────────────── */

export interface TreeNode {
  id: string;
  label: string;
  sublabel?: string;
  tags?: string[];
  /** Extra metadata lines shown inside the card */
  meta?: string[];
}

interface FamilyTreeProps {
  parent: TreeNode;
  childNodes: TreeNode[];
  onNodeClick?: (id: string, kind: "parent" | "child") => void;
  selectedId?: string | null;
  className?: string;
}

/* ────────────────────────────────────────────── */
/*  Connector lines (SVG overlay)                 */
/* ────────────────────────────────────────────── */

interface LineCoord {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

/* ────────────────────────────────────────────── */
/*  Main tree component                           */
/* ────────────────────────────────────────────── */

export function FamilyTree({
  parent,
  childNodes,
  onNodeClick,
  selectedId,
  className,
}: FamilyTreeProps) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const parentRef = useRef<HTMLDivElement>(null);
  const childRefs = useRef<Map<string, HTMLDivElement>>(new Map());
  const [lines, setLines] = useState<LineCoord[]>([]);

  /* ── Recalculate connector lines ── */
  const recalc = useCallback(() => {
    if (!wrapperRef.current || !parentRef.current) return;
    const wr = wrapperRef.current.getBoundingClientRect();
    const pr = parentRef.current.getBoundingClientRect();

    // Parent bottom-center
    const px = pr.left + pr.width / 2 - wr.left;
    const py = pr.bottom - wr.top;

    const next: LineCoord[] = [];
    childRefs.current.forEach((el) => {
      if (!el) return;
      const cr = el.getBoundingClientRect();
      // Child top-center
      next.push({
        x1: px,
        y1: py,
        x2: cr.left + cr.width / 2 - wr.left,
        y2: cr.top - wr.top,
      });
    });
    setLines(next);
  }, []);

  useEffect(() => {
    recalc();
    const el = wrapperRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => recalc());
    ro.observe(el);
    return () => ro.disconnect();
  }, [recalc, childNodes.length]);

  /* Re-calc after children spring-animate in */
  useEffect(() => {
    const t = setTimeout(recalc, 450);
    return () => clearTimeout(t);
  }, [recalc, childNodes]);

  const setChildRef = useCallback(
    (id: string) => (el: HTMLDivElement | null) => {
      if (el) childRefs.current.set(id, el);
      else childRefs.current.delete(id);
    },
    []
  );

  const hasChildren = childNodes.length > 0;

  return (
    <div ref={wrapperRef} className={cn("relative w-full", className)}>
      {/* ── SVG connector lines layer ── */}
      {hasChildren && lines.length > 0 && (
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none"
          style={{ zIndex: 0 }}
        >
          {lines.map((l, i) => (
            <motion.line
              key={i}
              x1={l.x1}
              y1={l.y1}
              x2={l.x2}
              y2={l.y2}
              stroke="hsl(var(--border))"
              strokeWidth={2}
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: 1 }}
              transition={{
                delay: 0.12 + i * 0.06,
                duration: 0.4,
                ease: "easeOut",
              }}
            />
          ))}
          {/* Small dot at parent anchor */}
          {lines.length > 0 && (
            <circle
              cx={lines[0].x1}
              cy={lines[0].y1}
              r={4}
              fill="hsl(var(--primary))"
              opacity={0.5}
            />
          )}
        </svg>
      )}

      {/* ── Parent card (centered, wider) ── */}
      <div className="flex justify-center" style={{ position: "relative", zIndex: 1 }}>
        <div ref={parentRef}>
          <motion.button
            type="button"
            onClick={() => onNodeClick?.(parent.id, "parent")}
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 24 }}
            className={cn(
              "relative w-full max-w-sm rounded-xl border text-left transition-colors",
              "glass depth-shadow",
              "border-l-4 border-l-primary border-border/50",
              "px-5 py-4",
              selectedId === parent.id &&
                "ring-2 ring-ring ring-offset-2 ring-offset-background"
            )}
          >
            <p className="font-semibold text-sm text-foreground truncate">
              {parent.label}
            </p>
            {parent.sublabel && (
              <p className="text-xs text-muted-foreground mt-0.5 truncate">
                {parent.sublabel}
              </p>
            )}
            {parent.meta && parent.meta.length > 0 && (
              <div className="flex flex-wrap gap-x-3 gap-y-0 mt-1.5 text-[11px] text-muted-foreground">
                {parent.meta.map((m, i) => (
                  <span key={i} className="truncate">{m}</span>
                ))}
              </div>
            )}
          </motion.button>
        </div>
      </div>

      {/* ── Vertical gap for connectors ── */}
      {hasChildren && <div className="h-16" />}

      {/* ── Child cards row ── */}
      {hasChildren && (
        <div
          className="flex flex-wrap justify-center gap-4"
          style={{ position: "relative", zIndex: 1 }}
        >
          <AnimatePresence>
            {childNodes.map((child, i) => (
              <div key={child.id} ref={setChildRef(child.id)}>
                <motion.button
                  type="button"
                  onClick={() => onNodeClick?.(child.id, "child")}
                  initial={{ opacity: 0, y: 14 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 14 }}
                  transition={{
                    type: "spring",
                    stiffness: 300,
                    damping: 24,
                    delay: 0.08 + i * 0.05,
                  }}
                  className={cn(
                    "relative rounded-xl border text-left transition-colors",
                    "glass depth-shadow border-border/50",
                    "px-4 py-3 min-w-[160px] max-w-[220px]",
                    selectedId === child.id &&
                      "ring-2 ring-ring ring-offset-2 ring-offset-background"
                  )}
                >
                  <p className="font-medium text-xs text-foreground truncate">
                    {child.label}
                  </p>
                  {child.sublabel && (
                    <p className="text-[11px] text-muted-foreground mt-0.5 truncate">
                      {child.sublabel}
                    </p>
                  )}
                  {child.meta && child.meta.length > 0 && (
                    <div className="flex flex-wrap gap-x-2 gap-y-0 mt-1 text-[10px] text-muted-foreground">
                      {child.meta.map((m, j) => (
                        <span key={j} className="truncate">{m}</span>
                      ))}
                    </div>
                  )}
                  {child.tags && child.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      {child.tags.slice(0, 3).map((tag, j) => (
                        <span
                          key={j}
                          className="rounded-md bg-muted/80 px-1.5 py-0.5 text-[10px] text-muted-foreground"
                        >
                          {tag}
                        </span>
                      ))}
                      {child.tags.length > 3 && (
                        <span className="text-[10px] text-muted-foreground">
                          +{child.tags.length - 3}
                        </span>
                      )}
                    </div>
                  )}
                </motion.button>
              </div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
