"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronDown, LogOut, Settings, User, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/auth-context";
import { useSearch } from "@/contexts/search-context";
import { CreditsBadge } from "@/components/credits-badge";
import { cn } from "@/lib/utils";

export function AppNav() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const search = useSearch();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const isDiscover = pathname === "/home" || pathname === "/";

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const menuItems = [
    { href: "/search", label: "Search", icon: Search },
    { href: "/profile", label: "Profile", icon: User },
    { href: "/settings", label: "Settings", icon: Settings },
  ];

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    search.performSearch();
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-background/80 backdrop-blur-sm">
      <div className="container flex h-14 items-center justify-between gap-4 px-4">
        <Link
          href="/home"
          className="font-semibold text-sm text-foreground transition-colors flex items-center gap-2 flex-shrink-0"
        >
          CONXA
        </Link>

        {isDiscover && (
          <form
            onSubmit={handleSearchSubmit}
            className="flex-1 flex items-center gap-2 max-w-lg min-w-0"
          >
            <div className="relative flex-1 min-w-0">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <input
                type="text"
                placeholder="Describe who you're looking for..."
                value={search.query}
                onChange={(e) => search.setQuery(e.target.value)}
                className="flex h-8 w-full rounded-md border border-border bg-muted/50 pl-8 pr-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring/30 transition-colors"
              />
            </div>
            <Button
              type="submit"
              size="sm"
              disabled={search.isSearching || !search.query.trim()}
              className="flex-shrink-0 h-8"
            >
              {search.isSearching ? "..." : "Search"}
            </Button>
          </form>
        )}

        <div className="flex items-center gap-2 flex-shrink-0">
          <CreditsBadge />
          <div className="relative" ref={dropdownRef}>
            <button
              type="button"
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="flex items-center gap-1.5 rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
              aria-expanded={dropdownOpen}
              aria-haspopup="true"
            >
              <span className="truncate max-w-[100px] sm:max-w-[140px]">
                {user?.display_name || user?.email}
              </span>
              <ChevronDown
                className={cn("h-3.5 w-3.5 transition-transform", dropdownOpen && "rotate-180")}
              />
            </button>
            {dropdownOpen && (
              <div
                className="absolute right-0 mt-1 w-48 rounded-lg border border-border bg-card py-1 shadow-lg z-50"
                role="menu"
              >
                {menuItems.map(({ href, label, icon: Icon }) => (
                  <Link
                    key={href}
                    href={href}
                    onClick={() => setDropdownOpen(false)}
                    className={cn(
                      "flex items-center gap-2 px-3 py-2 text-sm transition-colors hover:bg-accent mx-1 rounded-md",
                      pathname === href ? "bg-accent text-foreground" : "text-muted-foreground"
                    )}
                    role="menuitem"
                  >
                    <Icon className="h-4 w-4" />
                    {label}
                  </Link>
                ))}
                <div className="border-t border-border my-1" />
                <button
                  type="button"
                  onClick={() => {
                    setDropdownOpen(false);
                    logout();
                  }}
                  className="flex w-full items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors mx-1 rounded-md"
                  role="menuitem"
                >
                  <LogOut className="h-4 w-4" />
                  Log out
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
