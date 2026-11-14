// One small fetch wrapper: bearer token, JSON in and out, the backend's error envelope as a typed error.
const BASE = "/api/v1";
const TOKEN_KEY = "studease.token";

let token: string | null = null;
try { token = sessionStorage.getItem(TOKEN_KEY); } catch { /* storage blocked: the token lives in memory only */ }

export function setToken(value: string | null): void {
  token = value;
  try {
    if (value) sessionStorage.setItem(TOKEN_KEY, value);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch { /* storage blocked */ }
}
export const hasToken = (): boolean => token !== null;

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public requestId?: string) {
    super(message);
  }
}

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void): void { onUnauthorized = fn; }

type Query = Record<string, string | number | boolean | null | undefined>;

export async function api<T = any>(method: "GET" | "POST", path: string, opts: { query?: Query; body?: unknown; headers?: Record<string, string> } = {}): Promise<T> {
  const url = new URL(BASE + path, location.origin);
  for (const [k, v] of Object.entries(opts.query ?? {})) if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers: { ...(opts.body ? { "Content-Type": "application/json" } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...opts.headers },
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
  } catch {
    throw new ApiError(0, "NETWORK", "Cannot reach the server. Check your connection and try again.");
  }
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) {
    const e = data?.error;
    if (res.status === 401 && token && path !== "/auth/login") onUnauthorized();
    throw new ApiError(res.status, e?.code ?? "ERROR", e?.message ?? `Request failed (${res.status})`, e?.request_id);
  }
  return data as T;
}

export const get = <T = any>(path: string, query?: Query) => api<T>("GET", path, { query });
export const post = <T = any>(path: string, body?: unknown, headers?: Record<string, string>) => api<T>("POST", path, { body: body ?? {}, headers });
