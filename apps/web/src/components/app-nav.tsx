"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/auth";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/builder", label: "Builder" },
  { href: "/search", label: "Search" },
  { href: "/settings", label: "Settings" },
];

export function AppNav() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 items-center justify-between px-4">
        <Link href="/builder" className="font-semibold text-lg">
          Search Engine
        </Link>
        <nav className="flex items-center gap-1">
          {navItems.map(({ href, label }) => (
            <Link key={href} href={href}>
              <Button
                variant="ghost"
                size="sm"
                className={cn(pathname === href && "bg-accent")}
              >
                {label}
              </Button>
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground truncate max-w-[120px]">
            {user?.display_name || user?.email}
          </span>
          <Button variant="outline" size="sm" onClick={logout}>
            Log out
          </Button>
        </div>
      </div>
    </header>
  );
}
