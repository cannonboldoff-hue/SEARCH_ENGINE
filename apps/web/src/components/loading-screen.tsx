"use client";

export function LoadingScreen({ message = "Loading…" }: { message?: string }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="animate-pulse text-muted-foreground">{message}</div>
    </div>
  );
}
