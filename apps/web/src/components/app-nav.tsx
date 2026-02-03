"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronDown, User, FileEdit, Hammer, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/auth";
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

  const menuItems = [
    { href: "/profile", label: "Profile", icon: User },
    { href: "/onboarding/bio", label: "Edit Bio", icon: FileEdit },
    { href: "/builder", label: "Builder", icon: Hammer },
  ];

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 items-center justify-between px-4">
        <Link
          href="/home"
          className="font-semibold text-lg text-foreground hover:text-primary transition-colors"
        >
          Search Engine
        </Link>

        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground truncate max-w-[140px] sm:max-w-[200px]">
            {user?.display_name || user?.email}
          </span>
          <div className="relative" ref={dropdownRef}>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="gap-1"
              aria-expanded={dropdownOpen}
              aria-haspopup="true"
            >
              <ChevronDown className={cn("h-4 w-4 transition-transform", dropdownOpen && "rotate-180")} />
            </Button>
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
                      "flex items-center gap-2 px-3 py-2 text-sm transition-colors hover:bg-accent",
                      pathname === href ? "bg-accent/50 text-foreground" : "text-foreground"
                    )}
                    role="menuitem"
                  >
                    <Icon className="h-4 w-4 text-muted-foreground" />
                    {label}
                  </Link>
                ))}
                <button
                  type="button"
                  onClick={() => {
                    setDropdownOpen(false);
                    logout();
                  }}
                  className="flex w-full items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-accent hover:text-destructive transition-colors"
                  role="menuitem"
                >
                  <LogOut className="h-4 w-4 text-muted-foreground" />
                  Logout
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
