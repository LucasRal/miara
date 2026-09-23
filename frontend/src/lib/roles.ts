import type { Role } from "@/lib/api";

/**
 * Rôles : valeurs techniques d'un côté, mots français de l'autre.
 *
 * `owner`, `admin`, `sales`, `hr` sont ce que le backend attend et ce que
 * l'interface lui renvoie — jamais ce qu'elle affiche. Un recruteur ne se
 * reconnaît pas dans « hr ».
 */
export const ROLES: readonly Role[] = ["owner", "admin", "sales", "hr"] as const;

export const ROLE_LIBELLE: Record<Role, string> = {
  owner: "Propriétaire",
  admin: "Administrateur",
  sales: "Commercial",
  hr: "Ressources humaines",
};

/** Ce que le rôle donne le droit de faire, dans les mots de l'application. */
export const ROLE_AIDE: Record<Role, string> = {
  owner: "Propriétaire : tout, y compris la facturation",
  admin: "Administrateur : membres, intégrations, usage",
  sales: "Commercial : agent commercial et coach",
  hr: "Ressources humaines : offres et présélection de CV",
};

export function libelleRole(role: Role | null): string {
  return role === null ? "Sans rôle" : ROLE_LIBELLE[role];
}
