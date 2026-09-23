"use client";

import { ArrowRight, Clock } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ActivityList } from "@/components/dashboard/activity-list";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { SqueletteTableauDeBord } from "@/components/ui/skeletons";
import { ErrorState } from "@/components/ui/states";
import { api } from "@/lib/api";
import { duree, heure, type DashboardSummary } from "@/lib/dashboard";

/**
 * Les quatre indicateurs du mois et l'activité récente.
 *
 * Les heures économisées sont une HYPOTHÈSE (temps de tri manuel de
 * référence), pas une mesure : l'écran affiche la formule sous le chiffre.
 * Un indicateur de valeur dont on cache le calcul ne vaut rien dans une
 * soutenance.
 */
export function DashboardMetrics() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(async () => {
    setErreur(null);
    try {
      setData(await api.get<DashboardSummary>("/dashboard/summary"));
    } catch {
      setErreur("Impossible de charger les indicateurs.");
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void charger();
  }, [charger]);

  if (erreur) return <ErrorState message={erreur} onRetry={() => void charger()} />;
  if (data === null) return <SqueletteTableauDeBord />;

  const m = data.metrics;
  const cartes = [
    {
      cle: "cv",
      titre: "CV analysés ce mois",
      valeur: String(m.cv_analyses),
      note: `${data.cv_total} CV déposés au total`,
    },
    {
      cle: "heures",
      titre: "Heures RH estimées économisées",
      valeur: m.heures_economisees.toLocaleString("fr-FR"),
      note: `${m.cv_analyses} CV × ${m.minutes_par_cv} min de tri manuel (hypothèse)`,
    },
    {
      cle: "crm",
      titre: "Actions CRM confirmées",
      valeur: String(m.ecritures_crm),
      note: "Chacune validée par un humain",
    },
    {
      cle: "latence",
      titre: "Latence moyenne des réponses",
      valeur: m.latence_moyenne_ms === null ? "–" : duree(m.latence_moyenne_ms),
      note: "Agent commercial et coach",
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cartes.map((c) => (
          <Card key={c.cle}>
            <CardContent className="flex flex-col gap-1">
              <p className="text-sm text-muted-foreground">{c.titre}</p>
              <p className="font-heading text-2xl font-semibold tabular-nums">{c.valeur}</p>
              <p className="text-xs text-muted-foreground">{c.note}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h2 className="font-heading text-base font-medium">Activité récente</h2>
          {/* « Cache » était un mot d'ingénieur. Ce qui intéresse l'utilisateur
              est la fraîcheur du chiffre, pas le mécanisme qui la produit. */}
          <span className="text-xs text-muted-foreground">
            Mis à jour à {heure(data.generated_at)}
          </span>
        </div>
        {data.activity.length === 0 ? (
          <EmptyState
            icon={<Clock aria-hidden />}
            title="Aucune activité pour l'instant"
            description="Lancez une analyse de CV ou un briefing commercial : les dix derniers événements de l'organisation apparaîtront ici."
          />
        ) : (
          <>
            <ActivityList events={data.activity} instanceUrl={data.crm_instance_url} />
            {/* L'aperçu s'arrête à dix. Sans ce lien, tout ce qui est plus
                ancien n'existait nulle part dans l'interface. */}
            <Button asChild variant="ghost" size="sm" className="self-start">
              <Link href="/activity">
                Voir toute l&apos;activité <ArrowRight aria-hidden />
              </Link>
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
