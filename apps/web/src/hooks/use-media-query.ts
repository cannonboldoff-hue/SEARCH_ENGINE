"use client";

import { useState, useEffect } from "react";

const MOBILE_BREAKPOINT_PX = 768;

/**
 * Returns true when viewport width is below the mobile breakpoint (768px).
 * Defaults to false during SSR to avoid hydration mismatch.
 */
export function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT_PX - 1}px)`);
    const handler = () => setIsMobile(mql.matches);
    handler(); // set initial
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, []);

  return isMobile;
}
