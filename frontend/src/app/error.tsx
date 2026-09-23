"use client";

import { AlertTriangle } from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

/**
 * Exception de rendu, côté client comme côté serveur.
 *
 * Sans ce fichier, Next affiche son écran générique — page blanche en
 * production. L'utilisateur reçoit ici une phrase en français et deux issues ;
 * le détail technique part dans la console, jamais à l'écran (« NE PAS » de
 * la carte : ni pile d'erreur, ni message d'exception).
 *
 * `error.tsx` remplace le contenu à partir du layout racine : impossible d'y
 * déclarer `metadata` (c'est un composant client), d'où le `<title>` posé à
 * la main.
 */
export default function ErreurGlobale({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Le `digest` est l'identifiant que Next journalise côté serveur : c'est
    // lui qui permet de retrouver la trace, sans l'exposer à l'écran.
    console.error("erreur de rendu", error.digest ?? error.message);
  }, [error]);

  return (
    <main className="flex flex-1 items-center justify-center p-6">
      <title>Une erreur est survenue · Miara</title>
      <EmptyState
        icon={<AlertTriangle aria-hidden />}
        title="Une erreur inattendue est survenue"
        titreBalise="h1"
        description="La page n'a pas pu s'afficher. Réessayer suffit le plus souvent ; si le problème persiste, signalez-le à un administrateur de votre organisation."
        action={
          <div className="flex flex-wrap justify-center gap-2">
            <Button size="sm" onClick={reset}>
              Réessayer
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/">Revenir au tableau de bord</Link>
            </Button>
          </div>
        }
      />
    </main>
  );
}
