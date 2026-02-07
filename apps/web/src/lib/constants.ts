/**
 * App constants (env-derived and static).
 */

const fromEnv = process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ?? "";
const isLocal =
  typeof window !== "undefined" && window.location?.hostname === "localhost";

export const API_BASE = fromEnv || (isLocal ? "http://localhost:8000" : "");
