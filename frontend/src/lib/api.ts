/**
 * Typed fetch wrapper for the FastAPI backend.
 *
 * Reads NEXT_PUBLIC_API_URL (the backend origin) and prefixes the versioned
 * `/api/v1` namespace. If you proxy `/api/*` through next.config rewrites,
 * leave NEXT_PUBLIC_API_URL empty so calls stay same-origin.
 */

import type { components } from "@/lib/api-types";

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

/**
 * La ressource n'existe pas (ou pas pour cette organisation) — par opposition
 * à une panne passagère.
 *
 * 403 est rangé ici avec 404 volontairement : sous RLS, une ressource d'une
 * autre organisation est indistinguable d'une ressource inexistante, et c'est
 * bien ce que l'on veut dire à l'utilisateur. Dans les deux cas, réessayer ne
 * changera rien.
 */
export function estIntrouvable(err: unknown): boolean {
  return err instanceof ApiError && (err.status === 404 || err.status === 403);
}

async function request<T>(path: string, init?: RequestInit, allowRefresh = true): Promise<T> {
  // FormData : c'est le navigateur qui pose le Content-Type (avec la frontière
  // multipart). Le forcer casserait l'envoi de fichiers.
  const isForm = init?.body instanceof FormData;
  const res = await fetch(`${BASE}${API_PREFIX}${path}`, {
    ...init,
    headers: {
      ...(isForm ? {} : { "Content-Type": "application/json" }),
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
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  /** Envoi de fichiers : le navigateur pose lui-même le Content-Type multipart. */
  upload: <T>(path: string, form: FormData) => request<T>(path, { method: "POST", body: form }),
};

// --- Contrats GÉNÉRÉS depuis l'OpenAPI FastAPI ---------------------------
// `src/lib/api-types.ts` est produit par `make types` (openapi-typescript).
// Ne jamais retyper à la main un schéma que le backend expose : un champ
// renommé côté Python doit casser la compilation ici.

type Schemas = components["schemas"];

export type Role = Schemas["MembershipRole"];
export type MembershipInfo = Schemas["MembershipOut"];
export type Me = Schemas["MeOut"];
export type Member = Schemas["MemberOut"];

// --- Contrats écrits à la main -------------------------------------------
// Ces endpoints renvoient `dict[str, Any]` côté FastAPI : l'OpenAPI n'en dit
// rien. Les types ci-dessous sont donc un contrat de lecture, à garder aligné
// avec les modules concernés (chemin cité au-dessus de chaque bloc).

// backend/app/sales/integrations.py

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
