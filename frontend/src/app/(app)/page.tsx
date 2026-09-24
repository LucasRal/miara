import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

import { DashboardMetrics } from "@/components/dashboard/metrics";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  canAccess,
  COOKIE_ESPACE,
  espaceActif,
  espaceFor,
  sectionFor,
  type Espace,
} from "@/lib/navigation";
import { getMe } from "@/lib/server-api";
import { reprendreSession } from "@/lib/session";

export const metadata = { title: "Tableau de bord · Miara" };

/**
 * Tableau de bord : ce que les agents ont produit pour l'organisation.
 *
 * L'en-tête et les raccourcis sont rendus côté serveur (le rôle décide de ce
 * qui est proposé) ; les indicateurs sont chargés côté client, parce qu'ils
 * viennent d'un agrégat mis en cache que l'on veut pouvoir rafraîchir sans
 * recharger la page.
 */
export default async function DashboardPage() {
  const me = await getMe();
  if (!me) reprendreSession("/");
  // Session valide sans organisation : la coquille propose d'en créer une.
  if (!me.org_id) redirect("/");

  const choisi = (await cookies()).get(COOKIE_ESPACE)?.value as Espace | undefined;
  const espace = espaceActif("/", choisi ?? null, me.role);

  const raccourcis = [
    {
      href: "/hr",
      titre: "Analyser des candidatures",
      texte: "Créez une offre, validez la grille, déposez les CV.",
    },
    {
      href: "/sales",
      titre: "Préparer un appel",
      texte: "Demandez un briefing sourcé sur un compte Salesforce.",
    },
    // Deux raccourcis pour deux métiers : l'espace actif décide lequel est
    // proposé, le rôle décide s'il existe.
  ].filter(
    (r) => canAccess(sectionFor(r.href), me.role) && (!espace || espaceFor(r.href) === espace)
  );

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-heading text-xl font-semibold">Bonjour {me.full_name}</h1>
        <p className="text-sm text-muted-foreground">
          {espace === "rh"
            ? "Votre agent RH, sur les données de votre organisation."
            : espace === "commercial"
              ? "Votre agent commercial, sur les données de votre organisation."
              : "Vos agents commerciaux et RH, sur les données de votre organisation."}
        </p>
      </div>

      {/* Les raccourcis d'abord : la page d'accueil répond à « que puis-je
          faire ? » avant « que s'est-il passé ? ». Sous les indicateurs et
          les dix lignes d'activité, ils arrivaient après 3 000 px de
          défilement sur téléphone. */}
      <div className="grid gap-4 sm:grid-cols-2">
        {raccourcis.map((r) => (
          <Card key={r.href}>
            <CardHeader>
              <CardTitle>{r.titre}</CardTitle>
              <CardDescription>{r.texte}</CardDescription>
              <Button asChild size="sm" className="mt-3 w-fit">
                <Link href={r.href}>
                  Ouvrir<span className="sr-only"> : {r.titre.toLowerCase()}</span>
                </Link>
              </Button>
            </CardHeader>
          </Card>
        ))}
      </div>

      <DashboardMetrics />
    </div>
  );
}
