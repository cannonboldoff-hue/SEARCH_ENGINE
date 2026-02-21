import { API_BASE } from "./constants";
import { AUTH_TOKEN_KEY } from "./auth-flow";

function normalizeErrorDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    if (first && typeof first === "object" && "msg" in first && typeof first.msg === "string")
      return first.msg;
    return detail.map((d) => (d && typeof d === "object" && "msg" in d ? d.msg : String(d))).join(", ");
  }
  return null;
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

export type ApiOptions = Omit<RequestInit, "body"> & { body?: unknown };

export async function api<T>(
  path: string,
  options: ApiOptions = {}
): Promise<T> {
  const { body, ...rest } = options;
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const url = `${API_BASE}${path}`;
  if (!url.startsWith("http")) {
    throw new Error("Set NEXT_PUBLIC_API_BASE_URL (e.g. http://localhost:8000) and ensure the API is running.");
  }

  let res: Response;
  try {
    res = await fetch(url, {
      ...rest,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    const msg =
      e instanceof TypeError && (e.message === "Failed to fetch" || e.message?.includes("fetch"))
        ? "Cannot reach the API. Check NEXT_PUBLIC_API_BASE_URL and that the API is running."
        : e instanceof Error
          ? e.message
          : "Network error";
    throw new Error(msg);
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const message = normalizeErrorDetail(err.detail) || err.message || String(res.status);
    throw new Error(message);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export function apiWithIdempotency<T>(
  path: string,
  idempotencyKey: string,
  options: ApiOptions = {}
): Promise<T> {
  const headers = {
    ...(options.headers as Record<string, string>),
    "Idempotency-Key": idempotencyKey,
  };
  return api<T>(path, { ...options, headers });
}

/** Upload a file (e.g. profile photo) via multipart/form-data. Returns JSON. */
export async function apiUpload<T>(
  path: string,
  formData: FormData,
  options: Omit<RequestInit, "body" | "headers"> = {}
): Promise<T> {
  const token = getToken();
  const headers: HeadersInit = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const url = `${API_BASE}${path}`;
  if (!url.startsWith("http")) {
    throw new Error("Set NEXT_PUBLIC_API_BASE_URL and ensure the API is running.");
  }
  const res = await fetch(url, {
    ...options,
    method: "POST",
    headers,
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const message = normalizeErrorDetail(err.detail) || err.message || String(res.status);
    throw new Error(message);
  }
  return res.json();
}
