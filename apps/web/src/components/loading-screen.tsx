"use client";

export function LoadingScreen({ message = "Loading..." }: { message?: string }) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-background gap-3">
      <div className="h-5 w-5 rounded-full border-2 border-muted-foreground/30 border-t-foreground animate-spin" />
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}
