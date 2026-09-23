import { FileQuestion } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

/**
 * Écran « page introuvable », partagé par les deux frontières 404.
 *
 * Next résout une URL qui ne correspond à aucun segment tout en haut de
 * l'arbre : c'est `app/not-found.tsx` qui répond, pas celui d'un groupe. Les
 * deux fichiers rendent donc le même écran ; seule la coquille change.
 *
 * Le titre est un `h1` : cet état vide EST la page, et une page sans `h1`
 * laisse un lecteur d'écran sans repère (axe `page-has-heading-one`).
 */
export function Introuvable({ dansApplication = false }: { dansApplication?: boolean }) {
  return (
    <EmptyState
      icon={<FileQuestion aria-hidden />}
      title="Cette page n'existe pas"
      titreBalise="h1"
      description={
        dansApplication
          ? "L'adresse demandée ne correspond à aucune page de Miara. Les sections ouvertes à votre rôle sont dans les onglets ci-dessus."
          : "L'adresse demandée ne correspond à aucune page de Miara. Une faute de frappe, ou un lien qui a vieilli."
      }
      action={
        <Button asChild size="sm">
          <Link href="/">Revenir au tableau de bord</Link>
        </Button>
      }
    />
  );
}
