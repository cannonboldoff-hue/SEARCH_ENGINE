import Link from "next/link";

type BackLinkProps = {
  href?: string;
  children?: React.ReactNode;
  className?: string;
};

export function BackLink({ href = "/profile", children = "Back to profile", className }: BackLinkProps) {
  return (
    <Link
      href={href}
      className={
        className ??
        "text-sm text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-1 group"
      }
    >
      <span className="transition-transform group-hover:-translate-x-0.5">←</span> {children}
    </Link>
  );
}
