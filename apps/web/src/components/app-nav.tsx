"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ChevronDown,
  Hammer,
  LogOut,
  Search,
  Settings,
  User,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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

  const primaryNav = [
    { href: "/home", label: "Discover", icon: Search },
    { href: "/builder", label: "Experience", icon: Hammer },
  ];

  const menuItems = [
    { href: "/profile", label: "Profile", icon: User },
    { href: "/settings", label: "Settings", icon: Settings },
  ];

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    search.performSearch();
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/50 glass">
      <div className="container flex h-14 items-center justify-between gap-4 px-4">
        <Link
          href="/home"
          className="font-semibold text-lg text-foreground hover:text-primary transition-colors flex items-center gap-2 flex-shrink-0"
        >
          <span className="text-primary">Discover</span>
        </Link>

        {isDiscover && (
          <form
            onSubmit={handleSearchSubmit}
            className="flex-1 flex items-center gap-2 max-w-xl min-w-0"
          >
            <Input
              placeholder="Describe who you're looking for..."
              value={search.query}
              onChange={(e) => search.setQuery(e.target.value)}
              className="h-9 bg-background/50 border-border/70 flex-1 min-w-0"
            />
            <Button
              type="submit"
              size="sm"
              disabled={search.isSearching || !search.query.trim()}
              className="flex-shrink-0"
            >
              {search.isSearching ? "…" : "Search"}
            </Button>
          </form>
        )}

        <nav className="flex items-center gap-1 flex-shrink-0" aria-label="Main">
          {primaryNav.map(({ href, label, icon: Icon }) => {
            const isActive = pathname === href || (href === "/home" && pathname === "/");
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                  isActive
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
                )}
              >
                <Icon className="h-4 w-4" />
                <span className="hidden sm:inline">{label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-3 flex-shrink-0">
          <CreditsBadge />
          <div className="relative" ref={dropdownRef}>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="gap-1.5"
              aria-expanded={dropdownOpen}
              aria-haspopup="true"
            >
              <span className="text-sm text-muted-foreground truncate max-w-[120px] sm:max-w-[160px]">
                {user?.display_name || user?.email}
              </span>
              <ChevronDown
                className={cn("h-4 w-4 text-muted-foreground transition-transform", dropdownOpen && "rotate-180")}
              />
            </Button>
            {dropdownOpen && (
              <div
                className="absolute right-0 mt-1 w-52 rounded-xl border border-border bg-card/95 backdrop-blur-xl py-1.5 shadow-xl z-50 glow-ring"
                role="menu"
              >
                {menuItems.map(({ href, label, icon: Icon }) => (
                  <Link
                    key={href}
                    href={href}
                    onClick={() => setDropdownOpen(false)}
                    className={cn(
                      "flex items-center gap-2 px-3 py-2.5 text-sm transition-colors hover:bg-accent mx-1 rounded-lg",
                      pathname === href ? "bg-accent/50 text-foreground" : "text-foreground"
                    )}
                    role="menuitem"
                  >
                    <Icon className="h-4 w-4 text-muted-foreground" />
                    {label}
                  </Link>
                ))}
                <div className="border-t border-border/50 my-1.5" />
                <button
                  type="button"
                  onClick={() => {
                    setDropdownOpen(false);
                    logout();
                  }}
                  className="flex w-full items-center gap-2 px-3 py-2.5 text-sm text-foreground hover:bg-destructive/10 hover:text-destructive transition-colors mx-1 rounded-lg"
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
