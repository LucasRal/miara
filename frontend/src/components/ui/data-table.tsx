"use client";

import {
  createPaginatedRowModel,
  createSortedRowModel,
  rowPaginationFeature,
  rowSortingFeature,
  sortFn_alphanumeric,
  sortFn_basic,
  sortFn_datetime,
  sortFn_text,
  useTable,
  type ColumnDef,
  type RowData,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

/**
 * Tableau commun de l'application : tri, pagination, en-tête collant, et rendu
 * en cartes sous `sm` (un tableau à défilement horizontal sur téléphone n'est
 * pas lisible).
 *
 * Deux modes de pagination :
 *  - client (par défaut) : la page entière est déjà en mémoire (membres, alias)
 *  - serveur (`paginationServeur`) : le serveur borne (file de traitement,
 *    appels LLM) — ces listes grandissent sans limite, les paginer côté client
 *    reviendrait à tout télécharger d'abord.
 *
 * Toujours fournir `caption` : c'est le nom du tableau pour un lecteur d'écran.
 */
/**
 * Les deux seules fonctionnalités TanStack activées : tri et pagination.
 * Déclarées ici une fois, pour que les appelants n'aient à manipuler ni le jeu
 * de fonctionnalités ni ses génériques (`Colonne<T>` suffit).
 */
const FONCTIONS = {
  rowSortingFeature,
  rowPaginationFeature,
  sortedRowModel: createSortedRowModel(),
  paginatedRowModel: createPaginatedRowModel(),
  // Fonctions de tri enregistrées ici : seules celles-ci entrent dans le
  // paquet, et seuls leurs noms sont acceptés par `sortFn` sur une colonne.
  sortFns: {
    alphanumeric: sortFn_alphanumeric,
    basic: sortFn_basic,
    datetime: sortFn_datetime,
    text: sortFn_text,
  },
};

export type Colonne<T extends RowData> = ColumnDef<typeof FONCTIONS, T, unknown>;

export type PaginationServeur = {
  page: number;
  taillePage: number;
  total: number | null;
  onPage: (page: number) => void;
};

/**
 * Rend un gabarit de colonne — texte fixe ou fonction — SANS `flexRender`.
 *
 * `flexRender` fait `createElement(fn, contexte)` : la fonction `cell` devient
 * le TYPE du composant. Or ces fonctions sont réécrites à chaque rendu de
 * l'appelant (elles vivent dans un littéral de colonnes), donc React voyait à
 * chaque fois un type différent et démontait puis remontait chaque cellule.
 * Conséquences mesurées : un bouton mémorisé pour rendre le focus après un
 * dialogue était déjà détaché du document à la fermeture, et tout le tableau
 * se reconstruisait à chaque frappe dans un champ voisin.
 *
 * L'appel direct rend le même arbre, réconcilié sur les éléments réellement
 * retournés. Contrainte assumée : un gabarit de colonne ne peut pas appeler de
 * hook — ce n'est pas un composant.
 */
function rendu<T>(gabarit: unknown, contexte: T): ReactNode {
  if (typeof gabarit === "function") return (gabarit as (c: T) => ReactNode)(contexte);
  return gabarit as ReactNode;
}

export function DataTable<T extends RowData>({
  colonnes,
  donnees,
  caption,
  captionVisible = false,
  taillePage = 25,
  paginationServeur,
  triInitial,
  carte,
  vide,
  cleLigne,
  className,
}: {
  colonnes: Colonne<T>[];
  donnees: T[];
  caption: string;
  captionVisible?: boolean;
  taillePage?: number;
  paginationServeur?: PaginationServeur;
  triInitial?: SortingState;
  /** Rendu d'une ligne sous `sm`. Sans lui, le tableau défile horizontalement. */
  carte?: (ligne: T) => ReactNode;
  vide?: ReactNode;
  cleLigne?: (ligne: T) => string;
  className?: string;
}) {
  const [tri, setTri] = useState<SortingState>(triInitial ?? []);

  const table = useTable({
    features: FONCTIONS,
    data: donnees,
    columns: colonnes,
    state: { sorting: tri },
    onSortingChange: setTri,
    manualPagination: paginationServeur !== undefined,
    initialState: { pagination: { pageIndex: 0, pageSize: taillePage } },
  });

  const lignes = table.getRowModel().rows;
  if (lignes.length === 0 && vide) return <>{vide}</>;

  const pageCourante = paginationServeur
    ? paginationServeur.page
    : (table.state.pagination?.pageIndex ?? 0);
  const nbPages = paginationServeur
    ? paginationServeur.total === null
      ? pageCourante + (donnees.length === paginationServeur.taillePage ? 2 : 1)
      : Math.max(1, Math.ceil(paginationServeur.total / paginationServeur.taillePage))
    : table.getPageCount();
  const allerA = (page: number) =>
    paginationServeur ? paginationServeur.onPage(page) : table.setPageIndex(page);

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {/* Cartes sous sm : une ligne = un bloc, aucune colonne hors écran. */}
      {carte && (
        <ul className="flex flex-col gap-2 sm:hidden">
          {lignes.map((ligne) => (
            <li key={ligne.id}>{carte(ligne.original)}</li>
          ))}
        </ul>
      )}

      {/* `borne` : le tableau défile dans son cadre à partir de `sm`, au lieu
          d'étirer la page sur mille pixels et d'emporter sa pagination avec
          lui. Sous `sm`, ce sont les cartes qui s'affichent. */}
      <Table borne sommet={pageCourante} label={caption} className={cn(carte && "hidden sm:table")}>
        <TableCaption className={cn(!captionVisible && "sr-only")}>{caption}</TableCaption>
        <TableHeader>
          {table.getHeaderGroups().map((groupe) => (
            <TableRow key={groupe.id}>
              {groupe.headers.map((entete) => {
                const triable = entete.column.getCanSort();
                const sens = entete.column.getIsSorted();
                const contenu = rendu(entete.column.columnDef.header, entete.getContext());
                return (
                  <TableHead
                    key={entete.id}
                    aria-sort={
                      !triable || !sens ? undefined : sens === "asc" ? "ascending" : "descending"
                    }
                  >
                    {triable ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="-mx-2 h-7 font-medium"
                        onClick={entete.column.getToggleSortingHandler()}
                      >
                        {contenu}
                        {sens === "asc" ? (
                          <ArrowUp aria-hidden />
                        ) : sens === "desc" ? (
                          <ArrowDown aria-hidden />
                        ) : (
                          <ChevronsUpDown className="opacity-50" aria-hidden />
                        )}
                        <span className="sr-only">
                          {sens === "asc"
                            ? ", trié par ordre croissant"
                            : sens === "desc"
                              ? ", trié par ordre décroissant"
                              : ", trier"}
                        </span>
                      </Button>
                    ) : (
                      contenu
                    )}
                  </TableHead>
                );
              })}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {lignes.map((ligne) => (
            <TableRow key={cleLigne ? cleLigne(ligne.original) : ligne.id}>
              {ligne.getAllCells().map((cellule) => (
                <TableCell key={cellule.id}>
                  {rendu(cellule.column.columnDef.cell, cellule.getContext())}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {nbPages > 1 && (
        // Collante : sur la liste en cartes d'un téléphone, la pagination
        // était à vingt-cinq blocs du premier écran. Elle reste au bas de la
        // fenêtre tant que la liste est en vue, et redevient une barre
        // ordinaire dès que tout tient à l'écran.
        <div className="sticky bottom-0 z-10 flex flex-wrap items-center justify-between gap-2 border-t bg-background py-2 sm:static sm:border-0 sm:py-0">
          <p className="text-xs text-muted-foreground">
            {paginationServeur?.total != null
              ? `${paginationServeur.total} au total · page ${pageCourante + 1} sur ${nbPages}`
              : `Page ${pageCourante + 1} sur ${nbPages}`}
          </p>
          <Pagination className="mx-0 w-auto justify-end">
            <PaginationContent>
              <PaginationItem>
                <PaginationPrevious
                  href="#"
                  aria-label="Page précédente"
                  aria-disabled={pageCourante === 0}
                  className={cn(pageCourante === 0 && "pointer-events-none opacity-50")}
                  onClick={(e) => {
                    e.preventDefault();
                    if (pageCourante > 0) allerA(pageCourante - 1);
                  }}
                />
              </PaginationItem>
              {pagesVisibles(pageCourante, nbPages).map((page) => (
                <PaginationItem key={page}>
                  <PaginationLink
                    href="#"
                    isActive={page === pageCourante}
                    aria-label={`Page ${page + 1}`}
                    onClick={(e) => {
                      e.preventDefault();
                      allerA(page);
                    }}
                  >
                    {page + 1}
                  </PaginationLink>
                </PaginationItem>
              ))}
              <PaginationItem>
                <PaginationNext
                  href="#"
                  aria-label="Page suivante"
                  aria-disabled={pageCourante >= nbPages - 1}
                  className={cn(pageCourante >= nbPages - 1 && "pointer-events-none opacity-50")}
                  onClick={(e) => {
                    e.preventDefault();
                    if (pageCourante < nbPages - 1) allerA(pageCourante + 1);
                  }}
                />
              </PaginationItem>
            </PaginationContent>
          </Pagination>
        </div>
      )}
    </div>
  );
}

/** Au plus cinq numéros autour de la page courante : au-delà, c'est du bruit. */
function pagesVisibles(courante: number, total: number): number[] {
  const debut = Math.max(0, Math.min(courante - 2, total - 5));
  return Array.from({ length: Math.min(5, total) }, (_, i) => debut + i).filter((p) => p < total);
}
