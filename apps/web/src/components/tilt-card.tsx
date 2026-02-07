"use client";

import { useRef, type ReactNode } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import { cn } from "@/lib/utils";

type TiltCardProps = {
  children: ReactNode;
  className?: string;
  /** Max tilt in degrees (default 8) */
  maxTilt?: number;
  /** Scale on hover (default 1.02) */
  scale?: number;
  /** Enable perspective container (default true) */
  perspective?: boolean;
  /** Disable tilt (e.g. on touch) */
  disabled?: boolean;
};

export function TiltCard({
  children,
  className,
  maxTilt = 8,
  scale = 1.02,
  perspective = true,
  disabled = false,
}: TiltCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const x = useMotionValue(0.5);
  const y = useMotionValue(0.5);

  const springConfig = { stiffness: 300, damping: 25 };
  const rotateX = useSpring(useTransform(y, [0, 1], [maxTilt, -maxTilt]), springConfig);
  const rotateY = useSpring(useTransform(x, [0, 1], [-maxTilt, maxTilt]), springConfig);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (disabled || !ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const w = rect.width;
    const h = rect.height;
    const mx = (e.clientX - rect.left) / w;
    const my = (e.clientY - rect.top) / h;
    x.set(mx);
    y.set(my);
  };

  const handleMouseLeave = () => {
    x.set(0.5);
    y.set(0.5);
  };

  return (
    <motion.div
      ref={ref}
      className={cn(perspective && "perspective-1000", !disabled && "transform-3d", className)}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={
        disabled
          ? undefined
          : {
              rotateX,
              rotateY,
              transformStyle: "preserve-3d",
              transformPerspective: 1000,
            }
      }
      whileHover={disabled ? undefined : { scale }}
      transition={{ type: "spring", stiffness: 300, damping: 24 }}
    >
      {disabled ? (
        children
      ) : (
        <div className="card-3d-inner" style={{ transform: "translateZ(6px)" }}>
          {children}
        </div>
      )}
    </motion.div>
  );
}
