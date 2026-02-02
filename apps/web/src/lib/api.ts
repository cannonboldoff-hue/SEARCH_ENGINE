import { API_BASE } from "./utils";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
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
  const res = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || err.message || String(res.status));
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
