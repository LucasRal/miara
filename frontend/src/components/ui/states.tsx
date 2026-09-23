import { AlertCircle, SearchX } from "lucide-react";
import Link from "next/link";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { cn } from "@/lib/utils";

/**
 * Erreur de chargement : message lisible + relance, jamais une trace brute.
 *
 * Construit sur `Alert` (donc `role="alert"` : l'erreur est annoncée dès son
 * apparition). Le chargement, lui, n'a plus d'état commun : chaque écran
 * affiche un squelette à la forme de son contenu (`components/ui/skeletons`).
 */
export function ErrorState({
  message,
  onRetry,
  retryLabel = "Réessayer",
  titre = "Chargement impossible",
  className,
}: {
  message: string;
  onRetry?: () => void;
  /** Ce que fait le bouton : relancer l'appel, ou simplement masquer. */
  retryLabel?: string;
  titre?: string;
  className?: string;
}) {
  return (
    <Alert variant="destructive" className={cn("items-start", className)}>
      <AlertCircle aria-hidden />
      <AlertTitle>{titre}</AlertTitle>
      <AlertDescription>
        {message}
        {onRetry && (
          <Button variant="outline" size="sm" className="mt-2 w-fit" onClick={onRetry}>
            {retryLabel}
          </Button>
        )}
      </AlertDescription>
    </Alert>
  );
}

/**
 * Ressource absente : un titre, une explication, et la sortie.
 *
 * Distinct de `ErrorState` par ce qu'il NE propose pas : « Réessayer » sur une
 * 404 promet une issue qui n'arrivera jamais. Un identifiant périmé vient
 * d'un favori ou d'un lien du tableau de bord après suppression — la seule
 * action utile est de remonter à la liste parente.
 */
export function NotFoundState({
  titre,
  description,
  retour,
  className,
}: {
  titre: string;
  description: string;
  /** Liste parente : là où l'utilisateur voulait aller, en fait. */
  retour: { href: string; label: string };
  className?: string;
}) {
  return (
    <EmptyState
      icon={<SearchX aria-hidden />}
      title={titre}
      titreBalise="h1"
      description={description}
      className={className}
      action={
        <Button asChild size="sm" variant="outline">
          <Link href={retour.href}>{retour.label}</Link>
        </Button>
      }
    />
  );
}
