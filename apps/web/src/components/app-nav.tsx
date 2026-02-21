"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { LockOpen, Settings, Compass, LayoutGrid, Hammer, Globe, PanelLeftClose, PanelLeft } from "lucide-react";
import { useSidebarWidth } from "@/contexts/sidebar-width-context";
import { useProfileV1 } from "@/hooks/use-profile-v1";
import { cn } from "@/lib/utils";
import { CreditsBadge } from "@/components/credits-badge";
import { api } from "@/lib/api";
import type { SavedSearchesResponse } from "@/types";

function truncateQuery(text: string, maxLen = 40): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen).trim() + "…";
}

function formatSearchDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
  }).format(date);
}

export function AppNav() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const selectedSearchId = searchParams.get("id");
  const { sidebarWidth, collapsed, toggleCollapsed } = useSidebarWidth();

  const { data: profile } = useProfileV1();
  const accountName = (profile?.display_name || profile?.username || "Account").trim();
  const accountInitial = accountName ? accountName[0]?.toUpperCase() : "U";

  const { data } = useQuery({
    queryKey: ["me", "searches"],
    queryFn: () => api<SavedSearchesResponse>("/me/searches"),
  });

  const sidebarItems = [
    { href: "/home", label: "Home", icon: Compass },
    { href: "/explore", label: "Explore", icon: Globe },
    { href: "/cards", label: "Your Cards", icon: LayoutGrid },
    { href: "/builder", label: "Builder", icon: Hammer },
    { href: "/unlocked", label: "Unlocked", icon: LockOpen },
  ];

  const searches = data?.searches ?? [];

  return (
    <>
      {/* Left sidebar - permanent, GPT-style */}
      <aside
        className="fixed inset-y-0 left-0 z-50 flex-shrink-0 bg-background border-r border-border overflow-x-hidden min-w-0"
        style={{ width: sidebarWidth }}
        aria-label="Main navigation"
      >
        <div className="flex flex-col h-full min-w-0 overflow-hidden">
          {/* Logo at top + collapse toggle (logo hidden when collapsed) */}
          <div
            className={cn(
              "flex-shrink-0 flex border-b border-border",
              collapsed ? "items-center justify-center py-2 min-h-[2.5rem]" : "flex-row items-center gap-1 px-2 py-4 min-h-[3.5rem]"
            )}
          >
            {!collapsed && (
              <Link
                href="/home"
                className="flex flex-1 items-center text-foreground hover:opacity-90 transition-opacity min-w-0"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground text-sm font-semibold">
                  C
                </span>
                <span className="font-semibold text-sm truncate ml-2.5">CONXA</span>
              </Link>
            )}
            <button
              type="button"
              onClick={toggleCollapsed}
              className="p-2 rounded-lg text-muted-foreground hover:bg-accent/50 hover:text-foreground transition-colors shrink-0"
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              {collapsed ? (
                <PanelLeft className="h-5 w-5" />
              ) : (
                <PanelLeftClose className="h-5 w-5" />
              )}
            </button>
          </div>

          {/* Nav links - fixed, not scrollable */}
          <nav className="flex-shrink-0 px-2 py-3 space-y-0.5">
            {sidebarItems.map(({ href, label, icon: Icon }) => {
              const isActive =
                pathname === href ||
                (href === "/home" && (pathname === "/" || pathname === "/home")) ||
                (href === "/explore" && pathname.startsWith("/explore")) ||
                (href === "/cards" && pathname.startsWith("/cards")) ||
                (href === "/builder" && pathname.startsWith("/builder"));
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "flex items-center rounded-lg text-sm font-medium transition-colors",
                    collapsed ? "justify-center px-0 py-2.5" : "gap-3 px-3 py-2.5",
                    isActive
                      ? "bg-accent text-foreground"
                      : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
                  )}
                  title={collapsed ? label : undefined}
                >
                  <Icon className="h-5 w-5 shrink-0" />
                  {!collapsed && <span>{label}</span>}
                </Link>
              );
            })}

            {/* Your searches - section header (hidden when collapsed) */}
            {!collapsed && (
              <div className="pt-4 pb-1">
                <p className="px-3 py-1 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Your searches
                </p>
              </div>
            )}
          </nav>

          {/* Your searches list - only this section scrolls (hidden when collapsed) */}
          {!collapsed && (
          <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden scrollbar-theme px-2 pb-2">
            {searches.length === 0 ? (
              <p className="px-3 py-2 text-xs text-muted-foreground/80">
                No searches yet
              </p>
            ) : (
              <ul className="space-y-0.5">
                {searches.map((search) => {
                  const isSearchActive =
                    pathname.startsWith("/searches") && selectedSearchId === search.id;
                  const content = (
                    <>
                      <span className="truncate font-medium block">
                        {truncateQuery(search.query_text)}
                      </span>
                      <span className="text-xs opacity-80">
                        {search.expired
                          ? `Expired · ${formatSearchDate(search.created_at)}`
                          : `${search.result_count} results · ${formatSearchDate(search.created_at)}`}
                      </span>
                    </>
                  );
                  return (
                    <li key={search.id} className="min-w-0">
                      {search.expired ? (
                        <span
                          className={cn(
                            "flex flex-col gap-0.5 px-3 py-2 rounded-lg text-sm block min-w-0",
                            "text-muted-foreground/60 opacity-70 cursor-not-allowed"
                          )}
                        >
                          {content}
                        </span>
                      ) : (
                        <Link
                          href={`/searches?id=${encodeURIComponent(search.id)}`}
                          className={cn(
                            "flex flex-col gap-0.5 px-3 py-2 rounded-lg text-sm transition-colors block min-w-0",
                            isSearchActive
                              ? "bg-accent text-foreground font-medium"
                              : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
                          )}
                        >
                          {content}
                        </Link>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
          )}

          {/* Account + Settings at bottom */}
          <div className="flex-shrink-0 border-t border-border px-2 py-3 space-y-0.5">
            <Link
              href="/profile"
              className={cn(
                "flex items-center rounded-lg text-sm font-medium transition-colors min-w-0",
                collapsed ? "justify-center px-0 py-2.5" : "gap-3 px-3 py-2.5",
                pathname === "/profile" || pathname.startsWith("/profile")
                  ? "bg-accent text-foreground"
                  : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
              )}
              title={accountName}
              aria-label="Account"
            >
              {profile?.photo_url ? (
                <img
                  src={profile.photo_url}
                  alt={accountName}
                  className="h-7 w-7 shrink-0 rounded-full object-cover bg-muted"
                  referrerPolicy="no-referrer"
                />
              ) : (
                <span className="h-7 w-7 shrink-0 rounded-full bg-muted text-foreground/80 flex items-center justify-center text-xs font-semibold">
                  {accountInitial}
                </span>
              )}
              {!collapsed && <span className="truncate">{accountName}</span>}
            </Link>

            <Link
              href="/settings"
              className={cn(
                "flex items-center rounded-lg text-sm font-medium transition-colors",
                collapsed ? "justify-center px-0 py-2.5" : "gap-3 px-3 py-2.5",
                pathname === "/settings" || pathname.startsWith("/settings")
                  ? "bg-accent text-foreground"
                  : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
              )}
              title={collapsed ? "Settings" : undefined}
            >
              <Settings className="h-5 w-5 shrink-0" />
              {!collapsed && <span>Settings</span>}
            </Link>
          </div>
        </div>
      </aside>

      {/* Top bar - CONXA centered in the main content area (right of sidebar) */}
      <header
        className="sticky top-0 z-40 flex h-14 items-center border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80"
        style={{ marginLeft: sidebarWidth }}
      >
        <div className="grid h-full w-full grid-cols-3 items-center px-4">
          <div />
          <Link
            href="/home"
            className="justify-self-center font-semibold text-sm text-foreground hover:text-foreground/90 transition-colors"
          >
            CONXA
          </Link>
          <div className="flex items-center justify-self-end">
            <CreditsBadge />
          </div>
        </div>
      </header>
    </>
  );
}
