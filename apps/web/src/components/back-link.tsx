import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { cn } from "@/lib/utils";

type BackLinkProps = {
  href?: string;
  children?: React.ReactNode;
  className?: string;
};

export function BackLink({ href = "/profile", children = "Back to profile", className }: BackLinkProps) {
  return (
    <Link
      href={href}
      className={cn(
        "text-sm text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-1.5 group",
        className
      )}
    >
      <ArrowLeft className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5" />
      {children}
    </Link>
  );
}
