import { Skeleton } from "@/components/ui/skeleton";
import { SqueletteCartes } from "@/components/ui/skeletons";

/**
 * Attente d'une navigation SERVEUR dans l'application authentifiée.
 *
 * Sans ce fichier, la navigation semblait figée : le navigateur restait sur
 * la page précédente le temps de `getMe()` et de la requête de segment, sans
 * rien dire. Le squelette est volontairement neutre — il couvre sept routes
 * de formes différentes — et tient la place d'un titre et d'un premier bloc.
 */
export default function Loading() {
  return (
    <div className="flex flex-col gap-6">
      <div role="status" aria-busy className="flex flex-col gap-2">
        <span className="sr-only">Chargement de la page…</span>
        <Skeleton className="h-6 w-56" />
        <Skeleton className="h-4 w-80 max-w-full" />
      </div>
      <SqueletteCartes nombre={4} label="Chargement du contenu…" />
    </div>
  );
}
