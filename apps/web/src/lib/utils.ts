import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const fromEnv = process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ?? "";
const isLocal =
  typeof window !== "undefined" && window.location?.hostname === "localhost";
export const API_BASE = fromEnv || (isLocal ? "http://localhost:8000" : "");
