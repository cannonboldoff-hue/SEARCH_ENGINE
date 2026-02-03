"use client";

import { motion } from "framer-motion";

/**
 * Production hero background: mesh gradients + subtle 3D-style orbs (CSS + motion).
 * Used on login, signup, and top of Discover.
 */
export function HeroBg() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden>
      <div className="mesh-bg absolute inset-0" />
      {/* Subtle 3D-style orbs with float animation */}
      <div className="absolute top-[-20%] left-1/2 -translate-x-1/2 w-[min(80vw,520px)] aspect-square perspective-[800px]">
        <motion.div
          className="w-full h-full rounded-full opacity-30"
          style={{
            background:
              "radial-gradient(circle at 30% 30%, hsl(263 70% 60% / 0.4), hsl(199 89% 45% / 0.2) 40%, transparent 70%)",
            filter: "blur(40px)",
            transformStyle: "preserve-3d",
          }}
          animate={{
            y: [0, -8],
            rotateX: [12, 14],
            scale: [1, 1.05],
          }}
          transition={{
            duration: 6,
            repeat: Infinity,
            repeatType: "reverse",
          }}
        />
      </div>
      <motion.div
        className="absolute w-[min(60vw,360px)] aspect-square rounded-full opacity-20"
        style={{
          bottom: "-10%",
          right: "-5%",
          background:
            "radial-gradient(circle at 70% 70%, hsl(199 89% 50% / 0.35), transparent 60%)",
          filter: "blur(32px)",
        }}
        animate={{
          y: [0, 6],
          scale: [1, 1.08],
        }}
        transition={{
          duration: 5,
          repeat: Infinity,
          repeatType: "reverse",
        }}
      />
    </div>
  );
}

/**
 * Subtle grid overlay for depth (optional).
 */
export function DepthGrid() {
  return (
    <div
      className="absolute inset-0 opacity-[0.03] pointer-events-none"
      aria-hidden
      style={{
        backgroundImage:
          "linear-gradient(hsl(var(--foreground)) 1px, transparent 1px), linear-gradient(90deg, hsl(var(--foreground)) 1px, transparent 1px)",
        backgroundSize: "4rem 4rem",
      }}
    />
  );
}
