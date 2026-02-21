"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

export const MIN_SIDEBAR_WIDTH = 200;
export const MAX_SIDEBAR_WIDTH = 520;

/** Width when sidebar is collapsed (icon-only) */
export const COLLAPSED_SIDEBAR_WIDTH = 64;

/** Width when sidebar is expanded */
const EXPANDED_SIDEBAR_WIDTH = 260;

interface SidebarWidthContextValue {
  sidebarWidth: number;
  setSidebarWidth: (value: number) => void;
  collapsed: boolean;
  setCollapsed: (value: boolean) => void;
  toggleCollapsed: () => void;
}

const SidebarWidthContext = createContext<SidebarWidthContextValue | undefined>(undefined);

export function SidebarWidthProvider({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const sidebarWidth = collapsed ? COLLAPSED_SIDEBAR_WIDTH : EXPANDED_SIDEBAR_WIDTH;
  const setSidebarWidth = useCallback((_value: number) => {
    // Sidebar is fixed width; no-op to keep API stable
  }, []);
  const toggleCollapsed = useCallback(() => setCollapsed((c) => !c), []);

  const contextValue = useMemo(
    () => ({ sidebarWidth, setSidebarWidth, collapsed, setCollapsed, toggleCollapsed }),
    [sidebarWidth, setSidebarWidth, collapsed, setCollapsed, toggleCollapsed]
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
