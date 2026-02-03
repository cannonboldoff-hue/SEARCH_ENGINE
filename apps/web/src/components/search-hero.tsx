"use client";

import { motion } from "framer-motion";

/**
 * Large 3D hero section for the search/discover flow: floating nodes, depth,
 * and motion suggesting connection and discovery.
 */
export function SearchHero() {
  return (
    <div
      className="relative w-full min-h-[50vh] flex items-center justify-center overflow-hidden rounded-2xl -mx-4 px-4 perspective-[1200px]"
      style={{ transformStyle: "preserve-3d" }}
      aria-hidden
    >
      <div className="absolute inset-0 mesh-bg opacity-60 rounded-2xl" />
      {/* Central orb — focal point */}
      <motion.div
        className="absolute w-[min(70vw,420px)] aspect-square rounded-full"
        style={{
          background:
            "radial-gradient(circle at 35% 35%, hsl(263 70% 55% / 0.35), hsl(199 89% 48% / 0.2) 45%, transparent 70%)",
          filter: "blur(50px)",
          transform: "translateZ(-100px)",
        }}
        animate={{
          scale: [1, 1.15, 1],
          opacity: [0.4, 0.6, 0.4],
          rotateY: [0, 180, 360],
        }}
        transition={{
          duration: 12,
          repeat: Infinity,
          repeatType: "loop",
        }}
      />
      {/* Orbiting nodes — people and connections */}
      <motion.div
        className="absolute inset-0 flex items-center justify-center"
        style={{ transformStyle: "preserve-3d", perspective: 800 }}
        animate={{ rotateY: 360, rotateX: 12 }}
        transition={{ duration: 22, repeat: Infinity, ease: "linear" }}
      >
        <div className="relative w-[min(75vw,440px)] aspect-square">
          {[0, 1, 2, 3, 4, 5].map((i) => {
            const angle = (i / 6) * Math.PI * 2;
            const r = 48;
            const x = 50 + Math.cos(angle) * r;
            const y = 50 + Math.sin(angle) * r;
            return (
              <motion.div
                key={i}
                className="absolute w-3 h-3 rounded-full bg-primary/50 backdrop-blur-sm border border-primary/40 -ml-1.5 -mt-1.5"
                style={{
                  left: `${x}%`,
                  top: `${y}%`,
                  boxShadow: "0 0 16px hsl(var(--primary) / 0.35)",
                }}
                animate={{
                  scale: [1, 1.25, 1],
                  opacity: [0.7, 1, 0.7],
                }}
                transition={{
                  duration: 2.2,
                  repeat: Infinity,
                  delay: i * 0.18,
                }}
              />
            );
          })}
        </div>
      </motion.div>
      {/* Outer glow orbs */}
      <motion.div
        className="absolute w-[min(50vw,320px)] aspect-square rounded-full opacity-25"
        style={{
          left: "10%",
          top: "20%",
          background:
            "radial-gradient(circle at 60% 40%, hsl(199 89% 50% / 0.5), transparent 60%)",
          filter: "blur(40px)",
        }}
        animate={{
          x: [0, 20, 0],
          y: [0, -15, 0],
          scale: [1, 1.1, 1],
        }}
        transition={{ duration: 8, repeat: Infinity, repeatType: "reverse" }}
      />
      <motion.div
        className="absolute w-[min(45vw,280px)] aspect-square rounded-full opacity-20"
        style={{
          right: "5%",
          bottom: "15%",
          background:
            "radial-gradient(circle at 30% 70%, hsl(263 70% 55% / 0.45), transparent 65%)",
          filter: "blur(35px)",
        }}
        animate={{
          x: [0, -15, 0],
          y: [0, 10, 0],
          scale: [1, 1.08, 1],
        }}
        transition={{ duration: 7, repeat: Infinity, repeatType: "reverse" }}
      />
      {/* Overlay gradient for depth */}
      <div
        className="absolute inset-0 rounded-2xl pointer-events-none"
        style={{
          background:
            "linear-gradient(180deg, transparent 0%, hsl(var(--background) / 0.4) 70%, hsl(var(--background) / 0.8) 100%)",
        }}
      />
    </div>
  );
}
