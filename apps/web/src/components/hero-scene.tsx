"use client";

import React from "react";

/**
 * CSS-only hero scene — same visual feel as the 3D hero without WebGL/React Three Fiber.
 * Use this to avoid ReactCurrentOwner / React instance conflicts with @react-three/fiber in Next.js.
 */
export function HeroScene() {
  return (
    <div className="hero-scene w-full h-[320px] sm:h-[380px] relative flex items-center justify-center overflow-hidden">
      {/* Central orb */}
      <div
        className="absolute w-32 h-32 sm:w-40 sm:h-40 rounded-full opacity-90 animate-[hero-float_6s_ease-in-out_infinite]"
        style={{
          background:
            "radial-gradient(circle at 30% 30%, #e8e8e8, #c0c0c0 40%, #888 100%)",
          boxShadow:
            "inset -8px -8px 24px rgba(255,255,255,0.4), inset 8px 8px 24px rgba(0,0,0,0.15), 0 0 60px rgba(128,128,128,0.2)",
        }}
      />
      {/* Orbital rings */}
      <div className="absolute w-48 h-48 sm:w-56 sm:h-56 rounded-full border border-white/20 animate-[hero-spin_12s_linear_infinite]" />
      <div
        className="absolute w-64 h-64 sm:w-72 sm:h-72 rounded-full border border-white/15 animate-[hero-spin_16s_linear_infinite_reverse]"
        style={{ transform: "rotateX(60deg)" }}
      />
      <div className="absolute w-80 h-80 sm:w-96 sm:h-96 rounded-full border border-white/10 animate-[hero-spin_20s_linear_infinite]" />
      {/* Floating nodes */}
      {Array.from({ length: 24 }).map((_, i) => (
        <div
          key={i}
          className="hero-node absolute rounded-full bg-white/60 animate-[hero-node-pulse_2.5s_ease-in-out_infinite]"
          style={{
            width: 4 + (i % 3) * 2,
            height: 4 + (i % 3) * 2,
            left: `${50 + 42 * Math.cos((i / 24) * Math.PI * 2)}%`,
            top: `${50 + 42 * Math.sin((i / 24) * Math.PI * 2)}%`,
            animationDelay: `${i * 0.08}s`,
          }}
        />
      ))}
      {/* Fade edges */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 80% 80% at 50% 50%, transparent 40%, hsl(var(--background)) 100%)",
        }}
      />
    </div>
  );
}
