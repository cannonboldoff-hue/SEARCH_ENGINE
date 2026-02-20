"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

export const MIN_SIDEBAR_WIDTH = 200;
export const MAX_SIDEBAR_WIDTH = 520;

interface SidebarWidthContextValue {
  sidebarWidth: number;
  setSidebarWidth: (value: number) => void;
}

const SidebarWidthContext = createContext<SidebarWidthContextValue | undefined>(undefined);

/** Fixed width for GPT-style permanent sidebar (no resize) */
const DEFAULT_SIDEBAR_WIDTH = 260;

export function SidebarWidthProvider({ children }: { children: ReactNode }) {
  const [sidebarWidth] = useState(DEFAULT_SIDEBAR_WIDTH);
  const setSidebarWidth = useCallback((_value: number) => {
    // Sidebar is fixed width; no-op to keep API stable
  }, []);

  const contextValue = useMemo(
    () => ({ sidebarWidth, setSidebarWidth }),
    [sidebarWidth, setSidebarWidth]
  );

  return <SidebarWidthContext.Provider value={contextValue}>{children}</SidebarWidthContext.Provider>;
}

export function useSidebarWidth() {
  const context = useContext(SidebarWidthContext);
  if (!context) {
    throw new Error("useSidebarWidth must be used within a SidebarWidthProvider");
  }
  return context;
}
