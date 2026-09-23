import Link from "next/link";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

/**
 * Rendu propre d'un accès refusé (URL tapée à la main vers un segment
 * interdit). La décision est prise côté serveur, à partir du rôle relu par le
 * backend : masquer l'onglet ne suffirait pas.
 */
export function Forbidden({ section, role }: { section: string; role: string | null }) {
  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <EmptyState
        title="Accès refusé"
        description={`La section « ${section} » n'est pas ouverte au rôle ${role ?? "sans rôle"}. Demandez un accès à un administrateur de votre organisation.`}
        action={
          <Button asChild size="sm">
            <Link href="/">Revenir au tableau de bord</Link>
          </Button>
        }
      />
    </div>
  );
}
