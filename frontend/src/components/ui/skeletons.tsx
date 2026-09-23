import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/**
 * Squelettes de chargement, à la forme du contenu attendu.
 *
 * Un spinner centré dit « attendez » ; un squelette dit ce qui arrive et, en
 * occupant déjà la place, évite que la page saute sous le curseur quand les
 * données arrivent. Le libellé reste annoncé aux lecteurs d'écran via
 * `role="status"` : l'information n'est pas perdue, elle est doublée.
 */
function Zone({
  label,
  className,
  children,
}: {
  label: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div role="status" aria-busy className={cn("flex flex-col gap-3", className)}>
      <span className="sr-only">{label}</span>
      {children}
    </div>
  );
}

/** N cartes d'indicateur côte à côte (tableau de bord, campagne). */
export function SqueletteCartes({
  nombre = 4,
  label = "Chargement des indicateurs…",
  className,
}: {
  nombre?: number;
  label?: string;
  className?: string;
}) {
  return (
    <Zone label={label} className={className}>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: nombre }, (_, i) => (
          <Card key={i}>
            {/* Trois lignes, comme la carte réelle : titre, chiffre, note. */}
            <CardContent className="flex flex-col gap-1">
              <Skeleton className="my-0.5 h-4 w-28" />
              <Skeleton className="my-1 h-6 w-16" />
              <Skeleton className="my-0.5 h-3 w-36" />
            </CardContent>
          </Card>
        ))}
      </div>
    </Zone>
  );
}

/** Tableau : en-tête + N lignes, aux largeurs de colonnes réelles. */
export function SqueletteTableau({
  lignes = 5,
  colonnes = 4,
  label = "Chargement du tableau…",
  className,
}: {
  lignes?: number;
  colonnes?: number;
  label?: string;
  className?: string;
}) {
  return (
    <Zone label={label} className={className}>
      <div className="flex gap-3 border-b pb-2">
        {Array.from({ length: colonnes }, (_, i) => (
          <Skeleton key={i} className="h-3 flex-1" />
        ))}
      </div>
      {Array.from({ length: lignes }, (_, l) => (
        <div key={l} className="flex gap-3 py-1">
          {Array.from({ length: colonnes }, (_, c) => (
            <Skeleton key={c} className="h-4 flex-1" />
          ))}
        </div>
      ))}
    </Zone>
  );
}

/** Liste de lignes bordées (CV déposés, offres, membres). */
export function SqueletteListe({
  lignes = 4,
  label = "Chargement de la liste…",
  className,
}: {
  lignes?: number;
  label?: string;
  className?: string;
}) {
  return (
    <Zone label={label} className={className}>
      <div className="flex flex-col divide-y rounded-lg border">
        {Array.from({ length: lignes }, (_, i) => (
          <div key={i} className="flex items-center justify-between gap-3 px-4 py-3">
            <div className="flex min-w-0 flex-1 flex-col gap-1.5">
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-3 w-24" />
            </div>
            <Skeleton className="h-6 w-20 shrink-0 rounded-4xl" />
          </div>
        ))}
      </div>
    </Zone>
  );
}

/** Fiches de classement : anneau de score + texte. */
export function SqueletteClassement({
  lignes = 3,
  label = "Chargement du classement…",
  className,
}: {
  lignes?: number;
  label?: string;
  className?: string;
}) {
  return (
    <Zone label={label} className={className}>
      {Array.from({ length: lignes }, (_, i) => (
        <Card key={i}>
          <CardContent className="flex items-center gap-4">
            <Skeleton className="size-14 shrink-0 rounded-full" />
            <div className="flex min-w-0 flex-1 flex-col gap-2">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-3 w-full" />
            </div>
          </CardContent>
        </Card>
      ))}
    </Zone>
  );
}

/** Formulaire : N champs étiquetés. */
export function SqueletteFormulaire({
  champs = 3,
  label = "Chargement du formulaire…",
  className,
}: {
  champs?: number;
  label?: string;
  className?: string;
}) {
  return (
    <Zone label={label} className={className}>
      {Array.from({ length: champs }, (_, i) => (
        <div key={i} className="flex flex-col gap-1.5">
          <Skeleton className="h-3 w-28" />
          <Skeleton className="h-8 w-full" />
        </div>
      ))}
    </Zone>
  );
}

/** Fil de messages : bulles alternées. */
export function SqueletteConversation({
  label = "Chargement de la conversation…",
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <Zone label={label} className={className}>
      {["w-3/4", "w-11/12", "w-3/5"].map((largeur, i) => (
        <div key={i} className={cn("flex", i % 2 === 1 && "justify-end")}>
          <Skeleton className={cn("h-16 rounded-lg", largeur)} />
        </div>
      ))}
    </Zone>
  );
}

/** Liste d'activité : lignes serrées à deux textes (tableau de bord). */
export function SqueletteActivite({
  lignes = 5,
  label = "Chargement de l'activité récente…",
  className,
}: {
  lignes?: number;
  label?: string;
  className?: string;
}) {
  return (
    <Zone label={label} className={className}>
      <div className="flex flex-col divide-y rounded-lg border">
        {Array.from({ length: lignes }, (_, i) => (
          <div key={i} className="flex items-center gap-3 px-4 py-2">
            <Skeleton className="size-4 shrink-0 rounded-sm" />
            <span className="flex min-w-0 flex-1 flex-col gap-1">
              <Skeleton className="my-0.5 h-4 w-2/3" />
              <Skeleton className="my-0.5 h-3 w-1/3" />
            </span>
            <Skeleton className="my-0.5 h-3 w-10 shrink-0" />
          </div>
        ))}
      </div>
    </Zone>
  );
}

/**
 * Tableau de bord entier : indicateurs ET activité récente.
 *
 * Esquisser les seules cartes ne suffisait pas — la liste d'activité arrivait
 * ensuite et poussait les raccourcis de plusieurs centaines de pixels. Un
 * squelette qui n'occupe pas toute la place du contenu ne corrige pas le
 * décalage, il le déplace.
 */
export function SqueletteTableauDeBord({ className }: { className?: string }) {
  return (
    <div className={cn("flex flex-col gap-6", className)}>
      <SqueletteCartes nombre={4} />
      <div className="flex flex-col gap-2">
        <Skeleton className="my-1 h-4 w-36" />
        <SqueletteActivite lignes={5} />
      </div>
    </div>
  );
}

/** Graphique : le cadre de la carte et l'aire du tracé. */
export function SqueletteGraphique({
  hauteur = "h-72",
  label = "Chargement du graphique…",
  className,
}: {
  hauteur?: string;
  label?: string;
  className?: string;
}) {
  return (
    <Zone label={label} className={className}>
      <Card>
        <CardContent className="flex flex-col gap-3">
          <Skeleton className="my-0.5 h-4 w-32" />
          <Skeleton className={cn("w-full", hauteur)} />
        </CardContent>
      </Card>
    </Zone>
  );
}
