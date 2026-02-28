"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LockOpen, Settings, Compass, LayoutGrid, Hammer, Globe, PanelLeftClose, PanelLeft, Menu, MoreVertical, Trash2 } from "lucide-react";
import { useSidebarWidth, MOBILE_DRAWER_WIDTH } from "@/contexts/sidebar-width-context";
import { useProfileSchema } from "@/hooks/use-profile-v1";
import { useProfilePhoto } from "@/hooks/use-profile-photo";
import { cn } from "@/lib/utils";
import { CreditsBadge } from "@/components/credits-badge";
import { Button } from "@/components/ui/button";
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
  const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").trim().replace(/\/+$/, "");
  const logoSrc = apiBase ? `${apiBase}/img/kana_icon_512.png` : "/img/kana_icon_512.png";

  const pathname = usePathname();
  const searchParams = useSearchParams();
  const selectedSearchId = searchParams.get("id");
  const {
    sidebarWidth,
    collapsed,
    toggleCollapsed,
    isMobile,
    mobileSidebarOpen,
    closeMobileSidebar,
    toggleMobileSidebar,
  } = useSidebarWidth();

  const { data: profile } = useProfileSchema();
  const { blobUrl: profilePhotoBlob } = useProfilePhoto(profile?.photo_url ?? null);
  const accountName = (profile?.display_name || profile?.username || "Account").trim();
  const accountInitial = accountName ? accountName[0]?.toUpperCase() : "U";

  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: ["me", "searches"],
    queryFn: () => api<SavedSearchesResponse>("/me/searches?limit=200"),
  });

  const deleteSearchMutation = useMutation({
    mutationFn: (searchId: string) =>
      api(`/me/searches/${encodeURIComponent(searchId)}`, { method: "DELETE" }),
    onMutate: async (searchId: string) => {
      setOpenDropdownId(null);
      await queryClient.cancelQueries({ queryKey: ["me", "searches"] });
      const prev = queryClient.getQueryData<SavedSearchesResponse>(["me", "searches"]);
      if (prev?.searches) {
        queryClient.setQueryData<SavedSearchesResponse>(["me", "searches"], {
          ...prev,
          searches: prev.searches.filter((s) => s.id !== searchId),
        });
      }
      return { prev };
    },
    onError: (_err, _searchId, context) => {
      if (context?.prev) {
        queryClient.setQueryData(["me", "searches"], context.prev);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["me", "searches"] });
    },
  });

  const [openDropdownId, setOpenDropdownId] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (openDropdownId === null) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current?.contains(e.target as Node)) return;
      setOpenDropdownId(null);
    };
    document.addEventListener("click", handleClickOutside, true);
    return () => document.removeEventListener("click", handleClickOutside, true);
  }, [openDropdownId]);

  const sidebarItems = [
    { href: "/home", label: "Home", icon: Compass },
    { href: "/explore", label: "Explore", icon: Globe },
    { href: "/cards", label: "Your Cards", icon: LayoutGrid },
    { href: "/builder", label: "Builder", icon: Hammer },
    { href: "/unlocked", label: "Unlocked", icon: LockOpen },
  ];

  const searches = data?.searches ?? [];

  const navLinkClass = (isActive: boolean) =>
    cn(
      "flex items-center rounded-lg text-sm font-medium transition-colors min-h-[44px] min-w-[44px]",
      collapsed && !isMobile ? "justify-center px-0 py-2.5" : "gap-3 px-3 py-2.5",
      isActive ? "bg-accent text-foreground" : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
    );

  const handleNavClick = () => {
    if (isMobile) closeMobileSidebar();
  };

  return (
    <>
      {/* Mobile backdrop - close drawer when tapping outside */}
      {isMobile && mobileSidebarOpen && (
        <button
          type="button"
          aria-label="Close menu"
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-[2px] md:hidden"
          onClick={closeMobileSidebar}
        />
      )}

      {/* Left sidebar - overlay on mobile, permanent on desktop */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex-shrink-0 bg-background border-r border-border overflow-x-hidden min-w-0 transition-[transform] duration-200 ease-out",
          isMobile && "shadow-xl md:shadow-none",
          isMobile && !mobileSidebarOpen && "-translate-x-full"
        )}
        style={{
          width: isMobile ? MOBILE_DRAWER_WIDTH : sidebarWidth,
        }}
        aria-label="Main navigation"
      >
        <div className="flex flex-col h-full min-w-0 overflow-hidden">
          {/* Logo at top + collapse toggle (desktop) / menu close (mobile) */}
          <div
            className={cn(
              "flex-shrink-0 flex border-b border-border",
              collapsed && !isMobile ? "items-center justify-center py-2 min-h-[2.5rem]" : "flex-row items-center gap-1 px-2 py-4 min-h-[3.5rem]"
            )}
          >
            {(!collapsed || isMobile) && (
              <Link
                href="/home"
                onClick={handleNavClick}
                className="flex flex-1 items-center text-foreground hover:opacity-90 transition-opacity min-w-0 min-h-[44px]"
              >
                <span className="inline-block h-9 w-9 shrink-0 overflow-hidden rounded-full bg-muted">
                  <img src={logoSrc} alt="CONXA" className="block h-full w-full object-cover" style={{ borderRadius: '50%', transform: 'scale(1.25)' }} />
                </span>
                <span className="font-semibold text-sm truncate ml-2.5">CONXA</span>
              </Link>
            )}
            {isMobile ? (
              <button
                type="button"
                onClick={closeMobileSidebar}
                className="p-2.5 rounded-lg text-muted-foreground hover:bg-accent/50 hover:text-foreground transition-colors shrink-0 min-h-[44px] min-w-[44px] flex items-center justify-center"
                aria-label="Close menu"
              >
                <PanelLeftClose className="h-5 w-5" />
              </button>
            ) : (
              <button
                type="button"
                onClick={toggleCollapsed}
                className="p-2 rounded-lg text-muted-foreground hover:bg-accent/50 hover:text-foreground transition-colors shrink-0 min-h-[44px] min-w-[44px] flex items-center justify-center"
                aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              >
                {collapsed ? (
                  <PanelLeft className="h-5 w-5" />
                ) : (
                  <PanelLeftClose className="h-5 w-5" />
                )}
              </button>
            )}
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
                  onClick={handleNavClick}
                  className={navLinkClass(isActive)}
                  title={collapsed && !isMobile ? label : undefined}
                >
                  <Icon className="h-5 w-5 shrink-0" />
                  {(!collapsed || isMobile) && <span>{label}</span>}
                </Link>
              );
            })}

            {/* Your searches - section header (hidden when collapsed on desktop) */}
            {(!collapsed || isMobile) && (
              <div className="pt-4 pb-1">
                <p className="px-3 py-1 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Your searches
                </p>
              </div>
            )}
          </nav>

          {/* Your searches list - only this section scrolls (hidden when collapsed on desktop) */}
          {(!collapsed || isMobile) && (
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
                        {`${search.result_count} results · ${formatSearchDate(search.created_at)}`}
                      </span>
                    </>
                  );
                  const rowClass = cn(
                    "flex flex-col gap-0.5 px-3 py-2.5 rounded-lg text-sm min-w-0 min-h-[44px] justify-center",
                    isSearchActive ? "bg-accent text-foreground font-medium" : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
                  );
                  return (
                    <li key={search.id} className="min-w-0">
                      <div
                        ref={openDropdownId === search.id ? dropdownRef : undefined}
                        className="flex items-stretch min-w-0 gap-0.5 rounded-lg"
                      >
                        <Link
                          href={`/searches?id=${encodeURIComponent(search.id)}`}
                          onClick={handleNavClick}
                          className={cn("flex-1 min-w-0 search-row-link", rowClass)}
                        >
                          {content}
                        </Link>
                        <div className="relative flex-shrink-0 flex items-center">
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 min-h-[44px] min-w-[44px] text-muted-foreground hover:text-foreground"
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              setOpenDropdownId((id) => (id === search.id ? null : search.id));
                            }}
                            aria-label="Search options"
                            aria-expanded={openDropdownId === search.id}
                          >
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                          {openDropdownId === search.id && (
                            <div
                              className="absolute right-0 top-full z-50 mt-0.5 rounded-md border border-border bg-background px-1 py-1 shadow-md min-w-[8rem]"
                              role="menu"
                            >
                              <button
                                type="button"
                                role="menuitem"
                                className="w-full flex items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm text-destructive hover:bg-accent hover:text-destructive"
                                onClick={() => {
                                  deleteSearchMutation.mutate(search.id);
                                  setOpenDropdownId(null);
                                }}
                                disabled={deleteSearchMutation.isPending}
                              >
                                <Trash2 className="h-4 w-4 shrink-0" />
                                Delete
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
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
              onClick={handleNavClick}
              className={navLinkClass(pathname === "/profile" || pathname.startsWith("/profile"))}
              title={accountName}
              aria-label="Account"
            >
              {profilePhotoBlob ? (
                <img
                  src={profilePhotoBlob}
                  alt={accountName}
                  className="h-7 w-7 shrink-0 rounded-full object-cover bg-muted"
                />
              ) : (
                <span className="h-7 w-7 shrink-0 rounded-full bg-muted text-foreground/80 flex items-center justify-center text-xs font-semibold">
                  {accountInitial}
                </span>
              )}
              {(!collapsed || isMobile) && <span className="truncate">{accountName}</span>}
            </Link>

            <Link
              href="/settings"
              onClick={handleNavClick}
              className={navLinkClass(pathname === "/settings" || pathname.startsWith("/settings"))}
              title={collapsed && !isMobile ? "Settings" : undefined}
            >
              <Settings className="h-5 w-5 shrink-0" />
              {(!collapsed || isMobile) && <span>Settings</span>}
            </Link>
          </div>
        </div>
      </aside>

      {/* Top bar - hamburger on mobile, CONXA centered, credits on right */}
      <header
        className="sticky top-0 z-40 flex h-14 min-h-[44px] items-center border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80"
        style={{ marginLeft: sidebarWidth }}
      >
        <div className="grid h-full w-full grid-cols-3 items-center px-3 sm:px-4 gap-2">
          <div className="flex items-center min-w-0">
            {isMobile && (
              <button
                type="button"
                onClick={toggleMobileSidebar}
                className="p-2.5 rounded-lg text-muted-foreground hover:bg-accent/50 hover:text-foreground transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
                aria-label="Open menu"
              >
                <Menu className="h-5 w-5" />
              </button>
            )}
          </div>
          <Link
            href="/home"
            className="justify-self-center font-semibold text-sm text-foreground hover:text-foreground/90 transition-colors min-h-[44px] flex items-center"
          >
            CONXA
          </Link>
          <div className="flex items-center justify-self-end min-h-[44px]">
            <CreditsBadge />
          </div>
        </div>
      </header>
    </>
  );
}
