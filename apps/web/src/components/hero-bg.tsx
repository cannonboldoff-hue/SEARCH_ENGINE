"use client";

/**
 * Production hero background: mesh gradients + subtle 3D-style orbs (CSS only).
 * Used on login, signup, and top of Discover.
 */
export function HeroBg() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden>
      <div className="mesh-bg absolute inset-0" />
      {/* Subtle 3D-style orbs (CSS perspective + blur) */}
      <div
        className="absolute w-[min(80vw,520px)] aspect-square rounded-full opacity-30"
        style={{
          top: "-20%",
          left: "50%",
          transform: "translateX(-50%) perspective(800px) rotateX(12deg)",
          background:
            "radial-gradient(circle at 30% 30%, hsl(263 70% 60% / 0.4), hsl(199 89% 45% / 0.2) 40%, transparent 70%)",
          filter: "blur(40px)",
        }}
      />
      <div
        className="absolute w-[min(60vw,360px)] aspect-square rounded-full opacity-20"
        style={{
          bottom: "-10%",
          right: "-5%",
          background:
            "radial-gradient(circle at 70% 70%, hsl(199 89% 50% / 0.35), transparent 60%)",
          filter: "blur(32px)",
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
