"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useIsMobile } from "@/hooks";

export const MIN_SIDEBAR_WIDTH = 200;
export const MAX_SIDEBAR_WIDTH = 520;

/** Width when sidebar is collapsed (icon-only) */
export const COLLAPSED_SIDEBAR_WIDTH = 64;

/** Width when sidebar is expanded */
const EXPANDED_SIDEBAR_WIDTH = 260;

/** Width of mobile drawer when open */
export const MOBILE_DRAWER_WIDTH = 280;

interface SidebarWidthContextValue {
  sidebarWidth: number;
  setSidebarWidth: (value: number) => void;
  collapsed: boolean;
  setCollapsed: (value: boolean) => void;
  toggleCollapsed: () => void;
  isMobile: boolean;
  mobileSidebarOpen: boolean;
  setMobileSidebarOpen: (open: boolean) => void;
  openMobileSidebar: () => void;
  closeMobileSidebar: () => void;
  toggleMobileSidebar: () => void;
}

const SidebarWidthContext = createContext<SidebarWidthContextValue | undefined>(undefined);

export function SidebarWidthProvider({ children }: { children: ReactNode }) {
  const isMobile = useIsMobile();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  const desktopWidth = collapsed ? COLLAPSED_SIDEBAR_WIDTH : EXPANDED_SIDEBAR_WIDTH;
  const sidebarWidth = isMobile ? (mobileSidebarOpen ? MOBILE_DRAWER_WIDTH : 0) : desktopWidth;

  const setSidebarWidth = useCallback((_value: number) => {
    // Sidebar is fixed width; no-op to keep API stable
  }, []);
  const toggleCollapsed = useCallback(() => setCollapsed((c) => !c), []);
  const closeMobileSidebar = useCallback(() => setMobileSidebarOpen(false), []);
  const openMobileSidebar = useCallback(() => setMobileSidebarOpen(true), []);
  const toggleMobileSidebar = useCallback(() => setMobileSidebarOpen((o) => !o), []);

  const contextValue = useMemo(
    () => ({
      sidebarWidth,
      setSidebarWidth,
      collapsed,
      setCollapsed,
      toggleCollapsed,
      isMobile,
      mobileSidebarOpen,
      setMobileSidebarOpen,
      openMobileSidebar,
      closeMobileSidebar,
      toggleMobileSidebar,
    }),
    [
      sidebarWidth,
      setSidebarWidth,
      collapsed,
      setCollapsed,
      toggleCollapsed,
      isMobile,
      mobileSidebarOpen,
      setMobileSidebarOpen,
      openMobileSidebar,
      closeMobileSidebar,
      toggleMobileSidebar,
    ]
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
