import { cookies } from "next/headers";
import { cache } from "react";

import type { Me } from "@/lib/api";

/**
 * Lecture serveur du contexte utilisateur, pour les gardes de segment.
 *
 * Le navigateur ne parle qu'au 3010 ; ici on est DANS le serveur Next, donc on
 * appelle FastAPI directement (BACKEND_URL) en relayant le cookie httpOnly.
 * `cache` dédoublonne l'appel : la coquille applicative et la garde du segment
 * consomment le même /me pour un rendu donné.
 */
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8010";

export const getMe = cache(async (): Promise<Me | null> => {
  const jar = await cookies();
  const access = jar.get("access")?.value;
  if (!access) return null;

  const res = await fetch(`${BACKEND_URL}/api/v1/me`, {
    headers: { cookie: `access=${access}` },
    cache: "no-store",
  });
  return res.ok ? ((await res.json()) as Me) : null;
});
