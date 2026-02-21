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
        "text-sm text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-1.5 group min-h-[44px] min-w-[44px] py-2 -my-2 rounded-lg hover:bg-accent/50",
        className
      )}
    >
      <ArrowLeft className="h-4 w-4 sm:h-3.5 sm:w-3.5 transition-transform group-hover:-translate-x-0.5 shrink-0" />
      {children}
    </Link>
  );
}
