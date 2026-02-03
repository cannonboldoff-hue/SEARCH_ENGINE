type PageLoadingProps = {
  message?: string;
  className?: string;
};

export function PageLoading({ message = "Loading…", className }: PageLoadingProps) {
  return (
    <div
      className={
        className ?? "min-h-[60vh] flex items-center justify-center"
      }
    >
      <div className="animate-pulse text-muted-foreground">{message}</div>
    </div>
  );
}
