"use client";

export function ErrorMessage({ message }: { message: string }) {
  return (
    <div className="text-sm text-destructive bg-destructive/10 rounded-lg p-3">
      {message}
    </div>
  );
}
