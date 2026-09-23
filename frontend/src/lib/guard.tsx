import { Forbidden } from "@/components/layout/forbidden";
import type { Me } from "@/lib/api";
import { canAccess, sectionFor } from "@/lib/navigation";
import { getMe } from "@/lib/server-api";
import { reprendreSession } from "@/lib/session";

/**
 * Garde de segment, côté SERVEUR.
 *
 * Rend soit rien (accès accordé), soit l'écran d'accès refusé — que l'onglet
 * ait été masqué ou non. Le rôle vient de /me, donc du backend qui relit la
 * membership en base : le client ne peut pas se l'attribuer.
 *
 * Note : Next rend ici un écran 403 « propre » sans changer le code HTTP de la
 * page (la fonction `forbidden()` reste expérimentale). Le verrou qui compte
 * est celui de l'API, qui renvoie bien 403 sur la donnée.
 */
export async function guardSection(href: string): Promise<{ me: Me; denied: React.ReactNode }> {
  const me = await getMe();
  if (!me) reprendreSession(href);

  const section = sectionFor(href);
  const denied = canAccess(section, me.role) ? null : (
    <Forbidden section={section?.label ?? href} role={me.role} />
  );
  return { me, denied };
}
