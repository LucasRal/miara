"use client";

import { useSyncExternalStore } from "react";

/**
 * Largeur `lg` de Tailwind (64rem = 1024 px), en une seule copie.
 *
 * Le seuil est dupliqué en JavaScript parce qu'une mise en forme CSS ne suffit
 * pas ici : la colonne des conversations n'est pas *cachée* sous `lg`, elle
 * devient un tiroir — deux arbres différents, dont un seul doit exister à la
 * fois (des `id` en double sinon).
 */
export const GRAND_ECRAN = "(min-width: 64rem)";

/**
 * Abonnement à une requête média, lisible pendant le rendu.
 *
 * Le rendu serveur répond « non » : la forme mobile est la plus contrainte,
 * c'est donc elle qu'on sert avant de savoir, et l'hydratation corrige.
 */
export function useMediaQuery(requete: string): boolean {
  return useSyncExternalStore(
    (rappel) => {
      const media = window.matchMedia(requete);
      media.addEventListener("change", rappel);
      return () => media.removeEventListener("change", rappel);
    },
    () => window.matchMedia(requete).matches,
    () => false
  );
}
