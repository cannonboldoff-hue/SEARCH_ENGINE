"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ChevronDown,
  FileEdit,
  Hammer,
  LogOut,
  Search,
  Settings,
  User,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/auth";
import { CreditsBadge } from "@/components/credits-badge";
import { cn } from "@/lib/utils";

export function AppNav() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

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
    { href: "/profile", label: "Profile", icon: User },
    { href: "/builder", label: "Experience", icon: Hammer },
  ];

  const menuItems = [
    { href: "/onboarding/bio", label: "Edit Bio", icon: FileEdit },
    { href: "/settings", label: "Settings", icon: Settings },
  ];

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/50 glass">
      <div className="container flex h-14 items-center justify-between px-4">
        <Link
          href="/home"
          className="font-semibold text-lg text-foreground hover:text-primary transition-colors flex items-center gap-2"
        >
          <span className="text-primary">Discover</span>
        </Link>

        <nav className="flex items-center gap-1" aria-label="Main">
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

        <div className="flex items-center gap-3">
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
