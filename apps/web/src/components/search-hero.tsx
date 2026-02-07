"use client";

/**
 * Minimal hero section with subtle gradient for the search/discover flow.
 */
export function SearchHero() {
  return (
    <div
      className="relative w-full py-16 sm:py-24 flex items-center justify-center overflow-hidden"
      aria-hidden
    >
      {/* Subtle radial gradient */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 70% 50% at 50% 20%, hsl(var(--accent)) 0%, transparent 70%)",
        }}
      />
    </div>
  );
}
