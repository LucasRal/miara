import { redirect } from "next/navigation";

/**
 * Reprise de session, côté serveur.
 *
 * Un composant serveur ne peut pas écrire de cookie pendant son rendu, et il
 * ne peut pas non plus faire tourner le jeton : le cookie `refresh` est limité
 * au chemin `/api/v1/auth` par le backend, le navigateur ne l'envoie donc
 * jamais avec une navigation de page. Quand `/me` refuse la session, le rendu
 * serveur ne peut que déléguer à une page cliente, seule à pouvoir appeler
 * `/auth/refresh` (rotation) ou `/auth/logout` (effacement des cookies).
 *
 * Rediriger directement vers `/login` fabriquait une boucle : la garde de
 * navigation (`proxy.ts`) renvoie `/login` vers `/` dès qu'un cookie `access`
 * existe, même périmé, et le rendu de `/` renvoyait vers `/login`.
 */
export const CHEMIN_REPRISE = "/session";

/** En-tête posé par la garde : le chemin demandé, pour y revenir après reprise. */
export const ENTETE_CHEMIN = "x-miara-chemin";

/** Un chemin de retour n'est accepté que s'il est interne (pas d'open redirect). */
export function cheminInterne(valeur: string | null | undefined): string {
  if (!valeur || !valeur.startsWith("/") || valeur.startsWith("//")) return "/";
  if (valeur.startsWith(CHEMIN_REPRISE)) return "/"; // jamais se renvoyer à soi-même
  return valeur;
}

/** Ne rend jamais : redirige vers la page de reprise, qui tranchera. */
export function reprendreSession(vers?: string | null): never {
  redirect(`${CHEMIN_REPRISE}?vers=${encodeURIComponent(cheminInterne(vers))}`);
}
