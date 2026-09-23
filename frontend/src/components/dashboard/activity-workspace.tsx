"use client";

import { Clock } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { ActivityList } from "@/components/dashboard/activity-list";
import { EmptyState } from "@/components/ui/empty-state";
import { Label } from "@/components/ui/label";
import { Paginateur } from "@/components/ui/paginateur";
import { ScrollX } from "@/components/ui/scroll-x";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SqueletteListe } from "@/components/ui/skeletons";
import { ErrorState } from "@/components/ui/states";
import { api } from "@/lib/api";
import { SOURCE_LIBELLE, type ActivityPage } from "@/lib/dashboard";

const TAILLE_PAGE = 25;

/**
 * Vue complète de l'activité de l'organisation.
 *
 * Le tableau de bord n'en montre que les dix derniers événements : c'est un
 * aperçu. Tout ce qui était plus ancien n'existait nulle part dans
 * l'interface — pas même derrière un « voir plus ».
 *
 * Pagination côté serveur : les trois sources (présélections, écritures CRM,
 * analyses du coach) sont fusionnées et triées par le backend, l'écran ne
 * décide que de la page et du filtre.
 */
export function ActivityWorkspace() {
  const [donnees, setDonnees] = useState<ActivityPage | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [source, setSource] = useState("toutes");

  const charger = useCallback(async () => {
    setErreur(null);
    const params = new URLSearchParams({
      limit: String(TAILLE_PAGE),
      offset: String(page * TAILLE_PAGE),
    });
    if (source !== "toutes") params.set("kind", source);
    try {
      setDonnees(await api.get<ActivityPage>(`/dashboard/activity?${params}`));
    } catch {
      setErreur("Impossible de charger l'activité.");
    }
  }, [page, source]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void charger();
  }, [charger]);

  if (erreur) return <ErrorState message={erreur} onRetry={() => void charger()} />;
  if (donnees === null) return <SqueletteListe lignes={6} label="Chargement de l'activité…" />;

  // Les sources viennent du backend : en ajouter une ne demande pas de
  // toucher à cet écran.
  const sources = donnees.kinds;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <Label htmlFor="source-activite" className="sr-only">
          Filtrer par source d&apos;activité
        </Label>
        <Select
          value={source}
          onValueChange={(v) => {
            setSource(v);
            setPage(0);
          }}
        >
          <SelectTrigger id="source-activite" className="w-64">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="toutes">Toutes les sources</SelectItem>
            {sources.map((k) => (
              <SelectItem key={k} value={k}>
                {SOURCE_LIBELLE[k] ?? k}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {donnees.events.length === 0 ? (
        <EmptyState
          icon={<Clock aria-hidden />}
          title={
            source === "toutes"
              ? "Aucune activité pour l'instant"
              : "Aucune activité de cette source"
          }
          description="Une analyse de CV, une écriture confirmée dans Salesforce ou un texte soumis au coach apparaîtront ici."
        />
      ) : (
        <ScrollX borne sommet={page} label="Activité">
          <ActivityList events={donnees.events} instanceUrl={donnees.crm_instance_url} />
        </ScrollX>
      )}

      <Paginateur
        page={page}
        taille={TAILLE_PAGE}
        total={donnees.total}
        onPage={setPage}
        nom="Événements"
      />
    </div>
  );
}
