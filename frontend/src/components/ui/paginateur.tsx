"use client";

import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";

/**
 * Fenêtre de numéros autour de la page courante.
 *
 * Toujours la première et la dernière (ce sont les deux sauts qu'on fait
 * vraiment), la courante et ses voisines, des ellipses pour le reste. À 25
 * pages, aligner 25 boutons ne serait pas une navigation mais une liste de
 * plus à lire.
 */
export function fenetre(page: number, pages: number): (number | "…")[] {
  if (pages <= 7) return Array.from({ length: pages }, (_, i) => i);
  const numeros = new Set([0, pages - 1, page - 1, page, page + 1]);
  const gardes = [...numeros].filter((n) => n >= 0 && n < pages).sort((a, b) => a - b);
  const sortie: (number | "…")[] = [];
  for (const [i, n] of gardes.entries()) {
    if (i > 0 && n - (gardes[i - 1] as number) > 1) sortie.push("…");
    sortie.push(n);
  }
  return sortie;
}

/**
 * Pagination d'une liste, en pages de `taille` éléments.
 *
 * Les listes de l'application sont vouées à grandir — 500 CV par lot est la
 * cible du produit — et rendre le tableau reçu en entier était tenable à 5
 * lignes, pas à 500. Une pagination plutôt qu'une virtualisation : ce qui est
 * à l'écran reste lisible, imprimable et exportable.
 *
 * `page` est un index à partir de 0 ; l'affichage compte à partir de 1.
 */
export function Paginateur({
  page,
  taille,
  total,
  onPage,
  nom,
}: {
  page: number;
  taille: number;
  total: number;
  onPage: (page: number) => void;
  /** Ce qui est paginé, au pluriel : « CV », « offres », « conversations ». */
  nom: string;
}) {
  const pages = Math.ceil(total / taille);
  // Une seule page n'est pas une pagination : deux flèches grisées sous une
  // liste courte n'apprennent rien à personne.
  if (pages <= 1) return null;

  const premier = page * taille + 1;
  const dernier = Math.min((page + 1) * taille, total);

  return (
    // Collante : une liste de vingt éléments repoussait sa pagination hors de
    // l'écran, et changer de page demandait d'abord de tout faire défiler.
    // Elle reste au bas de la fenêtre tant que la liste est en vue.
    <div className="sticky bottom-0 z-10 flex flex-wrap items-center justify-between gap-2 border-t bg-background py-2">
      <p className="text-sm text-muted-foreground" role="status">
        {nom} {premier} à {dernier} sur {total}
      </p>
      <Pagination className="mx-0 w-auto justify-end">
        <PaginationContent>
          <PaginationItem>
            <PaginationPrevious
              onClick={() => onPage(page - 1)}
              aria-disabled={page === 0}
              disabled={page === 0}
            />
          </PaginationItem>
          {fenetre(page, pages).map((n, i) =>
            n === "…" ? (
              <PaginationItem key={`saut-${i}`}>
                <PaginationEllipsis />
              </PaginationItem>
            ) : (
              <PaginationItem key={n}>
                <PaginationLink
                  isActive={n === page}
                  onClick={() => onPage(n)}
                  aria-label={`Page ${n + 1} sur ${pages}`}
                >
                  {n + 1}
                </PaginationLink>
              </PaginationItem>
            )
          )}
          <PaginationItem>
            <PaginationNext
              onClick={() => onPage(page + 1)}
              aria-disabled={page >= pages - 1}
              disabled={page >= pages - 1}
            />
          </PaginationItem>
        </PaginationContent>
      </Pagination>
    </div>
  );
}
