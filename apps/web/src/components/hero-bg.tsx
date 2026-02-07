"use client";

/**
 * Minimal background for auth and hero sections.
 * Uses a subtle dot pattern and radial gradient for depth.
 */
export function HeroBg() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden>
      {/* Subtle radial gradient */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 60% 50% at 50% 0%, hsl(var(--accent)) 0%, transparent 70%)",
        }}
      />
    </div>
  );
}

/**
 * Subtle dot grid for texture.
 */
export function DepthGrid() {
  return (
    <div
      className="absolute inset-0 opacity-[0.04] pointer-events-none"
      aria-hidden
      style={{
        backgroundImage:
          "radial-gradient(circle, hsl(var(--foreground)) 1px, transparent 1px)",
        backgroundSize: "24px 24px",
      }}
    />
  );
}
