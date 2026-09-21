/**
 * Typed fetch wrapper for the FastAPI backend.
 *
 * Reads NEXT_PUBLIC_API_URL (the backend origin) and prefixes the versioned
 * `/api/v1` namespace. If you proxy `/api/*` through next.config rewrites,
 * leave NEXT_PUBLIC_API_URL empty so calls stay same-origin.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";
const API_PREFIX = "/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit, allowRefresh = true): Promise<T> {
  const res = await fetch(`${BASE}${API_PREFIX}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  // Access token (15 min) expiré : on tente UNE rotation du refresh httpOnly
  // puis on rejoue la requête. Jamais de token en localStorage.
  if (res.status === 401 && allowRefresh && !path.startsWith("/auth/")) {
    const refreshed = await fetch(`${BASE}${API_PREFIX}/auth/refresh`, { method: "POST" });
    if (refreshed.ok) return request<T>(path, init, false);
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json())?.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }

  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

// --- Contrats du module auth (backend/app/auth/schemas.py) ---

export type Role = "owner" | "admin" | "sales" | "hr";

export interface MembershipInfo {
  organization_id: string;
  organization_name: string;
  organization_slug: string;
  role: Role;
}

export interface Me {
  id: string;
  email: string;
  full_name: string;
  org_id: string | null;
  role: Role | null;
  memberships: MembershipInfo[];
}

// --- Contrats du module sales (backend/app/sales/integrations.py) ---

export interface Integration {
  provider: string;
  instance_url: string | null;
  status: "connected";
}

export interface Org {
  id: string;
  name: string;
  slug: string;
}
