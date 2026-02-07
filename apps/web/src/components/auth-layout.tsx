"use client";

import { motion } from "framer-motion";
import { HeroBg, DepthGrid } from "@/components/hero-bg";

type AuthLayoutProps = {
  title: string;
  subtitle: string;
  children: React.ReactNode;
};

export function AuthLayout({ title, subtitle, children }: AuthLayoutProps) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4 relative">
      <HeroBg />
      <DepthGrid />
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: "easeOut" }}
        className="w-full max-w-sm relative z-10"
      >
        <div className="text-center mb-8">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground text-balance">
            {title}
          </h1>
          <p className="text-muted-foreground mt-2 text-sm leading-relaxed">{subtitle}</p>
        </div>
        {children}
      </motion.div>
    </div>
  );
}
