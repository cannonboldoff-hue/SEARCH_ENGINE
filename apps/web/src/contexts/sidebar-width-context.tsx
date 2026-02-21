"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

export const MIN_SIDEBAR_WIDTH = 200;
export const MAX_SIDEBAR_WIDTH = 520;

export const SIDEBAR_WIDTH_EXPANDED = 260;
export const SIDEBAR_WIDTH_COLLAPSED = 64;

interface SidebarWidthContextValue {
  sidebarWidth: number;
  isCollapsed: boolean;
  setSidebarWidth: (value: number) => void;
  setIsCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;
}

const SidebarWidthContext = createContext<SidebarWidthContextValue | undefined>(undefined);

export function SidebarWidthProvider({ children }: { children: ReactNode }) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const sidebarWidth = isCollapsed ? SIDEBAR_WIDTH_COLLAPSED : SIDEBAR_WIDTH_EXPANDED;

  const setSidebarWidth = useCallback((_value: number) => {
    // Sidebar width is derived from isCollapsed; no-op to keep API stable
  }, []);

  const toggleSidebar = useCallback(() => setIsCollapsed((c) => !c), []);

  const contextValue = useMemo(
    () => ({ sidebarWidth, isCollapsed, setSidebarWidth, setIsCollapsed, toggleSidebar }),
    [sidebarWidth, isCollapsed, setSidebarWidth, setIsCollapsed, toggleSidebar]
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
