import type { Role } from "@/lib/api";

/**
 * Source unique de la navigation ET des droits par segment.
 *
 * Le même tableau sert à (1) afficher les onglets, (2) garder les segments
 * côté serveur. Ajouter une section = une ligne ici, pas deux listes à tenir
 * synchronisées — c'est ce qui garantit qu'un onglet masqué est aussi un
 * segment interdit (critère 2 de la carte).
 */
export type Espace = "rh" | "commercial";

/**
 * Cookie où vit l'espace actif. Préférence d'interface, pas un secret : le
 * serveur le lit pour rendre les bons onglets dès le premier octet.
 *
 * Il vit ICI et non dans `lib/espace.tsx` : ce module-là porte la directive
 * « use client », et un composant serveur qui importe une valeur d'un module
 * client n'en reçoit qu'une référence — `cookies().get(undefined)`, donc des
 * onglets qui ignorent le choix de l'utilisateur.
 */
export const COOKIE_ESPACE = "miara_espace";

export interface Section {
  href: string;
  label: string;
  /** null = tout membre de l'organisation. */
  roles: readonly Role[] | null;
  /**
   * Espace de travail auquel la section appartient. Absent = transverse :
   * la section reste visible quel que soit l'espace actif.
   */
  espace?: Espace;
  /**
   * Libellé dans la barre d'onglets quand l'espace est actif. Le nom de
   * l'espace est déjà dans l'en-tête : répéter « Agent RH » sous « Espace
   * RH » ne dit rien de plus que « Présélection ».
   */
  labelCourt?: string;
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
  { href: "/hr", label: "Agent RH", roles: METIER.hr, espace: "rh", labelCourt: "Présélection" },
  {
    href: "/sales",
    label: "Agent commercial",
    roles: METIER.sales,
    espace: "commercial",
    labelCourt: "Assistant",
  },
  { href: "/sales/coach", label: "Coach", roles: METIER.sales, espace: "commercial" },
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

/**
 * Les deux espaces de travail, dans l'ordre de la barre d'onglets.
 *
 * Un espace n'est PAS un droit : c'est un cadrage de l'interface. Ce qui
 * autorise ou refuse reste `roles`, lu côté serveur — le sélecteur d'espace
 * ne fait que choisir ce qu'on regarde parmi ce à quoi on a déjà droit.
 */
export const ESPACES: readonly { id: Espace; nom: string; accueil: string }[] = [
  { id: "rh", nom: "RH", accueil: "/hr" },
  { id: "commercial", nom: "commercial", accueil: "/sales" },
];

/** « Espace RH », pour un contrôle ou un titre. */
export function libelleEspace(espace: Espace | null): string {
  const nom = ESPACES.find((e) => e.id === espace)?.nom;
  return nom ? `Espace ${nom}` : "Tous les espaces";
}

/** « RH », pour une phrase : « ouvertes à votre rôle dans l'espace RH ». */
export function nomEspace(espace: Espace | null): string {
  return ESPACES.find((e) => e.id === espace)?.nom ?? "";
}

/** Espaces ouverts à ce rôle : un commercial n'en a qu'un, un admin les deux. */
export function espacesFor(role: Role | null): Espace[] {
  return ESPACES.filter((e) => SECTIONS.some((s) => s.espace === e.id && canAccess(s, role))).map(
    (e) => e.id
  );
}

/** Espace auquel appartient un chemin, s'il en a un. */
export function espaceFor(pathname: string): Espace | undefined {
  return sectionFor(pathname)?.espace;
}

/**
 * Espace réellement actif : l'URL d'abord (être sur /sales, c'est être dans
 * l'espace commercial, quel qu'ait été le dernier choix), puis le choix
 * mémorisé, puis le premier espace ouvert au rôle.
 */
export function espaceActif(
  pathname: string,
  choisi: Espace | null,
  role: Role | null
): Espace | null {
  const ouverts = espacesFor(role);
  const chemin = espaceFor(pathname);
  if (chemin && ouverts.includes(chemin)) return chemin;
  if (choisi && ouverts.includes(choisi)) return choisi;
  return ouverts[0] ?? null;
}

/**
 * Sections visibles : celles ouvertes au rôle, moins celles qui appartiennent
 * à l'autre espace. Les sections transverses restent toujours là.
 */
export function visibleSections(role: Role | null, espace?: Espace | null): Section[] {
  return SECTIONS.filter(
    (s) => canAccess(s, role) && (!s.espace || !espace || s.espace === espace)
  );
}
