import Link from "next/link";

type PageErrorProps = {
  message: string;
  backHref?: string;
  backLabel?: string;
  className?: string;
};

export function PageError({
  message,
  backHref = "/profile",
  backLabel = "← Back to profile",
  className,
}: PageErrorProps) {
  return (
    <div
      className={
        className ?? "min-h-[60vh] flex items-center justify-center"
      }
    >
      <div className="text-center space-y-4 max-w-md">
        <p className="text-destructive">{message}</p>
        <Link
          href={backHref}
          className="text-sm text-primary font-medium hover:underline"
        >
          {backLabel}
        </Link>
      </div>
    </div>
  );
}
