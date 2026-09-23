import type { Role } from "@/lib/api";

/**
 * Source unique de la navigation ET des droits par segment.
 *
 * Le même tableau sert à (1) afficher les onglets, (2) garder les segments
 * côté serveur. Ajouter une section = une ligne ici, pas deux listes à tenir
 * synchronisées — c'est ce qui garantit qu'un onglet masqué est aussi un
 * segment interdit (critère 2 de la carte).
 */
export interface Section {
  href: string;
  label: string;
  /** null = tout membre de l'organisation. */
  roles: readonly Role[] | null;
}

const METIER = {
  hr: ["owner", "admin", "hr"],
  sales: ["owner", "admin", "sales"],
  // Information budgétaire : l'encadrement, pas l'équipe. Même règle que la
  // garde de rôle du router /usage côté backend (app/usage.py).
  encadrement: ["owner", "admin"],
} as const;

export const SECTIONS: readonly Section[] = [
  { href: "/", label: "Tableau de bord", roles: null },
  { href: "/hr", label: "Agent RH", roles: METIER.hr },
  { href: "/sales", label: "Agent commercial", roles: METIER.sales },
  { href: "/sales/coach", label: "Coach", roles: METIER.sales },
  // Journal métier (ce que les agents ont produit), à ne pas confondre avec
  // la file de traitement, qui est technique.
  { href: "/activity", label: "Activité", roles: null },
  { href: "/queue", label: "File de traitement", roles: null },
  { href: "/usage", label: "Usage", roles: METIER.encadrement },
  { href: "/settings", label: "Paramètres", roles: null },
];

/** Section correspondant au chemin, la plus spécifique d'abord (/sales/coach avant /sales). */
export function sectionFor(pathname: string): Section | undefined {
  return [...SECTIONS]
    .sort((a, b) => b.href.length - a.href.length)
    .find((s) => (s.href === "/" ? pathname === "/" : pathname.startsWith(s.href)));
}

export function canAccess(section: Section | undefined, role: Role | null): boolean {
  if (!section || role === null) return false;
  return section.roles === null || section.roles.includes(role);
}

export function visibleSections(role: Role | null): Section[] {
  return SECTIONS.filter((s) => canAccess(s, role));
}
