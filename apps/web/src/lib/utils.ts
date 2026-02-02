import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// In dev, if no API URL is set, assume API runs on port 8000 (e.g. uvicorn)
const fromEnv = process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || "";
export const API_BASE =
  fromEnv ||
  (typeof window !== "undefined" && window.location?.hostname === "localhost"
    ? "http://localhost:8000"
    : "");
