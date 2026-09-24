import { cookies, headers } from "next/headers";

import { CreateOrgCard } from "@/components/auth/create-org-card";
import { AppHeader } from "@/components/layout/app-header";
import { SkipLink } from "@/components/ui/skip-link";
import { EspaceProvider } from "@/lib/espace";
import { COOKIE_ESPACE, type Espace } from "@/lib/navigation";
import { getMe } from "@/lib/server-api";
import { ENTETE_CHEMIN, reprendreSession } from "@/lib/session";

/**
 * Coquille de l'application authentifiée.
 *
 * Deux états : sans organisation (accueil de création, sans onglets — on ne
 * propose pas une navigation qui ne mènerait nulle part), sinon l'en-tête
 * complet. La session est lue côté serveur : aucun jeton ne transite par le
 * JavaScript client.
 *
 * L'espace de travail actif est lu ici, dans le cookie, pour que le premier
 * rendu soit déjà le bon : cadrer les onglets côté client seulement les ferait
 * passer d'un métier à l'autre sous les yeux de l'utilisateur.
 */
export default async function AppLayout({ children }: LayoutProps<"/">) {
  const me = await getMe();
  // Session refusée : passer par la reprise, jamais directement par /login —
  // la garde y renverrait vers l'accueil tant que le cookie `access` existe.
  if (!me) reprendreSession((await headers()).get(ENTETE_CHEMIN));

  if (!me.org_id) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-6 bg-muted/40 p-4">
        <p className="text-muted-foreground">Bienvenue {me.full_name}</p>
        <CreateOrgCard />
      </div>
    );
  }

  const choisi = (await cookies()).get(COOKIE_ESPACE)?.value;

  return (
    <EspaceProvider role={me.role} initial={(choisi as Espace | undefined) ?? null}>
      <div className="flex flex-1 flex-col">
        {/* Premier arrêt de tabulation de toute page connectée (WCAG 2.4.1) :
          sans lui, il fallait huit Tab — menu compte puis sept onglets —
          avant d'atteindre le contenu. Invisible tant qu'il n'a pas le focus,
          et `fixed` une fois visible pour ne décaler aucune mise en page. */}
        <SkipLink href="#contenu">Aller au contenu</SkipLink>
        <AppHeader me={me} />
        {/* `tabIndex={-1}` : la cible d'un lien d'évitement doit pouvoir
          recevoir le focus, sinon le Tab suivant repart du haut. */}
        <main id="contenu" tabIndex={-1} className="flex flex-1 flex-col p-4 sm:p-6">
          {children}
        </main>
      </div>
    </EspaceProvider>
  );
}
