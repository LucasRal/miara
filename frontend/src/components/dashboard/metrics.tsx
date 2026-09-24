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
import { duree, heure, type ActivityPage, type DashboardSummary } from "@/lib/dashboard";
import { useEspace } from "@/lib/espace";
import { type Espace } from "@/lib/navigation";

/**
 * Les quatre indicateurs du mois et l'activité récente.
 *
 * Les heures économisées sont une HYPOTHÈSE (temps de tri manuel de
 * référence), pas une mesure : l'écran affiche la formule sous le chiffre.
 * Un indicateur de valeur dont on cache le calcul ne vaut rien dans une
 * soutenance.
 *
 * L'écran est cadré sur l'espace de travail actif : dans l'espace RH, « CV
 * analysés » et les heures économisées ; dans l'espace commercial, les
 * écritures CRM et la latence ressentie. Un tableau de bord qui montre les
 * quatre au même rang ne dit pas dans quel métier on se trouve.
 */
export function DashboardMetrics() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [journal, setJournal] = useState<ActivityPage | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const { espace } = useEspace();

  const charger = useCallback(async () => {
    setErreur(null);
    // L'aperçu d'activité est demandé à part quand un espace est actif :
    // filtrer après coup les dix événements du résumé en laisserait trois.
    const cadre = espace ? `&espace=${espace}` : "";
    try {
      const [resume, recents] = await Promise.all([
        api.get<DashboardSummary>("/dashboard/summary"),
        api.get<ActivityPage>(`/dashboard/activity?limit=10${cadre}`),
      ]);
      setData(resume);
      setJournal(recents);
    } catch {
      setErreur("Impossible de charger les indicateurs.");
    }
  }, [espace]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void charger();
  }, [charger]);

  if (erreur) return <ErrorState message={erreur} onRetry={() => void charger()} />;
  if (data === null || journal === null) return <SqueletteTableauDeBord />;

  const m = data.metrics;
  const cartes: {
    cle: string;
    titre: string;
    valeur: string;
    note: string;
    espace?: Espace;
  }[] = [
    {
      cle: "cv",
      espace: "rh",
      titre: "CV analysés ce mois",
      valeur: String(m.cv_analyses),
      note: `${data.cv_total} CV déposés au total`,
    },
    {
      cle: "heures",
      espace: "rh",
      titre: "Heures RH estimées économisées",
      valeur: m.heures_economisees.toLocaleString("fr-FR"),
      note: `${m.cv_analyses} CV × ${m.minutes_par_cv} min de tri manuel (hypothèse)`,
    },
    {
      cle: "crm",
      espace: "commercial",
      titre: "Actions CRM confirmées",
      valeur: String(m.ecritures_crm),
      note: "Chacune validée par un humain",
    },
    {
      cle: "latence",
      espace: "commercial",
      titre: "Latence moyenne des réponses",
      valeur: m.latence_moyenne_ms === null ? "–" : duree(m.latence_moyenne_ms),
      note: "Agent commercial et coach",
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cartes
          .filter((c) => !espace || !c.espace || c.espace === espace)
          .map((c) => (
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
        {journal.events.length === 0 ? (
          <EmptyState
            icon={<Clock aria-hidden />}
            title="Aucune activité pour l'instant"
            description="Lancez une analyse de CV ou un briefing commercial : les dix derniers événements de l'organisation apparaîtront ici."
          />
        ) : (
          <>
            <ActivityList events={journal.events} instanceUrl={journal.crm_instance_url} />
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
